"""阴极保护监测接口：台账读数、批次导入、恒电位仪汇总与防腐层检查统计。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.schemas import PageResult
from app.services.cathodic import cathodic_service

router = APIRouter(prefix="/api/cathodic", tags=["阴极保护监测"])


class BatchImportPayload(BaseModel):
    """批次导入入参：批次号 + 现场采集行（保护电位等原始字段）。"""

    batch_no: str = Field(default="", description="批次号，为空时按导入时间生成")
    rows: list[dict] = Field(default_factory=list, description="现场采集的保护电位行")


@router.get("/readings", response_model=PageResult[dict])
def list_readings(
    rectifier: str | None = Query(default=None, description="按恒电位仪编号过滤"),
    electrode: str | None = Query(default=None, description="按参比电极编号过滤"),
    point: str | None = Query(default=None, description="按测点编号检索"),
    conclusion: str | None = Query(default=None, description="按采集结论过滤"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """台账历史条目：按采集时间倒序，存量回填记录与新导入记录同口径展示。"""
    if size > 500:
        raise HTTPException(status_code=400, detail="每页最多 500 条，请缩小分页范围")
    items, total = cathodic_service.list_readings(
        rectifier=rectifier,
        electrode=electrode,
        point=point,
        conclusion=conclusion,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/rectifiers")
def rectifier_overview() -> dict[str, object]:
    """每台恒电位仪最近一次采集结论与防腐层检查情况。"""
    return {"items": cathodic_service.latest_by_rectifier()}


@router.post("/import")
def import_batch(payload: BatchImportPayload) -> dict[str, object]:
    """按批次导入保护电位：逐行校验、失败行带原因返回，通过的行即时入库（部分提交）。

    同一测点同一采集时间重复导入按覆盖处理，不会多出记录。
    """
    if not payload.rows:
        raise HTTPException(status_code=400, detail="导入批次为空，请先粘贴或选择采集数据")
    return cathodic_service.import_batch(payload.batch_no, payload.rows)


@router.get("/coating")
def list_coating() -> dict[str, object]:
    """防腐层检查记录清单。"""
    return {"items": cathodic_service.list_coating()}


@router.get("/coating/stats")
def coating_stats() -> dict[str, object]:
    """防腐层检查统计页：读数条数直接取台账，保证与台账一致。"""
    return cathodic_service.coating_stats()
