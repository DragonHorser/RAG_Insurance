from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.insurance_plan.models import (
    InsurancePlan,
    InsurancePlanItem,
)
from app.modules.insurance_plan.schemas import InsurancePlanCreate


class InsurancePlanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        data: InsurancePlanCreate,
    ) -> InsurancePlan:
        # 1.计算方案年缴总预算，获取每个保险项目的金额
        item_budgets = [
            item.annual_premium_budget
            for item in data.items
            if item.annual_premium_budget is not None
        ]
        # 对每个保险项金额求合得到总金额
        annual_premium_budget = (
            sum(item_budgets, Decimal("0"))
            if item_budgets
            else None
        )

        # 2.保存保险方案
        plan = InsurancePlan(
            user_id=user_id,
            plan_name=data.plan_name,
            summary=data.summary,
            insured_profile=data.insured_profile,
            annual_premium_budget=annual_premium_budget,
        )
        self.session.add(plan)
        await self.session.flush()

        # 3.保存方案项
        plan_items = [
            InsurancePlanItem(
                plan_id=plan.id,
                product_id=item.product_id,
                priority=item.priority,
                recommendation_reason=item.recommendation_reason,
                annual_premium_budget=item.annual_premium_budget,
            )
            for item in data.items
        ]
        self.session.add_all(plan_items)
        return plan