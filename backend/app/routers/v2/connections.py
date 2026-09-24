"""
v2 Connection 管理 API
POST   /api/v2/connections
GET    /api/v2/connections
GET    /api/v2/connections/{id}
POST   /api/v2/connections/{id}/test
DELETE /api/v2/connections/{id}
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import SessionLocal
from app.deps import get_current_user, require_admin, require_editor
from app.models.user import User
from app.models.v2.connection import Connection
from app.services.connection.registry import get_connector

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Pydantic 模式 ─────────────────────────────────────────────

class ConnectionCreate(BaseModel):
    name: str
    kind: str  # file | mysql | postgres | mongo | rest
    config: dict  # 明文连接配置 (服务端加密)


class ConnectionResponse(BaseModel):
    id: str
    name: str
    kind: str
    status: str

    class Config:
        from_attributes = True


# ── 端点 ──────────────────────────────────────────────────────

@router.post("", response_model=ConnectionResponse, status_code=201, dependencies=[Depends(require_editor)])
def create_connection(body: ConnectionCreate, db: Session = Depends(get_db), current_user: User = Depends(require_editor)):
    """创建连接。config 加密后存储。"""
    from app.services import encryption_service
    from app.config import settings
    if not settings.encryption_key:
        raise HTTPException(status_code=503, detail="Configure ENCRYPTION_KEY before saving connections")
    encrypted_config = {"_encrypted": encryption_service.encrypt(json.dumps(body.config))}

    conn = Connection(
        name=body.name,
        kind=body.kind,
        config=encrypted_config,
        status="inactive",
        created_by=current_user.id,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@router.get("", response_model=list[ConnectionResponse])
def list_connections(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Connection)
    if current_user.role != "admin":
        query = query.filter(Connection.created_by == current_user.id)
    return query.all()


def _owned_connection(db: Session, connection_id: str, user: User) -> Connection:
    query = db.query(Connection).filter(Connection.id == connection_id)
    if user.role != "admin":
        query = query.filter(Connection.created_by == user.id)
    connection = query.first()
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return connection


@router.get("/{connection_id}", response_model=ConnectionResponse)
def get_connection(connection_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _owned_connection(db, connection_id, current_user)


class TestConfigBody(BaseModel):
    type: str
    config: dict = {}


def _build_db_config(raw_config: dict, db_type: str) -> dict:
    """
    ConnectorInspector 发送单个字段（host/port/user/password/database）而非
    connection_string，这里组装成 SQLAlchemy 可用的连接 URL。
    密码中的特殊字符通过 urllib.parse.quote 编码以避免 URL 解析歧义。
    """
    from urllib.parse import quote
    host = raw_config.get("host", "localhost")
    port = raw_config.get("port", "3306" if db_type == "mysql" else "5432")
    user = raw_config.get("user", "")
    password = raw_config.get("password", "")
    database = raw_config.get("database", "")
    # 密码/用户名/库名中的特殊字符（如 @ : / # 空格等）必须 URL 编码，
    # 否则 SQLAlchemy 的 URL 解析器会将 @ 等视为 URL 结构分隔符而非密码的一部分。
    # host 不编码（IPv6 地址用 [] 括起，需原样保留）。
    scheme = "mysql+pymysql" if db_type == "mysql" else "postgresql"
    conn_str = f"{scheme}://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{quote(database, safe='')}"
    config = dict(raw_config)
    config["connection_string"] = conn_str
    return config


@router.post("/test-config", dependencies=[Depends(require_editor)])
def test_connection_config(body: TestConfigBody):
    """测试连接配置（无需先创建 Connection，供 Builder 使用）"""
    try:
        cfg = body.config
        if body.type in ("mysql", "postgresql", "postgres"):
            db_type = "postgres" if "postgres" in body.type else "mysql"
            cfg = _build_db_config(cfg, db_type)
        connector = get_connector(body.type, cfg)
        ok = connector.test_connection()
        return {"success": ok}
    except Exception:
        logger.exception("Connection configuration test failed")
        return {"success": False, "detail": "Connection test failed"}


@router.post("/{connection_id}/test", dependencies=[Depends(require_editor)])
def test_connection(connection_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_editor)):
    """连接测试。尝试真实连接并返回结果。"""
    conn = _owned_connection(db, connection_id, current_user)

    from app.services import encryption_service
    raw = conn.config.get("_encrypted", "")
    try:
        config = json.loads(encryption_service.decrypt(raw)) if raw else conn.config
    except Exception:
        logger.exception("Could not decrypt connection %s", connection_id)
        raise HTTPException(status_code=409, detail="Connection credentials cannot be decrypted")

    # 与 test-config 一样，ConnectionsTab 存储的是独立字段而非 connection_string
    if conn.kind in ("mysql", "postgres"):
        config = _build_db_config(config, conn.kind)

    try:
        connector = get_connector(conn.kind, config)
        ok = connector.test_connection()
        conn.status = "active" if ok else "error"
        db.commit()
        return {"success": ok, "status": conn.status}
    except Exception:
        logger.exception("Stored connection test failed for %s", connection_id)
        conn.status = "error"
        db.commit()
        return {"success": False, "status": "error", "detail": "Connection test failed"}


@router.delete("/{connection_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_connection(connection_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    conn = _owned_connection(db, connection_id, current_user)
    db.delete(conn)
    db.commit()


@router.post("/{connection_id}/schedule", dependencies=[Depends(require_editor)])
def set_schedule(connection_id: str, cron_expr: str, db: Session = Depends(get_db), current_user: User = Depends(require_editor)):
    """为连接设置 Cron 调度表达式"""
    from app.services.v2.scheduler.cron_service import CronService
    svc = CronService()
    if not svc.validate_cron(cron_expr):
        raise HTTPException(400, f"无效的 cron 表达式: {cron_expr}")

    conn = _owned_connection(db, connection_id, current_user)

    result = svc.schedule_connection_sync(connection_id, cron_expr)
    config = dict(conn.config or {})
    config["schedule_cron"] = cron_expr
    conn.config = config
    db.commit()
    return result


@router.post("/{connection_id}/sync", dependencies=[Depends(require_editor)])
def trigger_sync(connection_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_editor)):
    """手动触发数据同步"""
    conn = _owned_connection(db, connection_id, current_user)

    if conn.status == "syncing":
        raise HTTPException(status_code=409, detail="Connection sync is already running")

    conn.status = "syncing"
    config = dict(conn.config or {})
    config["sync_started_at"] = datetime.now(timezone.utc).isoformat()
    conn.config = config
    db.commit()
    try:
        from app.tasks.v2.connection_sync import sync_connection_task
        task = sync_connection_task.delay(connection_id)
    except Exception:
        db.rollback()
        conn.status = "error"
        config = dict(conn.config or {})
        config.pop("sync_started_at", None)
        conn.config = config
        db.commit()
        logger.exception("Could not dispatch connection sync for %s", connection_id)
        return {"connection_id": connection_id, "status": "sync_failed",
                "error": "Task dispatch failed"}

    return {"connection_id": connection_id, "status": "sync_triggered", "task_id": task.id}
