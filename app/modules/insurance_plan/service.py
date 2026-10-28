from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.insurance_plan.repository import InsurancePlanRepository
from app.modules.insurance_plan.schemas import InsurancePlanCreate


class InsurancePlanService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = InsurancePlanRepository(session)

    async def create_plan(
        self,
        user_id: int,
        data: InsurancePlanCreate,
    ) -> UUID:
        try:
            plan = await self.repository.create(
                user_id=user_id,
                data=data,
            )
            await self.session.commit()
            return plan.id
        except Exception:
            await self.session.rollback()
            raise