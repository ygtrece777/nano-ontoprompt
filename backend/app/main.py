"""
OntoPrompt API v2

架构：FastAPI + PostgreSQL + Neo4j + ChromaDB + MinIO + Celery/Redis
v2 新增：Pipelines 全链路（Connection→Dataset→Transform→Curated→Mapping）
v1 兼容：/api/v1/* 路由全部保留

启动：uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
import logging
from app.database import engine, Base, SessionLocal
from app.config import settings
from app.deps import require_ontology_access

logger = logging.getLogger(__name__)
from app.routers import auth, users, overview, ontologies, files, prompts, models, entities, logic, actions, extraction, graph, settings as settings_router, export, audit
from app.routers.v2 import connections as connections_v2
from app.routers.v2 import datasets as datasets_v2
from app.routers.v2 import pipelines as pipelines_v2
from app.routers.v2 import graph as graph_v2
from app.routers.v2 import search as search_v2
from app.routers.v2 import curated as curated_v2
from app.routers.v2 import mappings as mappings_v2
from app.routers.v2 import analytics as analytics_v2
from app.routers.v2 import incremental as incremental_v2
from app.routers.v2 import logic_actions as logic_actions_v2

def _run_schema_migration():
    """统一 schema 迁移入口。

    生产环境通过 Alembic 管理迁移；开发环境若库未纳入 Alembic 版本管理
    （如由 create_all 建起的旧库），则回退到 create_all 兜底并 stamp 到最新版本。
    """
    import os
    from alembic import command
    from alembic.config import Config as AlembicConfig

    alembic_ini = os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini")
    cfg = AlembicConfig(alembic_ini)
    if os.environ.get("DATABASE_URL"):
        cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"].replace("%", "%%"))

    if settings.environment == "production":
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        expected = ScriptDirectory.from_config(cfg).get_current_head()
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
        if current != expected:
            raise RuntimeError(f"Database revision {current!r} is not at required revision {expected!r}")
        return

    try:
        # 已存在表但未纳入 alembic 版本管理时，stamp 到基线再升级
        insp = inspect(engine)
        existing_tables = set(insp.get_table_names())
        has_alembic_version = "alembic_version" in existing_tables
        if existing_tables and not has_alembic_version:
            if settings.environment == "production":
                raise RuntimeError("Existing database has no Alembic revision; migrate it explicitly")
            command.stamp(cfg, "0001_full_baseline")
        command.upgrade(cfg, "head")
    except Exception:
        if settings.environment == "production":
            logger.exception("database migration failed during production startup")
            raise
        # 开发环境兜底：alembic 失败时用 create_all 保证表结构就位
        logger.warning("alembic upgrade failed; falling back to Base.metadata.create_all", exc_info=True)
        Base.metadata.create_all(bind=engine)


def _seed_db():
    from app.services.auth_service import seed_admin
    from app.models.rules_config import RulesConfig
    import uuid

    db = SessionLocal()
    try:
        # Import all models to ensure tables are created
        from app.models import user, ontology, file, prompt, model_config, entity, logic as logic_model, action, relation, extraction_task, rules_config, audit_task
        from app.models import user, ontology, file, prompt, model_config, entity, logic as logic_model, action, relation, extraction_task, rules_config
        from app.models.v2 import dataset as v2_dataset, pipeline as v2_pipeline, connection as v2_connection  # noqa: F401
        from app.models.v2.logic import OntologyLogicRule, OntologyStateMachine  # noqa: F401
        from app.models.v2.action import OntologyActionType, OntologyActionRun  # noqa: F401
        from app.models.v2.curated import CuratedDataset, CuratedReview, CuratedRowEdit  # noqa: F401
        from app.models.v2.mapping import OntologyMapping, OntologyLinkMapping  # noqa: F401
        _run_schema_migration()

        seed_admin(db)

        # 重启时清理遗留的 running 任务 — daemon 线程被杀后 task 会永久卡在 85%
        from app.models.extraction_task import ExtractionTask
        stale = db.query(ExtractionTask).filter(ExtractionTask.status == "running").all()
        for t in stale:
            t.status = "failed"
            t.error  = "服务重启，任务中断。请重新触发提取。"
        if stale:
            db.commit()

        # Seed confidence rules
        if db.query(RulesConfig).count() == 0:
            rules = [
                ("confidence_entity_min", "0.5", "实体最低置信度", "Entity min confidence"),
                ("confidence_logic_min", "0.6", "逻辑规则最低置信度", "Logic rule min confidence"),
                ("confidence_action_min", "0.6", "动作最低置信度", "Action min confidence"),
                ("confidence_relation_min", "0.5", "关系最低置信度", "Relation min confidence"),
                ("confidence_high_threshold", "0.9", "高置信度阈值", "High confidence threshold"),
                ("confidence_medium_threshold", "0.7", "中置信度阈值", "Medium confidence threshold"),
                ("confidence_low_threshold", "0.5", "低置信度阈值", "Low confidence threshold"),
                ("confidence_display_dashed_below", "0.7", "低于此值显示虚线边", "Show dashed edge below threshold"),
            ]
            for key, val, label_cn, label_en in rules:
                db.add(RulesConfig(id=str(uuid.uuid4()), rule_key=key, rule_value=val,
                                   rule_label_cn=label_cn, rule_label_en=label_en))
            db.commit()

        # Seed / update builtin prompts (upsert by name)
        from app.models.prompt import Prompt
        from app.models.user import User
        from app.routers.prompts import BUILTIN_PROMPTS
        admin = db.query(User).filter(User.role == "admin").first()
        if admin:
            for p in BUILTIN_PROMPTS:
                existing = db.query(Prompt).filter(Prompt.name == p["name"]).first()
                if existing:
                    if settings.environment == "development":
                        existing.content = p["content"]
                        existing.domain = p["domain"]
                else:
                    db.add(Prompt(id=str(uuid.uuid4()), name=p["name"], domain=p["domain"],
                                  content=p["content"], version="v1.0", created_by=admin.id))
            db.commit()

        # 制造本体演示实例：让图谱查询返回具体供应商/物料，而不是只有类型概念。
        from app.models.ontology import OntologyProject
        from app.models.entity import Entity
        from app.models.relation import Relation
        manufacturing = db.query(OntologyProject).filter(OntologyProject.name == "制造质量管理本体").first()
        if manufacturing and settings.environment != "production":
            seed = [
                ("华东精密供应商", "Supplier", "为制造工厂提供金属材料"),
                ("华南电子供应商", "Supplier", "为制造工厂提供电子元件"),
                ("不锈钢板材", "Material", "用于结构件生产"),
                ("工业控制器", "Material", "用于设备控制模块"),
                ("智能装配设备", "Equipment", "用于自动化装配"),
                ("质量检验工单-2026-001", "QualityInspection", "装配批次的首件检验记录"),
                ("装配工单-2026-001", "WorkOrder", "智能控制柜装配生产工单"),
                ("智能控制柜", "Product", "制造完成的工业控制产品"),
            ]
            by_name = {}
            for name, kind, desc in seed:
                entity = db.query(Entity).filter(Entity.ontology_id == manufacturing.id, Entity.name_cn == name).first()
                if not entity:
                    entity = Entity(id=str(uuid.uuid4()), ontology_id=manufacturing.id, name_cn=name,
                                    name_en=name, type=kind, description=desc,
                                    properties={"demo_seed": True}, confidence=0.95)
                    db.add(entity)
                by_name[name] = entity
            db.flush()
            for source, target, rel_type in [
                ("华东精密供应商", "不锈钢板材", "SUPPLIED_BY"),
                ("华南电子供应商", "工业控制器", "SUPPLIED_BY"),
                ("装配工单-2026-001", "不锈钢板材", "USES_MATERIAL"),
                ("装配工单-2026-001", "工业控制器", "USES_MATERIAL"),
                ("装配工单-2026-001", "智能装配设备", "USES_EQUIPMENT"),
                ("装配工单-2026-001", "智能控制柜", "PRODUCES"),
                ("质量检验工单-2026-001", "智能控制柜", "INSPECTS"),
            ]:
                exists = db.query(Relation).filter(Relation.ontology_id == manufacturing.id,
                    Relation.source_entity == by_name[source].id, Relation.target_entity == by_name[target].id,
                    Relation.type == rel_type).first()
                if not exists:
                    db.add(Relation(id=str(uuid.uuid4()), ontology_id=manufacturing.id,
                                    source_entity=by_name[source].id, target_entity=by_name[target].id,
                                    type=rel_type, properties={"demo_seed": True}, confidence=0.95))
            db.commit()
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_db()
    try:
        from app.models.ontology import OntologyProject
        db = SessionLocal()
        manufacturing_id = db.query(OntologyProject.id).filter(OntologyProject.name == "制造质量管理本体").scalar()
        db.close()
        if manufacturing_id and settings.environment != "production":
            graph_v2.sync_graph(manufacturing_id)
    except Exception:
        logger.warning("manufacturing graph sync skipped", exc_info=True)
    # 初始化 Neo4j 索引（后台执行，不阻塞启动）
    try:
        from app.services.v2.graph.index_setup import setup_indexes
        setup_indexes()
    except Exception:
        logger.warning("Neo4j index setup skipped (unavailable); startup continues", exc_info=True)
    yield

app = FastAPI(title="OntoPrompt API", version="0.1.0", lifespan=lifespan)

# 注册限流器 - 保护 Auth 等敏感端点
from app.limiter import limiter
from slowapi.middleware import SlowAPIMiddleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(overview.router, prefix="/api/v1/overview", tags=["overview"])
app.include_router(ontologies.router, prefix="/api/v1/ontologies", tags=["ontologies"])
app.include_router(files.router, prefix="/api/v1/ontologies/{ontology_id}/files", tags=["files"], dependencies=[Depends(require_ontology_access)])
app.include_router(entities.router, prefix="/api/v1/ontologies/{ontology_id}/entities", tags=["entities"], dependencies=[Depends(require_ontology_access)])
app.include_router(logic.router, prefix="/api/v1/ontologies/{ontology_id}/logic", tags=["logic"], dependencies=[Depends(require_ontology_access)])
app.include_router(actions.router, prefix="/api/v1/ontologies/{ontology_id}/actions", tags=["actions"], dependencies=[Depends(require_ontology_access)])
app.include_router(extraction.router, prefix="/api/v1/ontologies/{ontology_id}/execute", tags=["extraction"], dependencies=[Depends(require_ontology_access)])
app.include_router(graph.router, prefix="/api/v1/ontologies/{ontology_id}/graph", tags=["graph"], dependencies=[Depends(require_ontology_access)])
app.include_router(export.router, prefix="/api/v1/ontologies/{ontology_id}/export", tags=["export"], dependencies=[Depends(require_ontology_access)])
app.include_router(audit.router, prefix="/api/v1/ontologies/{ontology_id}/audit", tags=["audit"], dependencies=[Depends(require_ontology_access)])
app.include_router(prompts.router, prefix="/api/v1/prompts", tags=["prompts"])
app.include_router(models.router, prefix="/api/v1/models", tags=["models"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(connections_v2.router, prefix="/api/v2/connections", tags=["v2-connections"])
app.include_router(datasets_v2.router, prefix="/api/v2/datasets", tags=["v2-datasets"])
app.include_router(pipelines_v2.router, prefix="/api/v2/pipelines", tags=["v2-pipelines"])
app.include_router(graph_v2.router, prefix="/api/v2/ontologies", tags=["v2-graph"], dependencies=[Depends(require_ontology_access)])
app.include_router(search_v2.router, prefix="/api/v2/ontologies", tags=["v2-search"], dependencies=[Depends(require_ontology_access)])
app.include_router(curated_v2.router, prefix="/api/v2/curated", tags=["v2-curated"])
app.include_router(mappings_v2.router, prefix="/api/v2/ontologies", tags=["v2-mappings"], dependencies=[Depends(require_ontology_access)])
app.include_router(analytics_v2.router, prefix="/api/v2/ontologies", tags=["v2-analytics"], dependencies=[Depends(require_ontology_access)])
app.include_router(incremental_v2.router, prefix="/api/v2/incremental", tags=["v2-incremental"])
app.include_router(logic_actions_v2.router, prefix="/api/v2/ontologies", tags=["v2-logic-actions"], dependencies=[Depends(require_ontology_access)])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health(response: Response, db: Session = Depends(get_db)):
    checks = {
        "status": "ok",
        "db": "unknown",
        "neo4j": "unknown",
        "minio": "unknown",
        "chroma": "unknown",
    }

    # PostgreSQL check
    try:
        db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"

    # Neo4j check
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        driver.verify_connectivity()
        driver.close()
        checks["neo4j"] = "ok"
    except Exception:
        checks["neo4j"] = "unavailable"

    # MinIO check
    try:
        from minio import Minio
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_use_ssl,
        )
        client.list_buckets()
        checks["minio"] = "ok"
    except Exception:
        checks["minio"] = "unavailable"

    # ChromaDB check
    try:
        import chromadb
        client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
        client.heartbeat()
        checks["chroma"] = "ok"
    except Exception:
        checks["chroma"] = "unavailable"

    if checks["db"] != "ok":
        checks["status"] = "error"
        response.status_code = 503
    return checks
