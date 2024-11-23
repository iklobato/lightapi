from dataclasses import dataclass
from math import ceil
from typing import List, Any, Optional


@dataclass
class PaginationInfo:
    page: int
    limit: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool


class Paginator:
    def __init__(self, limit: int = 20, sort: bool = False):
        self.limit = limit
        self.sort = sort

    async def paginate(
        self, items: List[Any], page: int = 1, sort_by: Optional[str] = None
    ) -> tuple[List[Any], PaginationInfo]:
        total = len(items)
        total_pages = ceil(total / self.limit)

        if self.sort and sort_by:
            items = sorted(items, key=lambda x: getattr(x, sort_by, None))

        start = (page - 1) * self.limit
        end = start + self.limit
        paginated_items = items[start:end]

        return paginated_items, PaginationInfo(
            page=page,
            limit=self.limit,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )
