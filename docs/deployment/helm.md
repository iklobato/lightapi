---
title: Kubernetes (Helm)
---

Deploy a full CRUD REST API over a database that already exists by writing only
a `values.yaml`. No CRUD code, no per-project image build.

LightAPI already turns a declarative YAML config into SQLAlchemy tables, Pydantic
schemas, and CRUD routes (see [YAML Configuration](../examples/yaml-configuration.md)).
The chart's only job is to hand that config to `LightApi.from_config`, inject the
database secret, run the process, and expose it. The config block in `values.yaml`
is exactly the declarative `lightapi.yaml` the framework parses.

## Prerequisites

- A running Kubernetes cluster (minikube, kind, or a real one).
- `helm` 3.x and `kubectl`.
- A reachable database. The chart connects to an existing database; it does not
  manage one.

## The container image

The chart runs a generic image whose entry point is `lightapi serve`. That
command reads `LIGHTAPI_CONFIG`, `LIGHTAPI_HOST`, and `LIGHTAPI_PORT` from the
environment. Build and publish it once:

```bash
docker build -t youracct/lightapi:0.1.21 .
docker push youracct/lightapi:0.1.21
```

Point the chart at it with `image.repository` and `image.tag`.

## Install

```bash
helm install shop charts/lightapi -f my-values.yaml
```

A minimal `my-values.yaml`:

```yaml
image:
  repository: youracct/lightapi
  tag: "0.1.21"

database:
  # Dev: the chart creates a Secret from this URL.
  url: "postgresql://postgres:pass@my-postgres:5432/app"

config:
  database:
    url: "${DATABASE_URL}"          # resolved from the Secret at runtime
  endpoints:
    - route: /products
      fields:
        name:  { type: str, max_length: 200 }
        price: { type: float }
      meta:
        methods: [GET, POST, PUT, DELETE]
        authentication: { permission: AllowAny }
```

## Add a table later

Add an entry under `config.endpoints` and upgrade. The ConfigMap checksum changes,
so the pods roll automatically:

```bash
helm upgrade shop charts/lightapi -f my-values.yaml
```

## Database credentials

Two ways to provide the connection URL:

- **Dev**: set `database.url`. The chart creates a Secret from it.
- **Production**: create your own Secret and set `database.existingSecret` to its
  name. The chart then references it and creates no Secret of its own. Keep the
  key name in `database.urlKey` (default `DATABASE_URL`) in sync with the
  `${DATABASE_URL}` placeholder in `config.database.url`.

```bash
kubectl create secret generic my-db \
  --from-literal=DATABASE_URL='postgresql://user:pass@host:5432/app'

helm upgrade shop charts/lightapi -f my-values.yaml \
  --set database.existingSecret=my-db
```

JWT and Redis follow the same pattern via `jwt.*` and `redis.url` (only needed
when an endpoint uses `JWTAuthentication` or `Meta.cache`).

## Health, probes, and autoscaling

- Liveness and readiness probes hit `GET /healthz` (always registered). A pod
  that fails to boot (for example, an invalid config) stays `NotReady` and
  receives no traffic.
- Set `ingress.enabled: true` with `ingress.hosts` to publish through an Ingress.
- Set `autoscaling.enabled: true` to create an HPA. When it is on, the chart does
  not set `replicas` (the HPA owns it).

## minikube walkthrough

```bash
minikube start
docker build -t lightapi:dev .
minikube image load lightapi:dev

# a throwaway Postgres in the cluster to connect to
kubectl create deployment pg --image=postgres:16-alpine
kubectl set env deployment/pg POSTGRES_PASSWORD=pass POSTGRES_DB=app
kubectl expose deployment pg --port=5432

helm install shop charts/lightapi \
  --set image.repository=lightapi --set image.tag=dev --set image.pullPolicy=Never \
  --set database.url='postgresql://postgres:pass@pg:5432/app'

kubectl rollout status deploy/shop-lightapi
kubectl port-forward svc/shop-lightapi 8000:80

curl http://127.0.0.1:8000/healthz
curl -X POST http://127.0.0.1:8000/products \
  -H 'Content-Type: application/json' -d '{"name":"Widget","price":9.5}'
```

## Uninstall

```bash
helm uninstall shop
```

## Values reference

See [charts/lightapi/README.md](https://github.com/iklobato/lightapi/blob/master/charts/lightapi/README.md)
for the complete list of values and defaults.
