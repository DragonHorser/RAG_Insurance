from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.chat_thread.models import ChatThread

class ChatThreadRepository:
    def __init__(self,session : AsyncSession):
        self.session = session

    async def create(self,chat_thread:ChatThread):
        # 把对象数据插入表中。只负责把对象加入当前 Session，事务由 Service 统一管理。
        self.session.add(chat_thread)

    async def list_by_user(self,user_id:int):
        result = await self.session.execute(select(ChatThread)
                                   .where(ChatThread.user_id == user_id)
                                   .order_by(ChatThread.created_at.desc()))
        return result.scalars().all()

    async def find_owned(self,thread_id:UUID,user_id :int):
       result = await self.session.execute(select(ChatThread)
                                           .where(ChatThread.user_id == user_id
                                                  ,ChatThread.id == thread_id))
       return result.scalar_one_or_none()

    async def delete(self,chat_thread:ChatThread)->None:
        await self.session.delete(chat_thread)