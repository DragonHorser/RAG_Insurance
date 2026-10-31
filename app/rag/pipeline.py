from pathlib import Path
from uuid import uuid4

from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_milvus import Milvus
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from mineru import MinerU

from app.core.config import APP_ROOT, settings
from app.infra.database import AsyncSessionFactory
from app.modules.product.models import Product
from app.rag.models import ParentChunk
from app.rag.repository import ParentChunkRepository
from app.core.logging import get_logger

logger = get_logger(__name__)

MARKDOWN_OPTIMIZATION_PROMPT = """
下面这份 Markdown 文档是从保险条款 PDF 解析得来，由于 PDF 中的各个小节是以表格形式存在，所以解析时出现错乱。你分析内容，帮我转为格式正确的 Markdown，特别是标题编号要正确。
- 标题等级要从 1 级标题开始，逐层增加，目录和文档名不计入标题等级。
- 输出结果中不要包含正文开始之前的部分。
- 输出结果只包含 Markdown 正文，不要解释或代码围栏。
- 不要修改保险条款。
""".strip()


class RAGPipeline:
    # Pipeline 只关注知识库构建流程，vector_tore 的初始化和生命周期由调用方管理
    # 项目启动时来初始化，创建pipeline，以后需要时就可以导入使用
    def __init__(self, vector_store: Milvus) -> None:
        """ 初始化操作：需要使用多次的对象在这里定义
            使用_定义私有属性，只在内部使用。
        """

        self._vector_store = vector_store

        # 1.初始化文档解析工具
        self._mineru = MinerU(settings.rag.mineru_token)

        self._model = init_chat_model(
            settings.llm.chat_model,
            api_key=settings.llm.api_key,
            extra_body={"thinking": {"type": "disabled"}},
            max_tokens=10000,
        )

        # 2.初始化文档切分工具
        self._markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "h1"),
                ("##", "h2"),
                ("###", "h3"),
                ("####", "h4"),
            ],
            strip_headers=True,
        )
        self._child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "；", ";", "，", ","],
            keep_separator="end",
        )
        logger.info("RAG Pipeline 初始化完成✅️")

    async def ingest(self, product: Product) -> None:
        """ 知识库构建主体流程入口 """

        # 1.解析并优化保险条款
        markdown = self._parse_and_optimize(product.clause_name)

        # 2.切分父块和子块
        parent_chunks, child_chunks = self._chunk(markdown, product)

        # 3.子块存入Milvus
        self._save_child_chunks(product.id, child_chunks)

        # 4.父块存入PostgreSQL
        await self._save_parent_chunks(product.id, parent_chunks)

    def _parse_and_optimize(self, clause_name: str) -> str:
        """ 解析并优化保险条款
            clause_name为保险条件pdf的文件名
        """

        # 1.使用MinerU解析PDF
        file_path = Path(APP_ROOT / "data" / "raw" / "kb" / clause_name)
        result = self._mineru.extract(str(file_path))

        # 2.使用大模型优化Markdown
        response = self._model.invoke(
            [
                {"role": "system", "content": MARKDOWN_OPTIMIZATION_PROMPT},
                {"role": "user", "content": result.markdown},
            ]
        )
        return response.content

    def _chunk(
            self,
            markdown: str,
            product: Product,
    ) -> tuple[list[ParentChunk], list[Document]]:
        """ 父子块切分处理，返回处理好的父块列表与子块列表 """

        # 1.按照Markdown标题切分父块
        sections = self._markdown_splitter.split_text(markdown)
        parent_chunks: list[ParentChunk] = []
        child_chunks: list[Document] = []

        # 2.遍历父块，继续切分子块
        for section in sections:
            section_path = list(section.metadata.values())
            parent = ParentChunk(
                id=uuid4(),
                product_id=product.id,
                clause_name=product.clause_name,
                section_path=section_path,
                content=section.page_content,
            )
            parent_chunks.append(parent)

            # 子块通过parent_id关联父块
            section.metadata = {
                "product_id": product.id,
                "parent_id": str(parent.id),
            }
            children = self._child_splitter.split_documents([section])

            # 把章节路径拼接到子块正文中，补充语义上下文
            section_header = "\n".join(section_path) + "\n"
            for child in children:
                child.page_content = section_header + child.page_content
            child_chunks.extend(children)

        return parent_chunks, child_chunks

    def _save_child_chunks(
            self,
            product_id: int,
            child_chunks: list[Document],
    ) -> None:
        """ 保存子块到向量库milvus中 """

        # Collection存在时，先删除该产品的旧子块
        if self._vector_store.client.has_collection(
                self._vector_store.collection_name
        ):
            self._vector_store.delete(expr=f"product_id == {product_id}")
        # 再新增子块
        self._vector_store.add_documents(child_chunks)

    async def _save_parent_chunks(
            self,
            product_id: int,
            parent_chunks: list[ParentChunk],
    ) -> None:
        """ 保存父块信息到pg数据库中。
        1.为防止重复添加，先删除旧数据，再添加新数据
        2.需要做事务控制
        """
        async with AsyncSessionFactory() as session:
            async with session.begin():
                repository = ParentChunkRepository(session)
                # 删除旧父块
                await repository.delete_by_product_id(product_id)
                # 添加新父块
                repository.add_all(parent_chunks)

    def close(self):
        """关闭mineru连接"""

        self._mineru.close()