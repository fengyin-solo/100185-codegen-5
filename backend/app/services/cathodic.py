"""阴极保护监测业务规则：保护电位批次导入、读数有效范围逐条校验、
按测点与采集时间覆盖、恒电位仪最近结论与防腐层检查情况汇总、统计口径对台账。

有效判据采用 GB/T 21448《埋地钢质管道阴极保护技术规范》：管道保护电位（相对
Cu/CuSO4 参比电极，负电位）应在 -1.20V ～ -0.85V 之间；正于 -0.85V 为欠保护，
负于 -1.20V 为过保护。电位单位支持 V 与 mV 两种填法。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

READING_MODULE = "cathodic"
RECTIFIER_MODULE = "cp_rectifier"
ELECTRODE_MODULE = "cp_electrode"
COATING_MODULE = "coating"

# 导入模板列名
COL_POINT = "测点编号"
COL_RECTIFIER = "恒电位仪编号"
COL_ELECTRODE = "参比电极编号"
COL_MEASURED_AT = "采集时间"
COL_VALUE = "保护电位"
COL_OPERATOR = "采集人员"
IMPORT_COLUMNS = [COL_POINT, COL_RECTIFIER, COL_ELECTRODE, COL_MEASURED_AT, COL_VALUE, COL_OPERATOR]

# 列名别名：容忍现场表格里常见的不同写法
COLUMN_ALIASES = {
    "电位": COL_VALUE,
    "保护电位(v)": COL_VALUE,
    "保护电位（v）": COL_VALUE,
    "通电电位": COL_VALUE,
    "电位(v)": COL_VALUE,
    "电位（v）": COL_VALUE,
    "测量时间": COL_MEASURED_AT,
    "采集日期": COL_MEASURED_AT,
    "时间": COL_MEASURED_AT,
    "测试桩": COL_POINT,
    "测点": COL_POINT,
    "恒电位仪": COL_RECTIFIER,
    "整流器": COL_RECTIFIER,
    "参比电极": COL_ELECTRODE,
    "采集人": COL_OPERATOR,
    "操作人员": COL_OPERATOR,
}
REQUIRED_COLUMNS = IMPORT_COLUMNS[:-1]  # 采集人员允许为空

VALID_MIN_V = -1.20  # 比它更负即过保护
VALID_MAX_V = -0.85  # 比它更正即欠保护

CONCLUSION_OK = "保护合格"
CONCLUSION_UNDER = "欠保护"
CONCLUSION_OVER = "过保护"
COATING_PENDING_STATUSES = ["破损待修", "限期整改", "超期未检"]


def classify(value_v: float) -> str:
    """按有效区间给出采集结论。"""
    if value_v < VALID_MIN_V:
        return CONCLUSION_OVER
    if value_v > VALID_MAX_V:
        return CONCLUSION_UNDER
    return CONCLUSION_OK


def parse_potential(raw: Any) -> tuple[float | None, str | None]:
    """把现场填写的保护电位解析成伏特数值；识别单位 V/mV，兼容全角负号。"""
    if raw is None or str(raw).strip() == "":
        return None, "保护电位为空"
    text = str(raw).strip().replace("　", "").replace("－", "-").replace("−", "-")
    unit = "v"
    if "mv" in text.lower():
        unit = "mv"
    number_text = text.lower().replace("mv", "").replace("v", "").strip()
    try:
        value = float(number_text)
    except ValueError:
        return None, f"保护电位「{raw}」不是数值"
    if unit == "mv" or abs(value) >= 50:  # 数值明显按毫伏填写（如 -950）
        value = value / 1000.0
    if value == 0 or value > 0:
        return None, f"保护电位 {value:.3f}V 极性或数值异常（应为负的通电电位）"
    return value, None


def parse_datetime(raw: Any) -> tuple[datetime | None, str | None]:
    """解析采集时间，兼容 2026-09-14 10:20、2026/9/14 10:20、ISO 等写法。"""
    if raw is None or str(raw).strip() == "":
        return None, "采集时间为空"
    text = str(raw).strip().replace("/", "-").replace("T", " ")
    if len(text) == 10:  # 只有日期，补零点
        text = f"{text} 00:00"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt), None
        except ValueError:
            continue
    return None, f"采集时间「{raw}」格式无法识别"


class CathodicService:
    # ---------------- 列表与台账 ----------------

    def list_readings(
        self,
        *,
        batch_no: str | None = None,
        rectifier: str | None = None,
        electrode: str | None = None,
        point: str | None = None,
        conclusion: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = sorted(store.rows(READING_MODULE), key=lambda r: str(r.get("采集时间", "")), reverse=True)
        rows = self._filter(rows, batch_no, rectifier, electrode, point, conclusion)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    @staticmethod
    def _filter(rows, batch_no, rectifier, electrode, point, conclusion):
        if batch_no:
            rows = [r for r in rows if batch_no in str(r.get("批次号", ""))]
        if rectifier:
            rows = [r for r in rows if r.get("恒电位仪编号") == rectifier]
        if electrode:
            rows = [r for r in rows if r.get("参比电极编号") == electrode]
        if point:
            rows = [r for r in rows if point in str(r.get("测点编号", ""))]
        if conclusion:
            rows = [r for r in rows if r.get("采集结论") == conclusion]
        return rows

    def list_history(self, point: str | None = None) -> list[dict[str, Any]]:
        """单测点（或全部测点）按采集时间升序的历史条目，用于回填后的历史曲线式查看。"""
        rows = list(store.rows(READING_MODULE))
        if point:
            rows = [r for r in rows if point in str(r.get("测点编号", ""))]
        return sorted(rows, key=lambda r: (str(r.get("测点编号", "")), str(r.get("采集时间", ""))))

    def history_points(self) -> list[dict[str, Any]]:
        points: dict[str, dict[str, Any]] = {}
        for row in sorted(store.rows(READING_MODULE), key=lambda r: str(r.get("采集时间", ""))):
            point = str(row.get("测点编号", ""))
            item = points.setdefault(point, {
                "测点编号": point,
                "恒电位仪编号": row.get("恒电位仪编号"),
                "参比电极编号": row.get("参比电极编号"),
                "历史条数": 0,
                "首次采集时间": row.get("采集时间"),
                "最近采集时间": row.get("采集时间"),
                "最近结论": row.get("采集结论"),
                "最近电位": row.get("保护电位(V)"),
            })
            item["历史条数"] += 1
            item["最近采集时间"] = row.get("采集时间")
            item["最近结论"] = row.get("采集结论")
            item["最近电位"] = row.get("保护电位(V)")
        return sorted(points.values(), key=lambda x: str(x["测点编号"]))

    def rectifier_ledger(self) -> list[dict[str, Any]]:
        """每台恒电位仪一行：最近一次采集结论 + 最近一次防腐层检查情况。"""
        readings = sorted(store.rows(READING_MODULE), key=lambda r: str(r.get("采集时间", "")))
        coatings = sorted(store.rows(COATING_MODULE), key=lambda r: str(r.get("检查日期", "")))
        latest_reading: dict[str, dict[str, Any]] = {}
        for row in readings:
            latest_reading[str(row.get("恒电位仪编号"))] = row
        latest_coating: dict[str, dict[str, Any]] = {}
        for row in coatings:
            latest_coating[str(row.get("恒电位仪编号"))] = row

        ledger: list[dict[str, Any]] = []
        for device in store.rows(RECTIFIER_MODULE):
            code = str(device.get("恒电位仪编号"))
            reading = latest_reading.get(code)
            coating = latest_coating.get(code)
            ledger.append({
                **device,
                "最近采集时间": reading.get("采集时间") if reading else None,
                "最近保护电位(V)": reading.get("保护电位(V)") if reading else None,
                "最近采集结论": reading.get("采集结论") if reading else "暂无采集",
                "最近检查日期": coating.get("检查日期") if coating else None,
                "防腐层检查结论": coating.get("检查结论") if coating else "未检查",
                "防腐层检查情况": coating.get("检查情况") if coating else "尚无防腐层检查记录",
                "破损点数": coating.get("破损点数") if coating else 0,
                "检查单号": coating.get("检查单号") if coating else None,
            })
        return ledger

    def list_coatings(self, rectifier: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        rows = sorted(store.rows(COATING_MODULE), key=lambda r: str(r.get("检查日期", "")), reverse=True)
        if rectifier:
            rows = [r for r in rows if r.get("恒电位仪编号") == rectifier]
        if status:
            rows = [r for r in rows if r.get("status") == status]
        return rows

    def master_data(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "rectifiers": [dict(r) for r in store.rows(RECTIFIER_MODULE)],
            "electrodes": [dict(r) for r in store.rows(ELECTRODE_MODULE)],
        }

    # ---------------- 批次导入 ----------------

    def import_batch(self, rows: list[dict[str, Any]], batch_no: str | None) -> dict[str, Any]:
        if not rows:
            return self._empty_result(batch_no)
        batch_no = (batch_no or "").strip() or f"B{datetime.now().strftime('%Y%m%d%H%M')}"

        rectifiers = {str(r.get("恒电位仪编号")) for r in store.rows(RECTIFIER_MODULE)}
        electrodes = {str(r.get("参比电极编号")) for r in store.rows(ELECTRODE_MODULE)}

        failures: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        staged: dict[tuple[str, str], dict[str, Any]] = {}  # 同批内重复测点+时间：后写覆盖
        duplicate_in_file = 0

        for line, raw_row in enumerate(rows, start=2):  # 第1行是表头
            row = self._normalize_row(raw_row)
            reason = self._validate_row(row, rectifiers, electrodes)
            if reason:
                failures.append({"行号": line, "原因": "；".join(reason), "原始数据": raw_row})
                continue
            value_v, _ = parse_potential(row.get(COL_VALUE))
            measured_at, _ = parse_datetime(row.get(COL_MEASURED_AT))
            assert value_v is not None and measured_at is not None
            conclusion = classify(value_v)
            if conclusion != CONCLUSION_OK:
                edge = f"负于 {VALID_MIN_V:.2f}V，过保护" if value_v < VALID_MIN_V else f"正于 {VALID_MAX_V:.2f}V，欠保护"
                warnings.append({
                    "行号": line,
                    "测点编号": str(row[COL_POINT]).strip(),
                    "恒电位仪编号": str(row[COL_RECTIFIER]).strip(),
                    "保护电位(V)": f"{value_v:.2f}",
                    "采集结论": conclusion,
                    "原因": f"保护电位 {value_v:.2f}V {edge}，已入库并标记异常",
                })
            point = str(row[COL_POINT]).strip()
            key = (point, measured_at.strftime("%Y-%m-%d %H:%M:%S"))
            if key in staged:
                duplicate_in_file += 1
            staged[key] = {
                "测点编号": point,
                "恒电位仪编号": str(row[COL_RECTIFIER]).strip(),
                "参比电极编号": str(row[COL_ELECTRODE]).strip(),
                "采集时间": measured_at.strftime("%Y-%m-%d %H:%M"),
                "_排序时间": key[1],
                "保护电位(V)": f"{value_v:.2f}",
                "采集结论": conclusion,
                "批次号": batch_no,
                "采集人员": str(row.get(COL_OPERATOR) or "").strip(),
                "status": conclusion,
                "pending": conclusion != CONCLUSION_OK,
                "abnormal": conclusion != CONCLUSION_OK,
            }

        inserted = updated = 0
        existing = store.rows(READING_MODULE)
        index = {
            (str(r.get("测点编号", "")), str(r.get("采集时间", ""))): r
            for r in existing
        }
        # 台账里同键只可能有一条；旧写法（秒级时间）也参与匹配
        for (point, measured_key), entry in staged.items():
            old = index.get((point, entry["采集时间"]))
            if old is None:  # 兼容秒级写法
                for candidate in existing:
                    if str(candidate.get("测点编号")) == point and str(candidate.get("采集时间", "")).startswith(entry["采集时间"]):
                        old = candidate
                        break
            if old is None:
                entry["id"] = max((int(r.get("id", 0)) for r in existing), default=0) + 1
                existing.append(entry)
                index[(point, entry["采集时间"])] = entry
                inserted += 1
            else:
                old_id = old.get("id")
                old.clear()
                old.update(entry)
                old["id"] = old_id
                updated += 1

        return {
            "批次号": batch_no,
            "总行数": len(rows),
            "通过行数": len(staged),
            "失败行数": len(failures),
            "异常入库行数": len(warnings),
            "新增条数": inserted,
            "覆盖条数": updated,
            "批内重复条数": duplicate_in_file,
            "失败明细": failures,
            "异常明细": warnings,
            "分组统计": self._group_stats(list(staged.values())),
            "台账总条数": len(existing),
        }

    @staticmethod
    def _normalize_row(raw: dict[str, Any]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in raw.items():
            name = str(key).strip()
            name = COLUMN_ALIASES.get(name.lower(), COLUMN_ALIASES.get(name, name))
            # 兜底：现场表头常带单位括号（如 电位(mV)、保护电位（V）），只要含“电位”就并入保护电位列
            if name not in IMPORT_COLUMNS and "电位" in name and COL_VALUE not in normalized:
                name = COL_VALUE
            normalized[name] = "" if value is None else str(value).strip()
        return normalized

    @staticmethod
    def _validate_row(row: dict[str, str], rectifiers: set[str], electrodes: set[str]) -> list[str]:
        reasons: list[str] = []
        for column in REQUIRED_COLUMNS:
            if not row.get(column):
                reasons.append(f"{column}为空")
        if reasons:
            return reasons  # 后续解析没有意义，先让现场补齐必填项

        code = str(row[COL_RECTIFIER]).strip()
        if code not in rectifiers:
            reasons.append(f"恒电位仪「{code}」未在台账登记")
        electrode = str(row[COL_ELECTRODE]).strip()
        if electrode not in electrodes:
            reasons.append(f"参比电极「{electrode}」未在台账登记")

        _, dt_reason = parse_datetime(row.get(COL_MEASURED_AT))
        if dt_reason:
            reasons.append(dt_reason)

        value_v, value_reason = parse_potential(row.get(COL_VALUE))
        if value_reason:
            reasons.append(value_reason)
            return reasons
        # 读数超出有效区间属于业务异常（欠/过保护），仍应入库并在采集结论里标出，
        # 不作为失败行拦截；这里只做格式与引用合法性校验。
        return reasons

    @staticmethod
    def _group_stats(staged: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按恒电位仪 × 参比电极分组的本批校验结果。"""
        groups: dict[tuple[str, str], dict[str, Any]] = {}
        for entry in staged:
            key = (str(entry["恒电位仪编号"]), str(entry["参比电极编号"]))
            item = groups.setdefault(key, {
                "恒电位仪编号": key[0],
                "参比电极编号": key[1],
                "通过条数": 0,
                "合格条数": 0,
                "欠保护条数": 0,
                "过保护条数": 0,
            })
            item["通过条数"] += 1
            if entry["采集结论"] == CONCLUSION_OK:
                item["合格条数"] += 1
            elif entry["采集结论"] == CONCLUSION_UNDER:
                item["欠保护条数"] += 1
            else:
                item["过保护条数"] += 1
        return [groups[key] for key in sorted(groups)]

    @staticmethod
    def _empty_result(batch_no: str | None) -> dict[str, Any]:
        return {
            "批次号": batch_no or "",
            "总行数": 0,
            "通过行数": 0,
            "失败行数": 0,
            "异常入库行数": 0,
            "新增条数": 0,
            "覆盖条数": 0,
            "批内重复条数": 0,
            "失败明细": [],
            "异常明细": [],
            "分组统计": [],
            "台账总条数": len(store.rows(READING_MODULE)),
        }

    # ---------------- 统计（汇进防腐层检查统计页） ----------------

    def coating_stats(self) -> dict[str, Any]:
        """统计直接由读数台账与防腐层检查记录聚合，台账读数条数即统计基数，保证两处一致。"""
        rows = store.rows(READING_MODULE)
        coatings = store.rows(COATING_MODULE)
        total = len(rows)
        ok = sum(1 for r in rows if r.get("采集结论") == CONCLUSION_OK)
        under = sum(1 for r in rows if r.get("采集结论") == CONCLUSION_UNDER)
        over = sum(1 for r in rows if r.get("采集结论") == CONCLUSION_OVER)

        per_device: dict[str, dict[str, Any]] = {}
        for code in sorted({str(r.get("恒电位仪编号")) for r in store.rows(RECTIFIER_MODULE)}):
            per_device[code] = {
                "恒电位仪编号": code,
                "台账读数条数": 0,
                "合格条数": 0,
                "欠保护条数": 0,
                "过保护条数": 0,
                "合格率": "—",
                "防腐层检查次数": 0,
                "破损点数合计": 0,
                "待整改检查数": 0,
            }
        for row in rows:
            item = per_device.setdefault(str(row.get("恒电位仪编号")), {
                "恒电位仪编号": row.get("恒电位仪编号"),
                "台账读数条数": 0, "合格条数": 0, "欠保护条数": 0, "过保护条数": 0,
                "合格率": "—", "防腐层检查次数": 0, "破损点数合计": 0, "待整改检查数": 0,
            })
            item["台账读数条数"] += 1
            if row.get("采集结论") == CONCLUSION_OK:
                item["合格条数"] += 1
            elif row.get("采集结论") == CONCLUSION_UNDER:
                item["欠保护条数"] += 1
            else:
                item["过保护条数"] += 1
        for item in per_device.values():
            if item["台账读数条数"]:
                rate = item["合格条数"] / item["台账读数条数"] * 100
                item["合格率"] = f"{rate:.1f}%"
        for coating in coatings:
            item = per_device.setdefault(str(coating.get("恒电位仪编号")), {
                "恒电位仪编号": coating.get("恒电位仪编号"),
                "台账读数条数": 0, "合格条数": 0, "欠保护条数": 0, "过保护条数": 0,
                "合格率": "—", "防腐层检查次数": 0, "破损点数合计": 0, "待整改检查数": 0,
            })
            item["防腐层检查次数"] += 1
            item["破损点数合计"] += int(coating.get("破损点数") or 0)
            if coating.get("status") in COATING_PENDING_STATUSES:
                item["待整改检查数"] += 1

        devices = sorted(per_device.values(), key=lambda x: str(x["恒电位仪编号"]))
        coating_total = len(coatings)
        coating_pending = sum(1 for c in coatings if c.get("status") in COATING_PENDING_STATUSES)
        return {
            "读数统计": {
                "台账读数条数": total,
                "合格条数": ok,
                "欠保护条数": under,
                "过保护条数": over,
                "合格率": f"{ok / total * 100:.1f}%" if total else "—",
            },
            "防腐层检查统计": {
                "检查记录数": coating_total,
                "待整改数": coating_pending,
                "破损点数合计": sum(int(c.get("破损点数") or 0) for c in coatings),
            },
            "分恒电位仪统计": devices,
            "对账说明": f"统计口径与采集台账同源：分组合计 {sum(d['台账读数条数'] for d in devices)} 条 = 台账读数 {total} 条",
        }
