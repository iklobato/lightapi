# lightapi Helm chart

Deploy a declarative CRUD REST API (LightAPI) over an existing database with only
a `values.yaml`. No CRUD code, no per-project image build.

The chart renders your `config` block into a ConfigMap, passes it to
`LightApi.from_config`, injects the database URL from a Secret, and serves the
app. Adding a table means adding an entry under `config.endpoints` and running
`helm upgrade`.

## Install

```bash
helm install shop charts/lightapi -f my-values.yaml
```

## Values

| Key | Default | Description |
|-----|---------|-------------|
| `replicaCount` | `2` | Replicas (ignored when `autoscaling.enabled`). |
| `image.repository` | `iklob1/lightapi` | Published multi-arch image. |
| `image.tag` | `""` | Image tag; defaults to the chart `appVersion`. |
| `image.pullPolicy` | `IfNotPresent` | Image pull policy. |
| `nameOverride` / `fullnameOverride` | `""` | Override generated names. |
| `database.url` | `""` | Connection URL. When set (and no `existingSecret`), the chart creates a Secret from it. Dev convenience. |
| `database.existingSecret` | `""` | Name of a Secret you manage that holds the URL. Production path; the chart creates no Secret. |
| `database.urlKey` | `DATABASE_URL` | Key under which the URL lives in the Secret. Keep in sync with the `${DATABASE_URL}` placeholder in `config`. |
| `jwt.secret` | `""` | JWT secret; chart-managed Secret (only if an endpoint uses `JWTAuthentication`). |
| `jwt.existingSecret` | `""` | Name of a Secret holding the JWT secret. |
| `jwt.secretKey` | `LIGHTAPI_JWT_SECRET` | Key for the JWT secret. |
| `redis.url` | `""` | `LIGHTAPI_REDIS_URL`; only needed when an endpoint sets `Meta.cache`. |
| `config` | products example | The declarative LightAPI config, copied verbatim into a ConfigMap. This is the whole developer-facing surface. |
| `service.type` | `ClusterIP` | Service type. |
| `service.port` | `80` | Service port. |
| `service.targetPort` | `8000` | Container port (`LIGHTAPI_PORT`). |
| `ingress.enabled` | `false` | Create an Ingress. |
| `ingress.className` | `""` | Ingress class. |
| `ingress.annotations` | `{}` | Ingress annotations. |
| `ingress.hosts` | `[]` | List of `{host, paths: [{path, pathType}]}`. |
| `autoscaling.enabled` | `false` | Create an HPA. When on, `replicas` is not set (the HPA owns it). |
| `autoscaling.minReplicas` | `2` | HPA min replicas. |
| `autoscaling.maxReplicas` | `5` | HPA max replicas. |
| `autoscaling.targetCPUUtilizationPercentage` | `80` | HPA CPU target. |
| `resources` | `{}` | Container resources. Left empty on purpose: derive from measured load, do not guess. |
| `extraEnv` | `[]` | Extra environment variables (list of `{name, value}`). |

## The `config` block

`config` is the declarative `lightapi.yaml` LightAPI already understands. Example:

```yaml
config:
  database:
    url: "${DATABASE_URL}"          # resolved from the Secret at runtime
  defaults:
    pagination: { style: page_number, page_size: 20 }
  endpoints:
    - route: /products
      fields:
        name:     { type: str, max_length: 200 }
        price:    { type: float }
        in_stock: { type: bool, default: true }
      meta:
        methods: [GET, POST, PUT, DELETE]
        authentication: { permission: AllowAny }
        filtering: { fields: [in_stock], ordering: [price] }
    # Wrap an existing table instead of declaring fields:
    - route: /legacy_users
      reflect: true
      meta: { methods: [GET] }
```

## Health

Liveness and readiness probes target `GET /healthz`, which every LightAPI app
registers. A pod with an invalid config stays `NotReady` and serves no traffic.

## Full guide

See the [Kubernetes (Helm) deployment guide](https://github.com/iklobato/lightapi/blob/master/docs/deployment/helm.md).
