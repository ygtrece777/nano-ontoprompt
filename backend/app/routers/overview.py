from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.deps import get_db, get_current_user
from app.models.ontology import OntologyProject

router = APIRouter()

def _safe_count(db, model):
    try:
        return db.query(model).count()
    except Exception:
        return 0


def _combined_count(db, legacy_model, v2_model, ontology_id=None):
    """Count legacy + V2 records, preferring V2 when the same named item exists."""
    try:
        legacy_query = db.query(legacy_model)
        v2_query = db.query(v2_model)
        if ontology_id is not None:
            legacy_query = legacy_query.filter(legacy_model.ontology_id == ontology_id)
            v2_query = v2_query.filter(v2_model.ontology_id == ontology_id)
        legacy_rows = legacy_query.all()
        v2_rows = v2_query.all()
        # V1 uses name_cn, while V2 uses name.  A mirrored record is one logical item.
        v2_names = {getattr(row, "name", None) for row in v2_rows}
        unique_legacy = [row for row in legacy_rows if getattr(row, "name_cn", None) not in v2_names]
        return len(v2_rows) + len(unique_legacy)
    except Exception:
        # Keep the overview available during migrations where one of the tables may not exist.
        return _safe_count(db, legacy_model)

@router.get("/stats")
def get_stats(db: Session = Depends(get_db), _=Depends(get_current_user)):
    from app.models.entity import Entity
    from app.models.logic import LogicRule
    from app.models.action import Action
    from app.models.v2.logic import OntologyLogicRule
    from app.models.v2.action import OntologyActionType

    # Recent ontologies
    recent = db.query(OntologyProject).order_by(OntologyProject.updated_at.desc()).limit(6).all()
    recent_list = []
    for o in recent:
        entity_count = db.query(Entity).filter(Entity.ontology_id == o.id).count()
        logic_count = _combined_count(db, LogicRule, OntologyLogicRule, o.id)
        action_count = _combined_count(db, Action, OntologyActionType, o.id)
        recent_list.append({
            "id": o.id,
            "name": o.name,
            "domain": o.domain,
            "status": o.status,
            "entity_count": entity_count,
            "logic_count": logic_count,
            "action_count": action_count,
            "updated_at": o.updated_at.isoformat() if o.updated_at else None,
        })

    # Domain distribution
    domain_rows = (
        db.query(OntologyProject.domain, func.count(OntologyProject.id))
        .group_by(OntologyProject.domain)
        .all()
    )
    domain_counts = {row[0]: row[1] for row in domain_rows if row[0]}

    # Status breakdown
    status_rows = (
        db.query(OntologyProject.status, func.count(OntologyProject.id))
        .group_by(OntologyProject.status)
        .all()
    )
    status_counts = {row[0]: row[1] for row in status_rows if row[0]}

    return {
        "data": {
            "ontology_count": _safe_count(db, OntologyProject),
            "entity_count": _safe_count(db, Entity),
            "logic_count": _combined_count(db, LogicRule, OntologyLogicRule),
            "action_count": _combined_count(db, Action, OntologyActionType),
            "recent_ontologies": recent_list,
            "domain_counts": domain_counts,
            "status_counts": status_counts,
        },
        "message": "ok"
    }
