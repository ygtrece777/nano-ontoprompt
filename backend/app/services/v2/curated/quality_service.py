"""Curated Dataset 质量评估服务"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any
from sqlalchemy.orm import Session
from app.models.v2.curated import CuratedDataset


@dataclass
class ColumnQuality:
    name: str
    null_count: int
    null_pct: float
    distinct_count: int
    sample_values: list[str]
    inferred_type: str


@dataclass
class QualityReport:
    dataset_id: str
    row_count: int
    column_count: int
    completeness_score: float      # 0~1，非空率平均值
    uniqueness_score: float        # 0~1，主键无重复
    validity_score: float          # 0~1，类型一致性
    overall_score: float           # 三项加权平均
    columns: list[ColumnQuality]
    duplicate_count: int
    issues: list[str]              # 质量问题描述列表
    analyzed_rows: int = 0
    coverage_pct: float = 0.0
    issue_details: list[dict] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "dataset_id": self.dataset_id,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "completeness_score": round(self.completeness_score, 3),
            "uniqueness_score": round(self.uniqueness_score, 3),
            "validity_score": round(self.validity_score, 3),
            "overall_score": round(self.overall_score, 3),
            "duplicate_count": self.duplicate_count,
            "issues": self.issues,
            "analyzed_rows": self.analyzed_rows or self.row_count,
            "coverage_pct": round(self.coverage_pct or 100.0, 1),
            "issue_details": self.issue_details,
            "recommendations": self.recommendations,
            "columns": [
                {
                    "name": c.name,
                    "null_pct": round(c.null_pct, 2),
                    "distinct_count": c.distinct_count,
                    "inferred_type": c.inferred_type,
                    "sample_values": c.sample_values[:3],
                }
                for c in self.columns
            ],
        }


class QualityService:
    """对 Curated Dataset 的数据行进行质量分析"""

    def __init__(self, db: Session):
        self._db = db

    def compute_report(self, curated_dataset_id: str, data: list[dict]) -> QualityReport:
        """
        根据传入的数据行列表计算质量报告。
        data：从 pipeline 输出的 curated 数据行，每行是 dict。
        """
        if not data:
            return QualityReport(
                dataset_id=curated_dataset_id,
                row_count=0, column_count=0,
                completeness_score=1.0, uniqueness_score=1.0,
                validity_score=1.0, overall_score=1.0,
                columns=[], duplicate_count=0, issues=["数据集为空"],
                analyzed_rows=0, coverage_pct=100.0,
                issue_details=[{"severity": "error", "code": "empty_dataset", "message": "数据集为空"}],
                recommendations=["先完成数据生成或发布，再进行质量审核"],
            )

        row_count = len(data)
        # 合并所有行的字段，避免首行缺字段导致漏检
        columns_names = list(dict.fromkeys(k for row in data for k in row.keys()))
        column_count = len(columns_names)
        issues = []
        issue_details = []
        recommendations = []

        # ── 列级质量分析 ──────────────────────────────────────────
        col_qualities = []
        null_rates = []

        for col in columns_names:
            values = [row.get(col) for row in data]
            null_count = sum(
                1 for v in values
                if v is None or (isinstance(v, str) and v.strip() == "")
            )
            non_null = [v for v in values if v is not None and str(v).strip() != ""]
            null_pct = null_count / row_count * 100
            null_rates.append(null_pct)

            distinct_count = len(set(str(v) for v in non_null))
            sample_values = [str(v) for v in non_null[:5]]
            inferred_type = self._infer_type(non_null)

            col_qualities.append(ColumnQuality(
                name=col,
                null_count=null_count,
                null_pct=null_pct,
                distinct_count=distinct_count,
                sample_values=sample_values,
                inferred_type=inferred_type,
            ))

            if null_pct > 50:
                message = f"列 '{col}' 空值率过高：{null_pct:.1f}%"
                issues.append(message)
                issue_details.append({"severity": "error", "code": "high_null_rate", "column": col, "message": message})
                recommendations.append(f"补齐或删除字段 '{col}' 的大量空值，并确认它是否应为必填字段")
            elif null_pct > 20:
                message = f"列 '{col}' 存在较多空值：{null_pct:.1f}%"
                issues.append(message)
                issue_details.append({"severity": "warning", "code": "null_rate", "column": col, "message": message})

        # ── 完整性分数（非空率均值） ────────────────────────────────
        avg_null_rate = sum(null_rates) / len(null_rates) if null_rates else 0
        completeness_score = 1.0 - avg_null_rate / 100

        # ── 唯一性分数（基于全行去重） ──────────────────────────────
        seen = set()
        duplicate_count = 0
        for row in data:
            key = json.dumps(row, sort_keys=True, default=str)
            if key in seen:
                duplicate_count += 1
            seen.add(key)

        uniqueness_score = 1.0 - duplicate_count / row_count

        if duplicate_count > 0:
            message = f"发现 {duplicate_count} 行重复数据"
            issues.append(message)
            issue_details.append({"severity": "warning", "code": "duplicate_rows", "message": message})
            recommendations.append("配置业务主键并在入库前执行去重，避免仅按整行去重")

        # ── 有效性分数（类型一致性：非 mixed 列占比） ────────────────
        mixed_cols = sum(1 for cq in col_qualities if cq.inferred_type == "mixed")
        validity_score = 1.0 - mixed_cols / column_count if column_count else 1.0
        if mixed_cols:
            for cq in col_qualities:
                if cq.inferred_type == "mixed":
                    message = f"列 '{cq.name}' 存在混合数据类型"
                    issues.append(message)
                    issue_details.append({"severity": "error", "code": "mixed_type", "column": cq.name, "message": message})
                    recommendations.append(f"统一字段 '{cq.name}' 的数据类型，并处理无法转换的值")

        # ── 综合分数 ────────────────────────────────────────────────
        overall_score = (completeness_score * 0.4 + uniqueness_score * 0.4 + validity_score * 0.2)

        return QualityReport(
            dataset_id=curated_dataset_id,
            row_count=row_count,
            column_count=column_count,
            completeness_score=completeness_score,
            uniqueness_score=uniqueness_score,
            validity_score=validity_score,
            overall_score=overall_score,
            columns=col_qualities,
            duplicate_count=duplicate_count,
            issues=issues,
            analyzed_rows=row_count,
            coverage_pct=100.0,
            issue_details=issue_details,
            recommendations=list(dict.fromkeys(recommendations)),
        )

    @staticmethod
    def _infer_type(values: list) -> str:
        if not values:
            return "null"
        types = set()
        for v in values[:50]:
            s = str(v).strip()
            try:
                int(s); types.add("integer"); continue
            except ValueError: pass
            try:
                float(s); types.add("float"); continue
            except ValueError: pass
            if s.lower() in ("true", "false"):
                types.add("boolean"); continue
            types.add("string")
        if len(types) == 1:
            return next(iter(types))
        if types <= {"integer", "float"}:
            return "float"
        return "mixed"
