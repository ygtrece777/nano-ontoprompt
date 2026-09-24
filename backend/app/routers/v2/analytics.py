"""Cross-domain analytics for ontology dashboards."""
from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends
from app.deps import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _first(props: dict, *keys: str) -> str:
    for key in keys:
        if _text(props.get(key)):
            return _text(props[key])
    return ""


def _risk(props: dict, object_type: str) -> tuple[str, str, str] | None:
    pairs = [
        ("on_time", ("延误", "延迟", "late", "delayed"), "物流延误"),
        ("status", ("逾期", "高", "失败", "待处理", "处理中", "overdue", "high"), "状态风险"),
        ("followup_status", ("延误", "逾期", "overdue"), "随访延误"),
        ("is_over_budget", ("是", "yes", "true"), "费用超标"),
        ("retention_risk", ("高", "high"), "高流失风险"),
        ("risk_level", ("高", "high"), "高风险"),
    ]
    for key, values, reason in pairs:
        value = _text(props.get(key)).lower()
        if value and any(v.lower() in value for v in values):
            title = _first(props, "display_name", "name", "name_cn", "id")
            severity = "high" if any(v in value for v in ("高", "high", "死亡", "逾期", "overdue")) else "medium"
            return title, reason, severity
    return None


@router.get("/{ontology_id}/analytics")
def analytics(ontology_id: str):
    from app.routers.v2.graph import get_neo4j
    from app.database import SessionLocal
    from app.models.entity import Entity
    from app.models.entity_instance import EntityInstance

    # 业务实例的权威来源是 EntityInstance，而不是 Neo4j 中用于绘图的展示节点。
    db = SessionLocal()
    try:
        entity_types_db = {
            e.id: (e.type or "Entity")
            for e in db.query(Entity).filter(Entity.ontology_id == ontology_id).all()
        }
        instance_rows_db = db.query(EntityInstance).filter(EntityInstance.ontology_id == ontology_id).all()
        db_instance_type_counts = Counter(entity_types_db.get(i.entity_id, "Entity") for i in instance_rows_db)
        db_instance_count = len(instance_rows_db)
    finally:
        db.close()

    neo = get_neo4j()
    if not neo.available:
        return {
            "available": False,
            "totals": {"rows": 0, "concepts": 0, "types": 0, "edges": 0},
            "entity_types": [], "status_breakdown": [], "risk_items": [],
            "sources": [], "trend": [],
        }

    rows = neo.run_cypher(
        """
        MATCH (n)
        WHERE n.ontology_id = $ontology_id
        RETURN properties(n) AS props, labels(n) AS labels
        LIMIT 10000
        """,
        {"ontology_id": ontology_id},
    )
    edge_rows = neo.run_cypher(
        "MATCH (n)-[r]->(m) WHERE n.ontology_id = $ontology_id AND m.ontology_id = $ontology_id RETURN type(r) AS type, count(r) AS count",
        {"ontology_id": ontology_id},
    )
    neo.close()

    entity_rows = []
    concepts = 0
    type_counts: Counter[str] = Counter()
    ontology_type_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    risks = []
    for raw in rows:
        props = dict(raw.get("props") or {})
        labels = raw.get("labels") or []
        ontology_type = _first(props, "object_type", "type") or (_text(labels[0]) if labels else "Entity")
        ontology_type_counts[ontology_type] += 1
        if props.get("is_concept") is True:
            concepts += 1
            continue
        object_type = ontology_type
        type_counts[object_type] += 1
        source = _first(props, "source_dataset", "source", "source_file") or "已映射数据"
        source_counts[source] += 1
        status = _first(props, "status", "on_time", "followup_status", "approval_status", "lead_status")
        if status:
            status_counts[status] += 1
        risk = _risk(props, object_type)
        if risk and len(risks) < 100:
            title, reason, severity = risk
            risks.append({"title": title, "reason": reason, "severity": severity, "type": object_type})
        entity_rows.append(props)

    # EntityInstance 是全量统计；只有在旧数据尚未迁移时才回退到图谱行节点。
    if db_instance_count > 0:
        type_counts = db_instance_type_counts
        entity_rows_count = db_instance_count
    else:
        entity_rows_count = len(entity_rows)

    return {
        "available": True,
        "totals": {
            "rows": entity_rows_count, "concepts": concepts,
            "types": len(ontology_type_counts), "data_types": len(type_counts),
            "ontology_entities": len(rows), "edges": sum(int(r.get("count", 0)) for r in edge_rows),
        },
        "entity_types": [{"name": k, "count": v} for k, v in type_counts.most_common(12)],
        "ontology_entity_types": [{"name": k, "count": v} for k, v in ontology_type_counts.most_common(20)],
        "relation_types": [{"name": _text(r.get("type")) or "RELATED", "count": int(r.get("count", 0))} for r in edge_rows],
        "status_breakdown": [{"name": k, "count": v} for k, v in status_counts.most_common(12)],
        "risk_items": risks,
        "sources": [{"name": k, "count": v} for k, v in source_counts.most_common(12)],
        "trend": [],
    }
