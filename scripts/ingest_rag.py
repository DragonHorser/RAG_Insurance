"""构建 RAG 知识库脚本。

参考 notebooks/day09/01.rag_pipeline.ipynb，将 products 表中的产品条款
解析、切分后写入 Milvus（子块）和 PostgreSQL（父块）。

用法（在项目根目录执行）：
    python scripts/ingest_rag.py                          # 导入全部 active 产品
    python scripts/ingest_rag.py --category critical_illness
    python scripts/ingest_rag.py --ids 1 2 3
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 直接运行脚本时，把项目根目录加入模块搜索路径
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langchain_milvus import BM25BuiltInFunction, Milvus
from langchain_ollama import OllamaEmbeddings

from app.core.config import APP_ROOT, settings
from app.core.logging import configure_logging, get_logger
from app.infra.database import AsyncSessionFactory, close_database
from app.modules.product.models import Product
from app.modules.product.service import ProductService
from app.rag.pipeline import RAGPipeline

logger = get_logger(__name__)

# 与 notebooks/day09/01.rag_pipeline.ipynb 保持一致
EMBEDDING_MODEL = "qwen3-embedding:0.6b"
EMBEDDING_DIMENSIONS = 1024
COLLECTION_NAME = "insurance_collection"


def init_vector_store() -> Milvus:
    """初始化 Embedding 模型与 Milvus VectorStore。"""

    embeddings = OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return Milvus(
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
        builtin_function=BM25BuiltInFunction(
            analyzer_params={"type": "chinese"}
        ),
        vector_field=["dense", "sparse"],
        connection_args={"uri": settings.rag.milvus_url},
        auto_id=True,
    )


async def load_products(
        category: str | None,
        product_ids: list[int] | None,
) -> list[Product]:
    """通过 ProductService 查询所有需要构建知识库的产品。"""

    async with AsyncSessionFactory() as session:
        products = await ProductService(session).list_products(category)

    if product_ids:
        wanted = set(product_ids)
        products = [p for p in products if p.id in wanted]
    return products


async def ingest_products(
        products: list[Product],
        pipeline: RAGPipeline,
) -> None:
    """逐个产品调用 Pipeline 构建知识库。"""

    succeeded: list[int] = []
    skipped: list[int] = []
    failed: list[int] = []

    for index, product in enumerate(products, start=1):
        pdf_path = APP_ROOT / "data" / "raw" / "kb" / product.clause_name
        prefix = f"[{index}/{len(products)}] 产品 {product.id}《{product.name}》"

        # 条款文件缺失时跳过，避免中途失败影响其他产品
        if not pdf_path.exists():
            logger.warning(f"{prefix} 条款文件不存在，已跳过：{pdf_path}")
            skipped.append(product.id)
            continue

        logger.info(f"{prefix} 开始构建知识库 ...")
        try:
            await pipeline.ingest(product)
        except Exception:
            logger.exception(f"{prefix} 构建失败")
            failed.append(product.id)
        else:
            logger.info(f"{prefix} 构建完成 ✅")
            succeeded.append(product.id)

    logger.info(
        f"知识库构建结束：成功 {len(succeeded)} 个，"
        f"失败 {len(failed)} 个，跳过 {len(skipped)} 个"
    )
    if failed:
        logger.warning(f"失败的产品 ID：{failed}")
    if skipped:
        logger.warning(f"跳过的产品 ID：{skipped}")


async def main(args: argparse.Namespace) -> None:
    # 1.初始化 Embedding 模型 + Milvus VectorStore
    vector_store = init_vector_store()

    # 2.初始化 RAG Pipeline
    pipeline = RAGPipeline(vector_store)

    try:
        # 3.查询产品（category 为空时查询全部 active 产品）
        products = await load_products(args.category, args.ids)
        if not products:
            logger.warning("没有查询到需要构建知识库的产品")
            return

        logger.info(f"共查询到 {len(products)} 个产品，开始构建 RAG 知识库")

        # 4.调用 Pipeline 构建知识库
        await ingest_products(products, pipeline)
    finally:
        # 5.释放资源
        pipeline.close()
        await close_database()


def force_utf8_console() -> None:
    """Windows 控制台默认编码可能是 GBK，而日志含中文与 emoji，统一使用 UTF-8。"""

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建保险产品 RAG 知识库")
    parser.add_argument(
        "--category",
        default=None,
        help="只处理指定产品分类，默认处理全部 active 产品",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        type=int,
        default=None,
        help="只处理指定产品 ID，默认处理全部产品",
    )
    return parser.parse_args()


if __name__ == "__main__":
    force_utf8_console()
    configure_logging(settings.logging.level)

    # Windows 下使用 Selector 事件循环，与 app/main.py 保持一致
    if sys.platform == "win32" and sys.version_info >= (3, 12):
        asyncio.run(main(parse_args()), loop_factory=asyncio.SelectorEventLoop)
    else:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main(parse_args()))
