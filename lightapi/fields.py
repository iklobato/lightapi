from typing import Any

from pydantic import Field as _pydantic_Field

_LIGHTAPI_KWARGS: frozenset[str] = frozenset(
    {"foreign_key", "unique", "index", "exclude", "decimal_places"}
)


def Field(
    **kwargs: Any,  # noqa: ANN401  pydantic Field kwargs, forwarded as given
) -> Any:  # noqa: ANN401  typed like pydantic.Field, so `x: int = Field()` type-checks
    """LightAPI Field wrapper.

    Accepts all standard Pydantic Field kwargs plus LightAPI-specific column kwargs
    (foreign_key, unique, index, exclude, decimal_places).  The LightAPI kwargs are
    stored in json_schema_extra so RestEndpointMeta can read them; they are stripped
    before Pydantic processes the field definition.
    """
    lightapi_meta = {k: kwargs.pop(k) for k in list(kwargs) if k in _LIGHTAPI_KWARGS}
    existing_extra: dict[str, Any] = kwargs.pop("json_schema_extra", None) or {}
    return _pydantic_Field(
        **kwargs, json_schema_extra={**existing_extra, **lightapi_meta}
    )
