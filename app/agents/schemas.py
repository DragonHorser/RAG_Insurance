from dataclasses import dataclass
from typing import Literal
from typing import Annotated, Any

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field

AdditionalInfo = dict[str, Any]

@dataclass(frozen=True)
class InsuranceAgentContext:
    """保险顾问Agent运行时上下文"""

    user_id: int

# 类型别名。路由意图常量，使用这个类型的只能有下面的5个值。咱们目前只有这5个分支
Intent = Literal[
    "chitchat",
    "recommendation_plan",
    "claim",
    "human_handoff",
    "fallback",
]

# 结构化模型输出，限制模型回答的内容按这个结构输出，回顾知识点：Day05:3.4
class RouteResult(BaseModel):
    """意图识别结果"""

    intent: Intent = Field(description="本轮消息应该进入的工作流")
    reason: str = Field(description="判断该意图的理由")


class InsuranceAgentState(MessagesState):
    """保险顾问主Graph状态"""

    previous_workflow: Intent
    active_workflow: Intent

def merge_additional_info(
    left: dict[str, AdditionalInfo],
    right: dict[str, AdditionalInfo],
) -> dict[str, AdditionalInfo]:
    """按照AI消息id合并引用信息"""
    if not left:
        return right
    return left.update(right)

class InsuranceAgentState(MessagesState):
    """保险顾问主Graph状态"""

    active_workflow: Intent     # 本轮对话激活的工作流
    previous_workflow: Intent   # 上一轮对话激活的工作流
    additional_info: Annotated[ # 记录AI回答中的引用来源信息
        dict[str, AdditionalInfo],
        merge_additional_info
    ]