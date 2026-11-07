from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.sse import ServerSentEvent
from aiostream import stream as astream
from langgraph.stream import CustomTransformer
from app.modules.chat.schemas import ChatRequest
from app.modules.chat_thread.exceptions import ChatThreadNotFoundError
from app.modules.chat_thread.repository import ChatThreadRepository
from app.agents.schemas import InsuranceAgentContext
from langchain_core.messages import AIMessage
from langgraph.types import Command


class ChatService:
    def __init__(self, session: AsyncSession, agent: CompiledStateGraph):
        self.repository = ChatThreadRepository(session)
        self.agent = agent

    async def chat_stream(self,user_id: int,request: ChatRequest,
    ) -> str:
        # 1.防止越权:校验会话是否属于当前用户
        chat_thread = await self.repository.find_owned(request.thread_id,user_id,)
        if chat_thread is None:
            raise ChatThreadNotFoundError

        # 2.找到于会话id相同的用户后 :调用Agent
        # 2.1.准备Agent输入
        if request.decision:
            _input = Command(resume=request.decision)
        else:
            _input = {"messages": [HumanMessage(content=request.message)]}
        # # 2.1.消息输入
        # _input = {"messages": [HumanMessage(content=request.message)]}
        # 2.2.定义会话ID(判断会话所属哪个用户)  request里的会话id默认为UUID格式，转为str后可被解析
        config = {"configurable": {"thread_id": str(request.thread_id)}}
        context = InsuranceAgentContext(user_id=user_id)

        #阻塞式输出,体验拉跨，废弃掉
        #response = await self.agent.ainvoke(
        #    input = {"messages":[HumanMessage(content = request.message)]},
        #    config = config
        #)
        #return response["messagaes"][-1].content

        # 2.3.使用v3协议获取异步事件流。
        # 【注意】这里调用的函数是astream_events
        stream = await self.agent.astream_events(
            input = _input,
            config = config,
            #todo:context = {"user_id": user_id}
            context=context,
            version="v3",
            transformers=[CustomTransformer],
        )
        # 2.3.1.记录AIMessage的ID和引用信息
        final_message_id: str | None = None
        additional_info: AdditionalInfo = {}

        #自定义stream处理
        async for event in stream:
            method = event['method']
            # 判断事件类型，可以是messages、interrupts等等
            if method == 'messages':
                data = event['params']['data'][0]
                if isinstance(data, AIMessage):
                    yield ServerSentEvent(data=data.text, event="message")
                elif data.get('delta') and data['delta'].get('text'):
                    yield ServerSentEvent(data=data['delta'].get('text'), event="message")
                elif data.get('event') == 'message-start' and data.get('id'):
                    # 第一个消息片段会传递Message的id
                    final_message_id = data.get('id')
            if method == 'custom':
                data = event["params"]["data"]
                if isinstance(data, dict) and data.get("type") == "additional_info":
                    additional_info = data.get("data", {})
                    yield ServerSentEvent(data=additional_info, event="additional_info")

        interrupts = await stream.interrupts()
        for item in interrupts:
            yield ServerSentEvent(data=item.value, event="interrupt")

        if final_message_id and additional_info:
            # 将additional_info更新到state中
            await self.agent.aupdate_state(
                config,
                {"additional_info": {final_message_id: additional_info}}
            )
        # 2.4.只读取消息中的文本增量
        async def stream_messages():
            async for message in stream.messages:
                async for text in message.text:
                    #封装text为ServerSentEvent对象,包含信息event = "message"
                    yield ServerSentEvent(data=text, event="message")

        # 2.5.判断是否有custom事件
        async def stream_custom():
            async for event in stream.extensions['custom']:
                if event.get('type') == 'additional_info':
                    yield ServerSentEvent(data=event.get('data'), event="additional_info")

        # 2.6.合并Message处理和custom事件处理
        merged = astream.merge(stream_messages(), stream_custom())
        async with merged.stream() as streamer:
            async for event in streamer:
                yield event

        # x2.4x.只读取消息中的文本增量
        # async for message in stream.messages:
        #     async for text in message.text:
        #         #把输出的text封装成ServerSentEvent结构化输出
        #         yield ServerSentEvent(data=text, event="message")

        # 2.7.返回结束标识
        yield ServerSentEvent(data="[DONE]", event="done")


