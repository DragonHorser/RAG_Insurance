from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from app.modules.product.models import Product

class ProductRepository:
    def __init__(self,session:AsyncSession):
        self.session = session

    async def find_by_category(self,categroy:str | None) -> list[Product]:
        where_clause = [Product.status == 'active']
        if categroy:
            where_clause.append(Product.category == categroy)

        result = await self.session.execute(select(Product)
                                            .where( *where_clause)
                                            .order_by(Product.id.asc()))
        return result.scalars().all()

class ProductRepository1:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_category(
        self,
        category: str | None,
    ) -> list[Product]:
        # 1.组装查询条件
        # 1.1.默认只查询active状态的产品
        conditions = [Product.status == "active"]
        # 1.2.如果有category，则添加category过滤
        if category:
            conditions.append(Product.category == category)

        # 2.查询产品列表
        products = await self.session.scalars(
            select(Product)
            .where(*conditions)
            .order_by(Product.id.asc())
        )
        return list(products.all())

    async def find_limited_by_category(
            self,
            category: str,
            premium_min: Decimal | None,
            limit: int,
    ) -> list[Product]:
        # 构建查询条件, 推荐的产品状态必须是active的，分类也是条件
        conditions = [
            Product.status == "active",
            Product.category == category,
        ]
        # 如果 最低保费 有值，则加入条件，
        if premium_min is not None:
            # 添加条件，产品的最低保费要小于 最低保费
            conditions.append(Product.min_premium < premium_min)
        # 执行查询 得到结果
        products = await self.session.scalars(
            select(Product)
            .where(*conditions)
            .order_by(
                # nullslast: 指定null排在最后，尽量不取空值数据
                # 升序排序时，null默认排在最后
                # 降序排序时，null默认排在最前
                # select * from products order by max_premium nulls first ;
                # select * from products order by max_premium desc nulls last;
                Product.min_premium.asc().nullslast(),
                Product.id.asc(),
            )
            .limit(limit)
        )
        # 返回结果
        return products.all()