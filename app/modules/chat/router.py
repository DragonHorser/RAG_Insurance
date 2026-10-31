from typing import Annotated

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.sse import EventSourceResponse, ServerSentEvent #模拟sse返回数据
from fastapi import APIRouter, Depends, Request, Header
from app.infra.database import get_session
from .schemas import ChatRequest
from .service import ChatService

router = APIRouter(prefix="/api/v1/chat", tags=["与AI对话接口"])
# 依赖注入，自动注入Request
def get_chat_service(
    # 执行中, FastAPI 自动把当前请求的 Request 对象传给request 是starlette的Request
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    # 1.创建ChatService
    agent = request.app.state.agent
    return ChatService(session, agent)

@router.post("test",response_class=EventSourceResponse)
async def chat(
    request: ChatRequest,
    user_id: Annotated[int, Header(alias="x-user-id")],
    service: ChatService=Depends(get_chat_service)
):
    # SSE流式输出: Generator, 用yield不断生成内容，形成动态列表
    async for sse in service.chat_stream(user_id, request):
        yield sse
    # # 1.调用
    # response = await service.chat_stream(user_id, request)
    # # 2.返回
    # return response

@router.post("",response_class=EventSourceResponse)
#参数中user_id用于用户越权校检 ,request用于接受固定格式的客户前端请求，service用于连接业务层方法代码
async def chat(user_id:Annotated[int,Header(alias="x-user-id")],
               request : ChatRequest,
               service : ChatService = Depends(get_chat_service)):
    #return await service.chat_stream(user_id,request.thread_id,request.message)
    # 测试流式输出
    # for i in range(100):
    #     yield ServerSentEvent(data = str(i),event="message")
    # yield ServerSentEvent(data="[DONE]",event='done')
    async for see in service.chat_stream(user_id, request):
        yield see