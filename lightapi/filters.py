from sqlalchemy.orm import Query


class BaseFilter:
    def filter_queryset(self, queryset: Query, request) -> Query:
        return queryset


class ParameterFilter(BaseFilter):
    def filter_queryset(self, queryset: Query, request) -> Query:

        query_params = dict(request.query_params)
        if not query_params:
            return queryset

        for param, value in query_params.items():
            if hasattr(queryset.column_descriptions[0]['entity'], param):
                queryset = queryset.filter(
                    getattr(queryset.column_descriptions[0]['entity'], param) == value
                )

        return queryset
