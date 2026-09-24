"""为制造质量管理本体补充可演示的实例级供应链数据。"""
from __future__ import annotations
import uuid

from app.database import SessionLocal
from app.models.entity import Entity
from app.models.relation import Relation
from app.models.ontology import OntologyProject


DATA = [
    ("华东精密供应商", "Supplier", "为制造工厂提供金属材料"),
    ("华南电子供应商", "Supplier", "为制造工厂提供电子元件"),
    ("不锈钢板材", "Material", "用于结构件生产"),
    ("工业控制器", "Material", "用于设备控制模块"),
    ("智能装配设备", "Equipment", "用于自动化装配"),
    ("质量检验工单-2026-001", "QualityInspection", "装配批次的首件检验记录"),
    ("装配工单-2026-001", "WorkOrder", "智能控制柜装配生产工单"),
    ("智能控制柜", "Product", "制造完成的工业控制产品"),
]


def main() -> None:
    db = SessionLocal()
    try:
        ontology = db.query(OntologyProject).filter(OntologyProject.name == "制造质量管理本体").first()
        if not ontology:
            raise SystemExit("未找到制造质量管理本体")
        oid = ontology.id
        entities: dict[str, Entity] = {}
        for name, kind, description in DATA:
            e = db.query(Entity).filter(Entity.ontology_id == oid, Entity.name_cn == name).first()
            if not e:
                e = Entity(id=str(uuid.uuid4()), ontology_id=oid, name_cn=name, name_en=name,
                           type=kind, description=description, properties={"demo_seed": True}, confidence=0.95)
                db.add(e)
            entities[name] = e
        db.flush()

        relations = [
            ("华东精密供应商", "不锈钢板材", "SUPPLIED_BY"),
            ("华南电子供应商", "工业控制器", "SUPPLIED_BY"),
            ("装配工单-2026-001", "不锈钢板材", "USES_MATERIAL"),
            ("装配工单-2026-001", "工业控制器", "USES_MATERIAL"),
            ("装配工单-2026-001", "智能装配设备", "USES_EQUIPMENT"),
            ("装配工单-2026-001", "智能控制柜", "PRODUCES"),
            ("质量检验工单-2026-001", "智能控制柜", "INSPECTS"),
        ]
        for source, target, rel_type in relations:
            exists = db.query(Relation).filter(
                Relation.ontology_id == oid,
                Relation.source_entity == entities[source].id,
                Relation.target_entity == entities[target].id,
                Relation.type == rel_type,
            ).first()
            if not exists:
                db.add(Relation(id=str(uuid.uuid4()), ontology_id=oid,
                                source_entity=entities[source].id, target_entity=entities[target].id,
                                type=rel_type, properties={"demo_seed": True}, confidence=0.95))
        db.commit()
        print(f"seeded ontology={oid} entities={len(DATA)} relations={len(relations)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
