from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.sse import ServerSentEvent

from app.modules.chat.schemas import ChatRequest
from app.modules.chat_thread.exceptions import ChatThreadNotFoundError
from app.modules.chat_thread.repository import ChatThreadRepository
from app.agents.schemas import InsuranceAgentContext


class ChatService:
    def __init__(self, session: AsyncSession, agent: CompiledStateGraph):
        self.repository = ChatThreadRepository(session)
        self.agent = agent

    async def chat_stream(
        self,
        user_id: int,
        request: ChatRequest,
    ) -> str:
        # 1.校验会话是否属于当前用户
        thread = await self.repository.find_owned(
            request.thread_id,
            user_id,
        )
        if thread is None:
            raise ChatThreadNotFoundError

        # 2.调用Agent
        # 2.1.消息输入
        _input = {"messages": [HumanMessage(content=request.message)]}
        # 2.2.会话ID
        config = {"configurable": {"thread_id": str(request.thread_id)}}
        context = InsuranceAgentContext(user_id=user_id)
        # 2.3.使用v3协议获取异步事件流。
        # 【注意】这里调用的函数是astream_events
        stream = await self.agent.astream_events(
            _input,
            config,
            context=context,
            version="v3",
        )

        # 2.4.只读取消息中的文本增量
        async for message in stream.messages:
            async for text in message.text:
                yield ServerSentEvent(data=text, event="message")
        # 2.5.返回结束标识
        yield ServerSentEvent(data="[DONE]", event="done")
