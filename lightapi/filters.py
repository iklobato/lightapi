from sqlalchemy.orm import Query


class BaseFilter:
    """
    Base class for query filters.

    Provides a common interface for all filtering methods.
    By default, returns the queryset unchanged.
    """

    def filter_queryset(self, queryset: Query, request) -> Query:
        """
        Filter a database queryset based on the request.

        Args:
            queryset: The SQLAlchemy query to filter.
            request: The HTTP request containing filter parameters.

        Returns:
            Query: The filtered query.
        """
        return queryset


class ParameterFilter(BaseFilter):
    """
    Filter queryset based on request query parameters.

    Automatically filters the queryset using query parameters that
    match model field names, performing exact matching.
    """

    def filter_queryset(self, queryset: Query, request) -> Query:
        """
        Filter a database queryset based on request query parameters.

        For each query parameter that matches a model field name,
        the queryset is filtered to records where that field equals
        the parameter value.

        Args:
            queryset: The SQLAlchemy query to filter.
            request: The HTTP request containing filter parameters.

        Returns:
            Query: The filtered query.
        """
        query_params = dict(request.query_params)
        if not query_params:
            return queryset

        entity = queryset.column_descriptions[0]["entity"]
        result = None
        for param, value in query_params.items():
            if hasattr(entity, param):
                result = queryset.filter(getattr(entity, param) == value)
        return result if result is not None else queryset
