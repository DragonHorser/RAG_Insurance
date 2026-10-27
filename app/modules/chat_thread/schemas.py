from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator



class ChatThreadCreate(BaseModel):
    # Pydantic：用于对数据进行校验
    # Field：对数据做更详细的要求。
    #   default：如果没有提供值，就采用默认值；
    #   min_length：传值的话，值的长度最小是1
    #   max_length：传值的话，值的长度最大是200
    title : str = Field(default="新的会话",min_length=1,max_lenth = 200)

    # 对title的值提供更复杂的校验逻辑
    #   field：是对哪个字段做校验，现在是对title的值做校验
    #   mode：什么时候进行校验，在封装成对象之前先校验，如果不通过则直接报错
    #   当前端传参title进来时，先把值交给此函数
    @field_validator("title",mode = 'before')
    @classmethod
    def normalize_title(cls,value:str) -> str:
        return value.strip()

class ChatThreadResponse(BaseModel):
    id:UUID
    title:str
    created_at : datetime
    updated_at : datetime