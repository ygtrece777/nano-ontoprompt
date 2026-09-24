"""Synchronize connection resources into versioned raw datasets."""
from __future__ import annotations

import json
import logging
import hashlib
from datetime import datetime, timezone, timedelta

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def sync_connection(connection_id: str, mode: str = "full") -> dict:
    if mode != "full":
        raise ValueError("Incremental connection sync needs a durable watermark and is not available yet")

    from app.database import SessionLocal
    from app.models.v2.connection import Connection
    from app.models.v2.dataset import Dataset
    from app.services.connection.registry import get_connector
    from app.services.encryption_service import decrypt
    from app.services.v2.dataset_service import DatasetService
    from app.config import settings

    db = SessionLocal()
    try:
        connection = db.query(Connection).filter(Connection.id == connection_id).first()
        if connection is None:
            raise ValueError("Connection not found")
        encrypted = (connection.config or {}).get("_encrypted")
        if not encrypted:
            raise ValueError("Connection configuration is missing encrypted credentials")
        config = json.loads(decrypt(encrypted))
        if connection.kind in ("mysql", "postgres", "postgresql") and "connection_string" not in config:
            from app.routers.v2.connections import _build_db_config
            config = _build_db_config(config, "mysql" if connection.kind == "mysql" else "postgres")
        connector = get_connector(connection.kind, config)
        resources = config.get("resources") or connector.list_resources()
        if not isinstance(resources, list) or not all(isinstance(item, str) for item in resources):
            raise ValueError("Connection resources must be a list of names")
        if not resources:
            raise ValueError("Connection has no resources to synchronize")

        service = DatasetService(db)
        synced = []
        for resource in resources:
            result = connector.pull_full(resource)
            if isinstance(result, bytes):
                content, kind, rowcount = result, "unstructured", None
            elif isinstance(result, list):
                content = json.dumps(result, ensure_ascii=False, default=str).encode("utf-8")
                kind, rowcount = "structured", len(result)
            else:
                raise ValueError(f"Unsupported data returned by resource {resource!r}")
            if len(content) > settings.max_upload_mb * 1024 * 1024:
                raise ValueError(f"Resource {resource!r} exceeds MAX_UPLOAD_MB")

            name = f"{connection.name}/{resource}"
            dataset = db.query(Dataset).filter(
                Dataset.source_connection_id == connection_id,
                Dataset.name == name,
            ).first()
            if dataset is None:
                dataset = service.create_dataset(name=name, kind=kind, connection_id=connection_id,
                                                 created_by=connection.created_by)
            checksum = hashlib.sha256(content).hexdigest()
            from app.models.v2.dataset import DatasetVersion
            latest = db.query(DatasetVersion).filter(DatasetVersion.id == dataset.latest_version_id).first()
            if latest is not None and latest.checksum == checksum:
                version = latest
            else:
                version = service.create_version(dataset.id, content, rowcount=rowcount)
            synced.append({"dataset_id": dataset.id, "version_no": version.version_no, "rows": rowcount})

        connection.status = "active"
        connection.last_sync_at = datetime.now(timezone.utc)
        state = dict(connection.config or {})
        state.pop("sync_started_at", None)
        connection.config = state
        db.commit()
        from app.services.v2.incremental.orchestrator import IncrementalOrchestrator
        orchestrator = IncrementalOrchestrator(db)
        for item in synced:
            orchestrator.on_connection_sync(connection_id, item["dataset_id"])
        return {"status": "ok", "resources": synced}
    except Exception:
        db.rollback()
        connection = db.query(Connection).filter(Connection.id == connection_id).first()
        if connection is not None:
            connection.status = "error"
            state = dict(connection.config or {})
            state.pop("sync_started_at", None)
            connection.config = state
            db.commit()
        logger.exception("Connection sync failed for %s", connection_id)
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.v2.connection_sync.sync_connection_task", time_limit=3600)
def sync_connection_task(connection_id: str) -> dict:
    return sync_connection(connection_id)


@celery_app.task(name="app.tasks.v2.connection_sync.poll_scheduled_connections")
def poll_scheduled_connections() -> dict:
    """Dispatch due full snapshots from the persisted connection schedules."""
    from celery.schedules import crontab
    from app.database import SessionLocal
    from app.models.v2.connection import Connection
    from app.services.v2.scheduler.cron_service import CronService

    db = SessionLocal()
    queued = []
    try:
        now = datetime.now(timezone.utc)
        for connection in db.query(Connection).all():
            config = dict(connection.config or {})
            expression = config.get("schedule_cron")
            if not expression:
                continue
            if connection.status == "syncing":
                started = config.get("sync_started_at")
                try:
                    if started and now - datetime.fromisoformat(started) < timedelta(minutes=70):
                        continue
                except (ValueError, TypeError):
                    pass
                connection.status = "error"
                config.pop("sync_started_at", None)
                connection.config = config
                db.commit()
            try:
                schedule = crontab(**CronService().parse_cron(expression))
                previous = config.get("schedule_last_attempt_at")
                last_attempt = datetime.fromisoformat(previous) if previous else now - timedelta(minutes=1)
                if not schedule.is_due(last_attempt).is_due:
                    continue
                config["schedule_last_attempt_at"] = now.isoformat()
                config["sync_started_at"] = now.isoformat()
                connection.config = config
                connection.status = "syncing"
                db.commit()
                sync_connection_task.delay(connection.id)
                queued.append(connection.id)
            except Exception:
                db.rollback()
                connection.status = "error"
                state = dict(connection.config or {})
                state.pop("sync_started_at", None)
                connection.config = state
                db.commit()
                logger.exception("Could not schedule connection %s", connection.id)
        return {"queued": queued}
    finally:
        db.close()
