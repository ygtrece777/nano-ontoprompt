from pydantic_settings import BaseSettings
from typing import Literal
from cryptography.fernet import Fernet

class Settings(BaseSettings):
    environment: Literal["development", "production"] = "development"
    database_url: str = "sqlite:///./ontoprompt.db"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "dev-secret-key"
    encryption_key: str = ""
    first_admin_user: str = "admin"
    first_admin_password: str = "admin123"
    uploads_dir: str = "./uploads"
    access_token_expire_minutes: int = 60

    # CORS - 逗号分隔的来源列表，可通过环境变量配置
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 上传限制
    max_upload_mb: int = 200
    max_sync_rows: int = 10000
    allowed_upload_extensions: str = "csv,xlsx,xls,json,xml,pdf,docx,doc,pptx,ppt,md,txt"
    allowed_connector_hosts: str = ""

    # v2 — Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "ontoprompt123"

    # v2 — MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_use_ssl: bool = False

    # v2 — ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()

# 生产环境禁止使用默认凭据 — 启动即失败, 避免带默认密钥上线
if settings.environment == "production":
    _insecure = []
    if settings.secret_key in {"dev-secret-key", "change-me", "change-me-to-a-random-32-char-string"} or len(settings.secret_key) < 32:
        _insecure.append("SECRET_KEY")
    if settings.first_admin_password == "admin123":
        _insecure.append("FIRST_ADMIN_PASSWORD")
    if settings.minio_access_key == "minioadmin" or settings.minio_secret_key == "minioadmin":
        _insecure.append("MINIO_ACCESS_KEY/MINIO_SECRET_KEY")
    if settings.neo4j_password == "ontoprompt123":
        _insecure.append("NEO4J_PASSWORD")
    if not settings.encryption_key:
        _insecure.append("ENCRYPTION_KEY")
    else:
        try:
            Fernet(settings.encryption_key.encode())
        except Exception:
            _insecure.append("ENCRYPTION_KEY (invalid Fernet key)")
    if _insecure:
        raise RuntimeError(
            f"ENVIRONMENT=production 但以下配置仍为默认值, 必须通过环境变量注入: {', '.join(_insecure)}"
        )
