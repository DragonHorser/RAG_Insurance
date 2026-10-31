from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from collections.abc import Sequence

from sqlalchemy import select
from app.rag.models import ParentChunk


class ParentChunkRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def delete_by_product_id(self, product_id: int) -> None:
        await self.session.execute(
            delete(ParentChunk).where(
                ParentChunk.product_id == product_id
            )
        )

    def add_all(self, parent_chunks: list[ParentChunk]) -> None:
        self.session.add_all(parent_chunks)

    async def list_by_ids(self, ids: list[str]) -> list[ParentChunk]:
        result = await self.session.scalars(
            select(ParentChunk).where(ParentChunk.id.in_(ids))
        )
        return result.all()