from sqlalchemy.orm import Query


class BaseFilter:
    def filter_queryset(self, queryset: Query, request) -> Query:
        return queryset


class ParameterFilter(BaseFilter):
    def filter_queryset(self, queryset: Query, request) -> Query:

        query_params = dict(request.query_params)
        if not query_params:
            return queryset

        # Use the original queryset for all filter calls
        entity = queryset.column_descriptions[0]['entity']
        result = None
        for param, value in query_params.items():
            if hasattr(entity, param):
                # Always call filter on the original queryset
                result = queryset.filter(
                    getattr(entity, param) == value
                )
        # Return the final filtered queryset or the original if no filters applied
        return result if result is not None else queryset
