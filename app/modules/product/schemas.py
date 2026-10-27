from decimal import Decimal
from pydantic import BaseModel


class ProductResponse(BaseModel):
    """保险产品响应结果"""

    id: int
    name: str
    clause_name: str
    category: str
    insurer: str
    image_url: str
    description: str
    min_premium: Decimal | None  #Decimal是decimal里的类，用于进行数字的精确计算
    max_premium: Decimal | None
    target_group: str | None
    highlights: list[str]
    status: str
