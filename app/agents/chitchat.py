from typing import NotRequired

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, SystemMessage, content
from langgraph.graph import StateGraph

from app.agents.schemas import InsuranceAgentState
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_MESSAGE = """
你是保险智能客服，负责处理与保险业务无关的普通聊天。

要求：
1. 回复友好、自然，最多两句话。
2. 不假装有个人经历、情感、实时信息或外部能力。
3. 不回答医疗、法律、投资等高风险专业建议。
4. 每次回复都自然引导用户回到保险产品、投保或理赔业务。
5. 超出能力范围时，如实说明无法提供。
""".strip()

MAX_CHITCHAT_COUNT = 3


class ChitchatState(InsuranceAgentState):
    """闲聊子Agent状态"""

    # NotRequired非必须的，该变量可以没有值，作用类似于Anootated[类型，函数]
    # 子图默认继承父图的类
    chitchat_count: NotRequired[int]


class ChitchatAgent:

    def __init__(self) -> None:
        self.model = init_chat_model(
            model=settings.llm.chat_model,
            model_provider="deepseek",
            api_key=settings.llm.api_key,
            extra_body={"thinking": {"type": "disabled"}},
        )

    async def handle_chitchat(
        self,
        state: ChitchatState,
    ) -> dict:
        #先获取闲聊的次数
        count = state.get("chitchat_count", 0)

        # 上一轮不是闲聊，重新开始计数,认为已经闲聊0次
        if state.get("previous_workflow","") != "chitchat":
            count = 0

        logger.info("处理闲聊消息", chitchat_count=count)

        if count >= MAX_CHITCHAT_COUNT:
            logger.info("闲聊次数已经耗尽",content = count)
            return {
                "messages": [
                    AIMessage("我主要协助处理保险产品、投保和理赔咨询，请告诉我想办理或了解的事项。")
                    ]
            }
        #否则 调用模型，由模型回复用户的消息
        response = await self.model.ainvoke(
            [SystemMessage(content=SYSTEM_MESSAGE), *state["messages"]]
        )
        logger.info("已经闲聊一次了",content = count)
        return {
            "messages": [response],
            "chitchat_count": count + 1,
        }

    def build(self):
        builder = StateGraph(ChitchatState)
        builder.add_node("handle_chitchat", self.handle_chitchat)
        builder.set_entry_point("handle_chitchat")
        builder.set_finish_point("handle_chitchat")

        # 使用父Graph提供的Checkpointer，保存子图私有状态
        return builder.compile(checkpointer=True)


def init_chitchat_agent():
    return ChitchatAgent().build()