from typing import Any, List

from sqlalchemy.orm import Query


class Paginator:
    limit = 10
    offset = 0
    sort = False

    def paginate(self, queryset: Query) -> List[Any]:

        request_limit = self.get_limit()
        request_offset = self.get_offset()

        if self.sort:
            queryset = self.apply_sorting(queryset)

        return queryset.limit(request_limit).offset(request_offset).all()

    def get_limit(self) -> int:
        return self.limit

    def get_offset(self) -> int:
        return self.offset

    def apply_sorting(self, queryset: Query) -> Query:

        return queryset
