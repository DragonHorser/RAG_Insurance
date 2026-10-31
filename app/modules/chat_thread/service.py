from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage
from app.modules.chat_thread.schemas import (
    ChatHistoryResponse,
    ChatMessageResponse,
)

from app.modules.chat_thread.models import ChatThread
from app.modules.chat_thread.repository import ChatThreadRepository
from app.modules.chat_thread.exceptions import ChatThreadNotFoundError

class ChatThreadService:
    def __init__(self,session:AsyncSession,agent: CompiledStateGraph):
        self.session = session
        self.repository = ChatThreadRepository(session)
        self.agent = agent

    async def create_chat_thread(self,user_id:int,title:str):
        # 用上下文管理，开启事务，运行完成，自动commit，出现异常，自动rollback
        async with self.session.begin():
            # 创建会话对象，封装要插入的数据,其中id自动由await self.repository.create(chat_thread)生成
            chat_thread = ChatThread(user_id =user_id ,title = title)
            # 调用repository的add方法，将数据插入数据库
            await self.repository.create(chat_thread)
            # 返回新创建的会话对象 供router层的实例对象使用
            return chat_thread

    async def list_by_user(self, user_id):
        return await self.repository.list_by_user(user_id)

    async def rename_chat_thread(self,thread_id:UUID,user_id:int,title:str):
        async with self.session.begin():
            # 1. 根据用户id和会话id，查询会话
            chat_thread = await self.repository.find_owned(thread_id,user_id)
            if chat_thread is None:
                # 为None，说明不存在，或者不属于当前用户，抛出异常
                # raise: 就是指扔出去一个异常，代码会立刻终止，结束运行，把异常扔给调用者
                raise ChatThreadNotFoundError
            # 2. 修改它的标题
            chat_thread.title = title
            # 3. 立即执行update语句 脏跟踪更新数据
            await self.session.flush()
            # 4. 重新加载最新会话数据
            await self.session.refresh(chat_thread) #最新数据重新加载
        return chat_thread

    async def delete_chat_thread(self,thread_id:UUID,user_id:int):
        async with self.session.begin():
            # 1.校验会话归属
            thread_id = await self.repository.find_owned(thread_id,user_id)
            if thread_id is None:
                raise ChatThreadNotFoundError
            await self.repository.delete(thread_id)
            # 2.+a 异步删除Checkpointer中的会话状态 返回字符串类型
            await self.agent.checkpointer.adelete_thread(str(thread_id))
            # 3.删除会话元数据
            await self.repository.delete(thread_id)

    async def get_history(
            self,
            thread_id: UUID,
            user_id: int,
    ) -> ChatHistoryResponse:
        """
        service层获取某单个会话历史
        :param thread_id: 前端请求会话id
        :param user_id: 数据库中用于校验的id
        :return: schemas响应类按前端要求格式返回数据
        """
        # 1.校验会话归属 防止越权 :根据前端送来的会话id与数据库存在的会话id做比较，
        # 若等则返回一个会话对象，
        chat_thread = await self.repository.find_owned(thread_id, user_id)
        if chat_thread is None:
            raise ChatThreadNotFoundError

        # 2.读取Agent最新状态,查询聊天记录
        config = {"configurable": {"thread_id": str(thread_id)}}
        #聊天记录的快照
        snapshot = await self.agent.aget_state(config)

        # 3.只保留用户消息和AI消息
        messages = []
        #在聊天记录的快照中获取名为messages的值即为聊天记录，若没有记录则赋给一个空列表
        message_list = snapshot.values.get("messages",[])
        for message in message_list:
            #isinstance : 判断参数一是否是参数二的实例化对象
            if isinstance(message, HumanMessage):
                role = "user"
            elif isinstance(message, AIMessage):
                role = "assistant"
            #其他的任何消息直接跳过不要获取下一条消息continue
            else:
                continue

            if message.text:
                messages.append(ChatMessageResponse(role=role, content=message.text))

        return ChatHistoryResponse(thread_id=thread_id, messages=messages)
