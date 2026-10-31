from decimal import Decimal

from langchain.tools import tool, ToolRuntime
from fastapi.encoders import jsonable_encoder

from app.infra.database import AsyncSessionFactory
from app.modules.product.models import Product
from app.modules.product.service import ProductService

from app.agents.schemas import InsuranceAgentContext
from app.modules.insurance_plan.schemas import InsurancePlanCreate
from app.modules.insurance_plan.service import InsurancePlanService

import json
from langgraph.config import get_stream_writer # 【新增导入】


@tool
async def query_candidate_products(
    categories: list[str],
    premium_min: Decimal | None = None,
    limit_per_category: int = 5
):
    """
    根据险种和保费条件查询可用于推荐的候选保险产品。当用户咨询具体保险产品或需要保险产品推荐时使用。

    Args:
        categories: 产品分类列表，可选值为 medical、critical_illness、life、accident。
        premium_min: 最低保费上限，可选参数，只返回最低保费小于该值的产品。
        limit_per_category: 每个险种最多返回的产品数量，可选参数，默认5。
    """
    # 要手工去获取session，不要用依赖注入Depends.是fastAPI来做的，要触发fastAPI来做这件事，就必须有router.
    # 我们这个函数给agent来调用的。
    async with AsyncSessionFactory() as session:
        # 1.初始化Service
        service = ProductService(session)
        # 2.调用Service，得到候选产品
        products: list[Product] = await service.list_candidates(
            categories,
            premium_min,
            limit_per_category
        )
        # 3.返回给AI，最好把Product处理成json返回
        return jsonable_encoder(products)

@tool
async def save_insurance_plan(
    plan: InsurancePlanCreate,
    runtime: ToolRuntime[InsuranceAgentContext],
) -> dict[str, str]:
    """
    保存当前用户的保险推荐方案。
    当你查询完候选产品后，根据用户画像、候选产品生成保险组合方案，保存到数据库
    """

    async with AsyncSessionFactory() as session:
        service = InsurancePlanService(session)
        plan_id = await service.create_plan(
            user_id=runtime.context.user_id,
            data=plan,
        )

    return {
        "plan_id": str(plan_id),
        "message": "保险方案保存成功",
    }


@tool
async def query_product_clause(
        query: str,
        product_id: int,
) -> str:
    """查询指定保险产品的条款内容。
    Args:
        query: 需要从保险条款中查询的问题。
        product_id: 保险产品ID。
    """
    from app.rag import retriever

    # 1. 【修复报错】必须传入 k 参数，写成 k=5
    chunks = await retriever.retrieve(query, k=5, product_id=product_id)
    if not chunks:
        return "没有查询到相关保险条款。"

    # 2. 组装给前端的引用字典，同时组装给大模型的上下文
    sources = {}
    context_str = ""

    for i, chunk in enumerate(chunks, start=1):
        ref_id = f"ref-{i:03d}"  # 例如 ref-001

        # 给前端的字典
        sources[ref_id] = {
            "product_id": chunk.product_id,
            "clause_name": chunk.clause_name,
            "section_path": chunk.section_path,
            "content": chunk.content,
        }

        # 给大模型的文本（必须带上 [ref-001] 这样的标记）
        section_path_str = " > ".join(chunk.section_path)
        context_str += f"[{ref_id}] 章节：{section_path_str}\n内容：{chunk.content}\n\n"

    # 3. 【核心】通过 Custom Stream 把引用详情推给前端
    writer = get_stream_writer()
    writer({"type": "additional_info", "data": sources})

    # 4. 返回带有引用标记的文本给大模型
    return context_str