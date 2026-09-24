from celery import Celery
from app.config import settings

celery_app = Celery("ontoprompt",
                    broker=settings.redis_url,
                    backend=settings.redis_url,
                    include=["app.tasks.extraction", "app.tasks.audit",
                             "app.tasks.v2.pipeline_run", "app.tasks.v2.mapping_apply",
                             "app.tasks.v2.connection_sync"])

# broker 不可用时快速失败 (默认会长时间重试, 导致 API 请求阻塞)
celery_app.conf.task_publish_retry = False
celery_app.conf.broker_connection_timeout = 3
# Celery 6 will require this explicit startup retry setting.
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.beat_schedule = {
    "poll-connection-schedules": {
        "task": "app.tasks.v2.connection_sync.poll_scheduled_connections",
        "schedule": 60.0,
    },
}
