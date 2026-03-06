from pydantic import Field as _pydantic_Field
from pydantic.fields import FieldInfo

_LIGHTAPI_KWARGS: frozenset[str] = frozenset(
    {"foreign_key", "unique", "index", "exclude", "decimal_places"}
)


def Field(**kwargs: object) -> FieldInfo:  # type: ignore[return]
    """LightAPI Field wrapper.

    Accepts all standard Pydantic Field kwargs plus LightAPI-specific column kwargs
    (foreign_key, unique, index, exclude, decimal_places).  The LightAPI kwargs are
    stored in json_schema_extra so RestEndpointMeta can read them; they are stripped
    before Pydantic processes the field definition.
    """
    lightapi_meta: dict[str, object] = {
        k: kwargs.pop(k)  # type: ignore[misc]
        for k in list(kwargs)
        if k in _LIGHTAPI_KWARGS
    }
    existing_extra: dict[str, object] = kwargs.pop("json_schema_extra", None) or {}  # type: ignore[assignment]
    return _pydantic_Field(
        **kwargs, json_schema_extra={**existing_extra, **lightapi_meta}
    )  # type: ignore[return-value]
