from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.infra.database import get_session
from app.modules.product.schemas import ProductResponse
from app.modules.product.service import ProductService
from decimal import Decimal
from typing import Annotated

router = APIRouter(prefix="/api/v1/products", tags=["products"])

logger = get_logger(__name__)

#后续每个方法都需要用到session直接封装提取出来，使用时当成参数依赖注入即可
async def get_product_service(
    session: AsyncSession = Depends(get_session),
) -> ProductService:
    return ProductService(session)

@router.get("1", response_model=list[ProductResponse])
async def list_products1(
    category: str | None = None,
    service: ProductService = Depends(get_product_service),
    # 1.获取Service
) -> list[ProductResponse]:
    logger.info("开始查询产品列表")
    # 2.查询并返回产品列表
    return await service.list_products(category)

@router.get("",response_model=list[ProductResponse])
async def list_products(category : str | None = None,service : ProductService = Depends(get_product_service) )-> list[ProductResponse]:
    return await service.list_products(category)

@router.get("/candidates", response_model=list[ProductResponse])
async def list_candidates(
    # Query的意思是将 categories 声明为 URL 查询参数（例如 ?categories=xxx&categories=yyy）。
    # min_length=1 的作用是限制该列表至少包含 1 个元素，确保客户端请求时至少传入一个产品类别
    # 当请求过来时，FastAPI会进行校验，如果校验不通过则报返回http 422状态码 错误
    categories: list[str] = Query(min_length=1),
    premium_min: Decimal | None = None,
    limit_per_category: int = 5,
    service: ProductService = Depends(get_product_service),
) -> list[ProductResponse]:
    return await service.list_candidates(
        categories=categories,
        premium_min=premium_min,
        limit_per_category=limit_per_category,
    )