from langchain_milvus import Milvus
from pymilvus import Function, FunctionType

from app.infra.database import AsyncSessionFactory
from app.rag.models import ParentChunk
from app.rag.repository import ParentChunkRepository
from app.core.logging import get_logger
logger = get_logger(__name__)


def create_reranker(query: str) -> Function:
    """milvus的reranker function，这里采用ali的重排模型"""
    return Function(
        name="dashscope_semantic_ranker",
        input_field_names=["text"],
        function_type=FunctionType.RERANK,
        params={
            "reranker": "model",
            "provider": "ali",
            "model_name": "gte-rerank-v2",
            "queries": [query],
            "max_client_batch_size": 5,
        },
    )


class ParentChunkRetriever:

    def __init__(self, vector_store: Milvus):
        self.vector_store = vector_store
        logger.info("RAG Retriever 初始化完成✅️")

    async def retrieve(self, query: str, k: int, product_id: int) -> list[ParentChunk]:
        # 1.在指定产品内混合检索并重排，得到子块
        child_chunks = await self.vector_store.asimilarity_search(
            query=query,
            # 精排后获取分数最高的前k数量
            k=k,
            # 召回侯选文档数量
            fetch_k=10,
            expr=f"product_id == {product_id}",
            reranker=create_reranker(query),
        )

        # 2.提取parent_id，并按照召回顺序去重
        parent_ids = list(
            dict.fromkeys(  # 用dict.fromkeys对parent_id滤重
                child.metadata["parent_id"] for child in child_chunks
            )
        )
        if not parent_ids:
            return []

        # 3.根据parent_id批量查询父块
        async with AsyncSessionFactory() as session:
            repository = ParentChunkRepository(session)
            parent_chunks = await repository.list_by_ids(parent_ids)

        # 4.按照子块召回顺序组装父文档

        # 4.1.先组装dict{key=parent_id, value=parent_chunk}
        parent_chunk_map = {
            str(parent.id): parent
            for parent in parent_chunks
        }
        # 4.2.按照召回的parent_ids顺序遍历，再到dict中拿到parent
        return [
            parent_chunk_map[parent_id]  # 推导式的结果
            for parent_id in parent_ids  # 推导式数据来源
        ]