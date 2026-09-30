"""阴极保护监测业务规则。

台账存两类数据：
- ``cp_reading``：现场按批次采集的保护电位读数（含存量回填的历史条目）；
- ``cp_coating``：恒电位仪管段的防腐层检查记录。

导入口径：
- 一个批次按「恒电位仪 + 参比电极」分组逐行校验；
- 只有校验通过的行才写入，不通过的行带原因单独返回，已通过的部分照常保留（部分提交）；
- 同一测点同一采集时间的读数按 upsert 覆盖，重复导入同一批不会堆积记录。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

READING_MODULE = "cp_reading"
COATING_MODULE = "cp_coating"

REQUIRED_FIELDS = ["测点编号", "恒电位仪编号", "参比电极编号", "采集时间", "保护电位(V)"]

# 相对于饱和硫酸铜参比电极（CSE）的有效保护电位区间（GB/T 21448 常用判据）。
POTENTIAL_MIN = -1.20
POTENTIAL_MAX = -0.85

CONCLUSION_OK = "保护达标"
CONCLUSION_UNDER = "欠保护（电位正于-0.85V）"
CONCLUSION_OVER = "过保护（电位负于-1.20V）"

LEGACY_BATCH = "存量回填"


def _parse_time(value: Any) -> datetime | None:
    """兼容 ``2026-09-01 10:00`` / ``2026-09-01T10:00`` / 仅日期三种写法。"""
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _parse_potential(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _conclusion_for(potential: float) -> str:
    if potential > POTENTIAL_MAX:
        return CONCLUSION_UNDER
    if potential < POTENTIAL_MIN:
        return CONCLUSION_OVER
    return CONCLUSION_OK


class CathodicService:
    # ---------- 台账读数 ----------
    def list_readings(
        self,
        *,
        rectifier: str | None = None,
        electrode: str | None = None,
        point: str | None = None,
        conclusion: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """历史条目按采集时间倒序回填展示，最新采集排在最前。"""
        rows = list(store.rows(READING_MODULE))
        if rectifier:
            rows = [r for r in rows if rectifier in str(r.get("恒电位仪编号", ""))]
        if electrode:
            rows = [r for r in rows if electrode in str(r.get("参比电极编号", ""))]
        if point:
            rows = [r for r in rows if point in str(r.get("测点编号", ""))]
        if conclusion:
            rows = [r for r in rows if r.get("采集结论") == conclusion]
        rows.sort(key=lambda r: str(r.get("采集时间", "")), reverse=True)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def latest_by_rectifier(self) -> list[dict[str, Any]]:
        """每台恒电位仪最近一次采集结论，并拼上最近一次防腐层检查情况。"""
        latest_point: dict[tuple[str, str], dict[str, Any]] = {}
        for row in store.rows(READING_MODULE):
            key = (str(row.get("恒电位仪编号", "")), str(row.get("测点编号", "")))
            current = latest_point.get(key)
            if current is None or str(row.get("采集时间", "")) > str(current.get("采集时间", "")):
                latest_point[key] = row

        latest_coating: dict[str, dict[str, Any]] = {}
        for coating in store.rows(COATING_MODULE):
            rectifier = str(coating.get("恒电位仪编号", ""))
            current = latest_coating.get(rectifier)
            if current is None or str(coating.get("检查日期", "")) > str(current.get("检查日期", "")):
                latest_coating[rectifier] = coating

        result: dict[str, dict[str, Any]] = {}
        for (rectifier, _point), row in latest_point.items():
            item = result.setdefault(rectifier, {
                "恒电位仪编号": rectifier,
                "最近采集时间": "",
                "达标点位数": 0,
                "异常点位数": 0,
                "点位数": 0,
                "机组结论": CONCLUSION_OK,
                "防腐层检查日期": "—",
                "防腐层状况等级": "—",
                "防腐层破损处数": "—",
                "防腐层检查意见": "—",
            })
            if str(row.get("采集时间", "")) > item["最近采集时间"]:
                item["最近采集时间"] = row.get("采集时间")
            item["点位数"] += 1
            if row.get("采集结论") == CONCLUSION_OK:
                item["达标点位数"] += 1
            else:
                item["异常点位数"] += 1

        for rectifier, item in result.items():
            item["机组结论"] = CONCLUSION_OK if item["异常点位数"] == 0 else "存在异常测点"
            coating = latest_coating.get(rectifier)
            if coating:
                item["防腐层检查日期"] = coating.get("检查日期", "—")
                item["防腐层状况等级"] = coating.get("防腐层状况等级", "—")
                item["防腐层破损处数"] = coating.get("破损处数", "—")
                item["防腐层检查意见"] = coating.get("检查意见", "—")
        return sorted(result.values(), key=lambda item: item["恒电位仪编号"])

    # ---------- 批次导入 ----------
    def import_batch(
        self,
        batch_no: str,
        raw_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """按批次导入保护电位。

        返回 ``inserted / updated / failed`` 三类计数；失败行带行号、分组与原因，
        且不影响同批其它行入库。重复导入同一批时命中唯一键的行走覆盖，条数不增加。
        """
        batch_no = batch_no.strip() or f"批次-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        imported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        inserted = 0
        updated = 0
        groups: dict[str, int] = {}
        failed_rows: list[dict[str, Any]] = []

        for index, raw in enumerate(raw_rows, start=1):
            rectifier = str(raw.get("恒电位仪编号") or "").strip()
            electrode = str(raw.get("参比电极编号") or "").strip()
            point = str(raw.get("测点编号") or "").strip()
            time_text = str(raw.get("采集时间") or "").strip()
            potential_text = raw.get("保护电位(V)")

            reasons: list[str] = []
            for label, value in (
                ("测点编号", point),
                ("恒电位仪编号", rectifier),
                ("参比电极编号", electrode),
                ("采集时间", time_text),
                ("保护电位(V)", "" if potential_text is None else str(potential_text).strip()),
            ):
                if not value:
                    reasons.append(f"缺少必填字段「{label}」")
            collected_at = _parse_time(time_text)
            if time_text and collected_at is None:
                reasons.append(f"采集时间「{time_text}」格式无法识别，应为 YYYY-MM-DD HH:MM")
            potential = _parse_potential(potential_text) if potential_text not in (None, "") else None
            if potential_text not in (None, "") and potential is None:
                reasons.append(f"保护电位「{potential_text}」不是数值")
            elif potential is not None and not (POTENTIAL_MIN <= potential <= POTENTIAL_MAX):
                reasons.append(
                    f"保护电位 {potential:.3f}V 超出有效范围 [{POTENTIAL_MIN}, {POTENTIAL_MAX}]（CSE）"
                )

            if reasons:
                failed_rows.append({
                    "行号": index,
                    "测点编号": point or "—",
                    "恒电位仪编号": rectifier or "—",
                    "参比电极编号": electrode or "—",
                    "采集时间": time_text or "—",
                    "保护电位(V)": potential_text if potential_text not in (None, "") else "—",
                    "原因": "；".join(reasons),
                })
                continue

            group_key = f"{rectifier} / {electrode}"
            groups[group_key] = groups.get(group_key, 0) + 1

            reading = self._upsert_reading({
                "测点编号": point,
                "恒电位仪编号": rectifier,
                "参比电极编号": electrode,
                "采集时间": collected_at.strftime("%Y-%m-%d %H:%M:%S") if collected_at else time_text,
                "保护电位(V)": round(potential, 3),
                "采集结论": _conclusion_for(potential),
                "批次号": batch_no,
                "导入时间": imported_at,
            })
            if reading.pop("_changed") == "inserted":
                inserted += 1
            else:
                updated += 1

        return {
            "批次号": batch_no,
            "总行数": len(raw_rows),
            "导入成功": inserted + updated,
            "新增": inserted,
            "覆盖": updated,
            "失败": len(failed_rows),
            "分组数": len(groups),
            "分组明细": [{"分组": key, "行数": count} for key, count in sorted(groups.items())],
            "失败行": failed_rows,
        }

    def _upsert_reading(self, values: dict[str, Any]) -> dict[str, Any]:
        """按（测点编号, 采集时间）覆盖；同一测点同一时刻只保留一条。"""
        rows = store.rows(READING_MODULE)
        for row in rows:
            if row.get("测点编号") == values["测点编号"] and row.get("采集时间") == values["采集时间"]:
                row.update(values)
                row["_changed"] = "updated"
                return row
        entry = {"id": max((int(r.get("id", 0)) for r in rows), default=0) + 1}
        entry.update(values)
        entry["_changed"] = "inserted"
        rows.append(entry)
        return entry

    # ---------- 防腐层检查 ----------
    def list_coating(self) -> list[dict[str, Any]]:
        rows = sorted(store.rows(COATING_MODULE), key=lambda r: str(r.get("检查日期", "")), reverse=True)
        return rows

    def coating_stats(self) -> dict[str, Any]:
        """防腐层检查统计页。

        读数口径直接取自台账 ``cp_reading``：按恒电位仪汇总的台账读数条数与统计页
        「台账读数条数」完全一致，避免导入结果汇进统计后两边对不上。
        """
        readings = store.rows(READING_MODULE)
        coatings = self.list_coating()

        per_rectifier: dict[str, dict[str, Any]] = {}
        for row in readings:
            rectifier = str(row.get("恒电位仪编号", ""))
            item = per_rectifier.setdefault(rectifier, {
                "恒电位仪编号": rectifier,
                "台账读数条数": 0,
                "达标条数": 0,
                "欠保护条数": 0,
                "过保护条数": 0,
                "防腐层检查次数": 0,
                "防腐层破损处数合计": 0,
                "最近防腐层等级": "—",
            })
            item["台账读数条数"] += 1
            conclusion = row.get("采集结论")
            if conclusion == CONCLUSION_OK:
                item["达标条数"] += 1
            elif conclusion == CONCLUSION_UNDER:
                item["欠保护条数"] += 1
            elif conclusion == CONCLUSION_OVER:
                item["过保护条数"] += 1

        latest_coating: dict[str, dict[str, Any]] = {}
        for coating in coatings:
            rectifier = str(coating.get("恒电位仪编号", ""))
            current = latest_coating.get(rectifier)
            if current is None or str(coating.get("检查日期", "")) > str(current.get("检查日期", "")):
                latest_coating[rectifier] = coating

        for coating in coatings:
            rectifier = str(coating.get("恒电位仪编号", ""))
            item = per_rectifier.setdefault(rectifier, {
                "恒电位仪编号": rectifier,
                "台账读数条数": 0,
                "达标条数": 0,
                "欠保护条数": 0,
                "过保护条数": 0,
                "防腐层检查次数": 0,
                "防腐层破损处数合计": 0,
                "最近防腐层等级": "—",
            })
            item["防腐层检查次数"] += 1
            try:
                item["防腐层破损处数合计"] += int(coating.get("破损处数", 0) or 0)
            except (TypeError, ValueError):
                pass

        for rectifier, item in per_rectifier.items():
            coating = latest_coating.get(rectifier)
            if coating:
                item["最近防腐层等级"] = coating.get("防腐层状况等级", "—")

        grade_dist: dict[str, int] = {}
        for coating in coatings:
            grade = str(coating.get("防腐层状况等级", "未评"))
            grade_dist[grade] = grade_dist.get(grade, 0) + 1

        items = sorted(per_rectifier.values(), key=lambda item: item["恒电位仪编号"])
        return {
            "汇总": {
                "台账读数总条数": len(readings),
                "达标条数": sum(i["达标条数"] for i in items),
                "欠保护条数": sum(i["欠保护条数"] for i in items),
                "过保护条数": sum(i["过保护条数"] for i in items),
                "防腐层检查次数": len(coatings),
                "防腐层破损处数合计": sum(i["防腐层破损处数合计"] for i in items),
                "恒电位仪台数": len({r.get("恒电位仪编号") for r in readings} | {c.get("恒电位仪编号") for c in coatings}),
            },
            "等级分布": [{"防腐层状况等级": grade, "次数": count} for grade, count in sorted(grade_dist.items())],
            "分组统计": items,
            "防腐层检查记录": coatings,
        }


cathodic_service = CathodicService()
