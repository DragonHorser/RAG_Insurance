from typing import Annotated
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.params import Header
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.chat_thread.schemas import ChatHistoryResponse

from app.infra.database import get_session
from app.modules.chat_thread.schemas import ChatThreadCreate,ChatThreadResponse
from app.modules.chat_thread.service import ChatThreadService

router = APIRouter(prefix="/api/v1/chat-threads",tags=["会话管理"])

# 知识补充：
# Annotated 是 Python 标准库 typing 提供的类型工具，它的核心作用给类型附加额外的元数据
# Annotated[T, metadata] 表示一个类型 T，同时携带一段元数据 metadata。
# 如：x: Annotated[int, "这是一个整数"]。这里的 "这是一个整数" 不会影响类型本身，只是附加说明。FastAPI 正是利用这个机制，把 Header、Query、Path、Body 等作为元数据嵌入到参数类型中。
# Header: 声明请求头中数据
# Query: 声明query中的数据
# Path: 声明请求路径中的数据
# Body: 声明请求体中的数据
# 这句话的意思：声明请求头要有个x-user-id的key,接收请求时，把请求头中的这个key对应的值赋值给user_id参数
User_id = Annotated[int,Header(alias = "x-user-id")]

def get_service(request: Request,session:AsyncSession = Depends(get_session)):
    return ChatThreadService(session = session,agent=request.app.state.agent)

@router.post("",response_model = ChatThreadResponse)
async def create_chat_thread(request:ChatThreadCreate,
                            user_id : User_id,
                            service:ChatThreadService = Depends(get_service)) -> ChatThreadResponse:
    chat_thread = await service.create_chat_thread(user_id,request.title)
    return  chat_thread

@router.get("",response_model=list[ChatThreadResponse])
async def list_chat_thread(user_id:User_id,
                           service: ChatThreadService = Depends(get_service)):
    chat_threads = await service.list_by_user(user_id)
    return chat_threads

@router.patch("/{thread_id}")
async def rename_chat_thread(thread_id: UUID,
                             user_id: User_id,
                             request:ChatThreadCreate,
                             service:ChatThreadService = Depends(get_service)):
    chat_thread = await service.rename_chat_thread(thread_id,user_id,request.title)
    return chat_thread

@router.delete("/{thread_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_thread(thread_id: UUID,
                            user_id:User_id,
                             service : ChatThreadService = Depends(get_service)):
    await service.delete_chat_thread(thread_id,user_id)
    return Response(status_code=  status.HTTP_204_NO_CONTENT)

@router.get("/{thread_id}/messages", response_model=ChatHistoryResponse)
async def get_chat_history(
    thread_id: UUID,
    user_id: User_id,
    service: ChatThreadService = Depends(get_service),
):
    """查询指定会话的历史消息"""

    return await service.get_history(thread_id, user_id)
