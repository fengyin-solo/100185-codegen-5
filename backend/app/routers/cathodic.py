"""阴极保护监测接口：台账查询、保护电位批次导入（逐行校验、部分成功）、
历史条目、防腐层检查与统计页数据。
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import CathodicImportPayload, PageResult
from app.services.cathodic import IMPORT_COLUMNS, CathodicService

router = APIRouter(prefix="/api/cathodic", tags=["阴极保护"])

service = CathodicService()


@router.get("/readings", response_model=PageResult[dict])
def list_readings(
    batch_no: str | None = Query(default=None, description="按批次号检索"),
    rectifier: str | None = Query(default=None, description="恒电位仪编号"),
    electrode: str | None = Query(default=None, description="参比电极编号"),
    point: str | None = Query(default=None, description="测点编号关键字"),
    conclusion: str | None = Query(default=None, description="保护合格、欠保护、过保护"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """采集台账：按批次/恒电位仪/参比电极/测点/结论过滤，按采集时间倒序。"""
    if size > 500:
        size = 500
    items, total = service.list_readings(
        batch_no=batch_no,
        rectifier=rectifier,
        electrode=electrode,
        point=point,
        conclusion=conclusion,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/history")
def list_history(point: str | None = None) -> dict:
    """历史条目：存量采集记录按测点与采集时间回填后的升序清单，附测点汇总。"""
    return {"items": service.list_history(point), "points": service.history_points()}


@router.get("/rectifiers")
def rectifier_ledger() -> dict:
    """恒电位仪台账：每台设备最近一次采集结论与最近一次防腐层检查情况。"""
    return {"items": service.rectifier_ledger()}


@router.get("/coatings")
def list_coatings(rectifier: str | None = None, status: str | None = None) -> dict:
    """防腐层检查记录列表。"""
    return {"items": service.list_coatings(rectifier=rectifier, status=status)}


@router.get("/stats")
def coating_stats() -> dict:
    """防腐层检查统计页：读数台账与防腐层检查联合聚合，条数与台账读数一致。"""
    return service.coating_stats()


@router.get("/master")
def master_data() -> dict:
    """恒电位仪、参比电极档案，供导入下拉与分组校验使用。"""
    return service.master_data()


@router.get("/import/template")
def import_template() -> dict:
    """导入模板列名与有效范围说明，供前端渲染表头和下载模板。"""
    return {
        "columns": IMPORT_COLUMNS,
        "valid_range_v": [-1.20, -0.85],
        "unit": "V（相对 Cu/CuSO4 参比电极），也可填 mV 如 -950",
        "rule": "同测点按采集时间覆盖；同一批次重复导入不会新增记录",
    }


@router.post("/import")
def import_batch(payload: CathodicImportPayload) -> dict:
    """按批次导入保护电位：逐条校验，失败行带原因单独返回，合格行照常入库。"""
    return service.import_batch(payload.rows, payload.batch_no)
