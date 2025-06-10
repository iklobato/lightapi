from typing import Any, List

from sqlalchemy.orm import Query


class Paginator:
    """
    Base class for pagination.

    Provides methods for limiting, offsetting, and sorting database queries.
    Can be subclassed to implement custom pagination behavior.

    Attributes:
        limit: Maximum number of records to return.
        offset: Number of records to skip.
        sort: Whether to apply sorting.
    """

    limit = 10
    offset = 0
    sort = False

    def paginate(self, queryset: Query) -> List[Any]:
        """
        Apply pagination to a database query.

        Limits the number of results, applies offset, and
        optionally sorts the queryset.

        Args:
            queryset: The SQLAlchemy query to paginate.

        Returns:
            List[Any]: The paginated list of results.
        """
        request_limit = self.get_limit()
        request_offset = self.get_offset()

        if self.sort:
            queryset = self.apply_sorting(queryset)

        return queryset.limit(request_limit).offset(request_offset).all()

    def get_limit(self) -> int:
        """
        Get the limit for pagination.

        Override this method to implement dynamic limits based on the request.

        Returns:
            int: The maximum number of records to return.
        """
        return self.limit

    def get_offset(self) -> int:
        """
        Get the offset for pagination.

        Override this method to implement dynamic offsets based on the request.

        Returns:
            int: The number of records to skip.
        """
        return self.offset

    def apply_sorting(self, queryset: Query) -> Query:
        """
        Apply sorting to the queryset.

        Override this method to implement custom sorting logic.

        Args:
            queryset: The SQLAlchemy query to sort.

        Returns:
            Query: The sorted query.
        """
        return queryset
