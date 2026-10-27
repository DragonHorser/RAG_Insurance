from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.product.repository import ProductRepository
from app.modules.product.schemas import ProductResponse

from decimal import Decimal
from app.modules.product.models import Product

class ProductService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ProductRepository(session)

    async def list_products1(
        self,
        category: str | None,
    ) -> list[Product]:
        return await self.repository.find_by_category(category)

    async def list_products(self,catrgory:str | None) -> List[Product]:
        result = await self.repository.find_by_category(catrgory)
        return result

    async def list_candidates(
        self,
        categories: list[str],
        premium_min: Decimal | None,
        limit_per_category: int,
    ) -> list[Product]:
        # 定义推荐的产品列表，用于合并各种分类的产品
        candidate_products: list[Product] = []
        # dict.fromKeys：先把list转成dict，key=列表项的值，value为None，利用dict的特点key是不能重复的，达到去重效果
        # 遍历时只要key不要value
        for category in dict.fromkeys(categories):
            # 调用repository条件查询
            products = await self.repository.find_limited_by_category(
                category=category,
                premium_min=premium_min,
                limit=limit_per_category
            )
            # 合并查询的结果到 推荐列表里
            candidate_products.extend(products)
        # 返回结果
        return candidate_products