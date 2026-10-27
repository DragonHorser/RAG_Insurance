from app.core.exceptions import ApplicationError


class ChatThreadNotFoundError(ApplicationError):
    """会话不存在或不属于当前用户"""

    status_code = 400
    code = "CHAT_THREAD_NOT_FOUND"
    message = "会话不存在或不属于当前用户"

class ChatThreadNameExistsError(ApplicationError):

    status_code = 400
    code = "CAHT THREAD NAME EXISTS"
    message = "会话名称已存在"