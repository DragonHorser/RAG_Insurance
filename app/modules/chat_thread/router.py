from typing import Annotated
from fastapi import APIRouter, Depends, Response, status
from fastapi.params import Header
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_session
from app.modules.chat_thread.schemas import ChatThreadCreate,ChatThreadResponse
from app.modules.chat_thread.service import ChatThreadService

router = APIRouter(prefix="/api/v1/chat-threads",tags=["会话管理"])

def get_service(session:AsyncSession = Depends(get_session)):
    return ChatThreadService(session)

@router.post("",response_model = ChatThreadResponse)
async def create_chat_thread(request:ChatThreadCreate,
                            user_id : Annotated[int,Header(alias = "x-user-id")],
                            service:ChatThreadService = Depends(get_service)):
    chat_thread = await service.create_chat_thread(user_id,request.title)
    return  chat_thread

@router.get("",response_model=list[ChatThreadResponse])
async def list_chat_thread(user_id:Annotated[int,Header(alias='x-user-id')],
                           service: ChatThreadService = Depends(get_service)):
    chat_threads = await service.list_by_user(user_id)
    return chat_threads

@router.patch("/{thread_id}")
async def rename_chat_thread(thread_id: UUID,
                             user_id: Annotated[int,Header(alias = "x-user-id")],
                             request:ChatThreadCreate,
                             service:ChatThreadService = Depends(get_service)):
    chat_thread = await service.rename_chat_thread(thread_id,user_id,request.title)
    return chat_thread

@router.delete("/{thread_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_thread(thread_id: UUID,
                            user_id:Annotated[int,Header(alias='x-user-id')],
                             service : ChatThreadService = Depends(get_service)):
    await service.delete_chat_thread(thread_id,user_id)
    return Response(status_code=  status.HTTP_204_NO_CONTENT)
