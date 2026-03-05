# API Reference Overview

Detailed reference for every public module in LightAPI v2.

## Modules

| Page | Description |
|------|-------------|
| [Core API](core.md) | `LightApi`, `Middleware`, `CORSMiddleware`, `Response` |
| [REST API](rest.md) | `RestEndpoint`, `Field`, `HttpMethod`, `SchemaFactory` |
| [Authentication](auth.md) | `Authentication`, `JWTAuthentication`, permission classes |
| [Database](database.md) | Engine setup, `get_sync_session`, `get_async_session`, reflection |
| [Caching](cache.md) | `Cache`, `RedisCache`, `BaseCache` |
| [Filtering](filters.md) | `Filtering`, `FieldFilter`, `SearchFilter`, `OrderingFilter` |
| [Pagination](pagination.md) | `Pagination`, `PageNumberPaginator`, `CursorPaginator` |
| [Models](models.md) | Field type map, auto-injected columns, `Meta` options |
| [Validation](validation.md) | Pydantic v2 constraints, schemas, `Serializer` |
| [Exceptions](exceptions.md) | `ConfigurationError`, `SerializationError` |
| [OpenAPI](swagger.md) | Schema access via `SchemaFactory`, third-party OpenAPI integration |

## See Also

- [Getting Started](../getting-started/introduction.md) — framework introduction
- [Tutorial](../tutorial/basic-api.md) — step-by-step guide
- [Advanced Topics](../advanced/async.md) — async, middleware, background tasks
