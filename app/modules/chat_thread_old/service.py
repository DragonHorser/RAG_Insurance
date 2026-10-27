from sqlalchemy.ext.asyncio import AsyncSession

from .repository import ChatThreadRepository
from .models import ChatThread
from uuid import UUID

from app.modules.chat_thread_old.exceptions import ChatThreadNotFoundError

class ChatThreadService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ChatThreadRepository(session)

    async def add(self, user_id: int , title: str):
        # 用上下文管理，开启事务，运行完成，自动commit，出现异常，自动rollback
        async with self.session.begin():
            # 创建会话对象，封装要插入的数据
            chat_thread = ChatThread(user_id = user_id, title = title)
            # 调用repository的add方法，将数据插入数据库
            await self.repository.add(chat_thread)
            # 返回新创建的会话对象
            return chat_thread

    async def list_by_user(self, user_id: int) -> list[ChatThread]:
        return await self.repository.list_by_user(user_id)

    async def rename(self, thread_id: UUID, user_id: int, title: str) -> ChatThread:
        async with self.session.begin():
            # 1.根据thread_id和user_id查询会话信息
            thread = await self.repository.find_owned(thread_id, user_id)
            if thread is None:
                # 为None，说明不存在，或者不属于当前用户，抛出异常
                # raise: 就是指扔出去一个异常，代码会立刻终止，结束运行，把异常扔给调用者
                raise ChatThreadNotFoundError
            # 2.查询后直接修改字段，会触发ORM框架对数据库做更新，执行update语句
            thread.title = title

            # 3. 马上执行sql语句
            await self.session.flush()
            # 4. 重刷新同步内存中的对象与数据库表中的记录，达到数据一致
            await self.session.refresh(thread)

        return thread

    async def delete(self, thread_id: UUID, user_id: int) -> None:
        async with self.session.begin():
            thread = await self.repository.find_owned(thread_id, user_id)
            if thread is None:
                raise ChatThreadNotFoundError

            await self.repository.delete(thread)