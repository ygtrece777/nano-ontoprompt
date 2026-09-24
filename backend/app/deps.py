from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError
from app.database import SessionLocal
from app.services.auth_service import decode_token, get_user_by_id
from app.models.user import User

bearer = HTTPBearer(auto_error=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=403, detail="Not authenticated")
    try:
        payload = decode_token(credentials.credentials)
        user = get_user_by_id(db, payload["sub"])
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return current_user

def require_editor(current_user: User = Depends(get_current_user)) -> User:
    """编辑权限：admin 或 editor 角色。"""
    if current_user.role not in ("admin", "editor"):
        raise HTTPException(status_code=403, detail="Editor role required")
    return current_user


def require_ontology_access(
    ontology_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """Only the creator and administrators may access an ontology."""
    from app.models.ontology import OntologyProject

    project = db.query(OntologyProject).filter(OntologyProject.id == ontology_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Ontology not found")
    if current_user.role != "admin" and project.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Ontology not found")
    return current_user


def require_pipeline_access(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    from app.models.v2.pipeline import Pipeline

    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if pipeline is None or (current_user.role != "admin" and pipeline.created_by != current_user.id):
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return current_user


def require_dataset_access(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    from app.models.v2.dataset import Dataset

    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if dataset is None or (current_user.role != "admin" and dataset.created_by != current_user.id):
        raise HTTPException(status_code=404, detail="Dataset not found")
    return current_user


def require_curated_access(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    from app.models.v2.dataset import Dataset
    from app.models.v2.curated import CuratedDataset
    from app.models.v2.pipeline import Pipeline

    dataset = db.query(Dataset).filter(Dataset.id == dataset_id, Dataset.kind == "curated").first()
    curated = db.query(CuratedDataset).filter(CuratedDataset.id == dataset_id).first()
    if dataset is None and curated is None:
        raise HTTPException(status_code=404, detail="Curated dataset not found")
    if current_user.role == "admin":
        return current_user
    if dataset is not None and dataset.created_by == current_user.id:
        return current_user
    if curated is not None and curated.pipeline_id:
        pipeline = db.query(Pipeline).filter(Pipeline.id == curated.pipeline_id).first()
        if pipeline is not None and pipeline.created_by == current_user.id:
            return current_user
    raise HTTPException(status_code=404, detail="Curated dataset not found")


def require_review_access(
    review_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    from app.models.v2.curated import CuratedReview

    review = db.query(CuratedReview).filter(CuratedReview.id == review_id).first()
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return require_curated_access(review.curated_dataset_id, db, current_user)
