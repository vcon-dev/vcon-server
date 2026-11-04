# Deploy on Kubernetes

This page gives example manifests for the API, the workers and Redis. The repo ships no manifests and CI does not test these, so treat them as a starting point. The Kubernetes group in the [deploy map](index.md) shows how the pieces connect.

## Prepare the cluster

You need:

- A cluster with a persistent volume provisioner
- `kubectl` configured for that cluster
- Pull access to `public.ecr.aws`

Use the two published images. `api` runs `vcon-server-api` and `worker` runs `vcon-server-conserver`. See [Run the published images](docker.md#run-the-published-images) for the tags, and pin a version in production. Each image starts its own process and waits for `REDIS_URL`, so the manifests set no `command`.

## Write the manifests

Create a `k8s/` folder with these files.

### Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: vcon-server
```

### ConfigMap

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: vcon-config
  namespace: vcon-server
data:
  config.yml: |
    links:
      tag_processed:
        module: links.tag
        options:
          tags:
            - processed

    storages:
      redis_storage:
        module: storage.redis_storage

    chains:
      main_chain:
        links:
          - tag_processed
        storages:
          - redis_storage
        ingress_lists:
          - default
```

Build your own chains with [YAML configuration](../configuration/yaml-configuration.md).

The server does not expand `${VAR}` in this file, so link and storage credentials sit in it as plain values. Once they do, move `config.yml` from the ConfigMap to a Secret. `POST /config` writes to this file, so it fails on a read-only mount.

### Secrets

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: vcon-secrets
  namespace: vcon-server
type: Opaque
stringData:
  api-token: "your-secure-api-token"
```

In production, fill this Secret from a secrets manager rather than a file in Git.

### Redis

The arguments match the `redis` service in `docker-compose.yml`.

```yaml
# k8s/redis.yaml
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: vcon-server
spec:
  ports:
    - port: 6379
      targetPort: 6379
  selector:
    app: redis
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
  namespace: vcon-server
spec:
  serviceName: redis
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7.4-alpine
          args: ["redis-server", "--save", "20", "1", "--notify-keyspace-events", "Ex", "--dir", "/data", "--appendonly", "yes"]
          ports:
            - containerPort: 6379
          resources:
            requests:
              memory: "256Mi"
              cpu: "100m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          volumeMounts:
            - name: redis-data
              mountPath: /data
  volumeClaimTemplates:
    - metadata:
        name: redis-data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 10Gi
```

### API

```yaml
# k8s/api.yaml
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: vcon-server
spec:
  ports:
    - port: 8000
      targetPort: 8000
  selector:
    app: api
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: vcon-server
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
        - name: api
          image: public.ecr.aws/r4g1k2s3/vcon-dev/vcon-server-api:latest
          ports:
            - containerPort: 8000
          env:
            - name: REDIS_URL
              value: "redis://redis:6379"
            - name: CONSERVER_API_TOKEN
              valueFrom:
                secretKeyRef:
                  name: vcon-secrets
                  key: api-token
            - name: CONSERVER_CONFIG_FILE
              value: "/config/config.yml"
          volumeMounts:
            - name: config
              mountPath: /config
          resources:
            requests:
              memory: "256Mi"
              cpu: "100m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          readinessProbe:
            httpGet:
              path: /api/health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /api/health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
      volumes:
        - name: config
          configMap:
            name: vcon-config
```

### Workers

```yaml
# k8s/worker.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: worker
  namespace: vcon-server
spec:
  replicas: 4
  selector:
    matchLabels:
      app: worker
  template:
    metadata:
      labels:
        app: worker
    spec:
      containers:
        - name: worker
          image: public.ecr.aws/r4g1k2s3/vcon-dev/vcon-server-conserver:latest
          env:
            - name: REDIS_URL
              value: "redis://redis:6379"
            - name: CONSERVER_API_TOKEN
              valueFrom:
                secretKeyRef:
                  name: vcon-secrets
                  key: api-token
            - name: CONSERVER_CONFIG_FILE
              value: "/config/config.yml"
            - name: CONSERVER_WORKERS
              value: "2"
            - name: CONSERVER_PARALLEL_STORAGE
              value: "true"
          volumeMounts:
            - name: config
              mountPath: /config
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
      volumes:
        - name: config
          configMap:
            name: vcon-config
      terminationGracePeriodSeconds: 60
```

### Ingress

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: vcon-ingress
  namespace: vcon-server
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - vcon.example.com
      secretName: vcon-tls
  rules:
    - host: vcon.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 8000
```

### Autoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: worker-hpa
  namespace: vcon-server
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: worker
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

## Apply the manifests

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Apply configurations
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml

# Deploy services
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/api.yaml
kubectl apply -f k8s/worker.yaml

# Configure ingress
kubectl apply -f k8s/ingress.yaml

# Optional: Enable autoscaling
kubectl apply -f k8s/hpa.yaml
```

## Check the deployment

```bash
# Check pod status
kubectl get pods -n vcon-server

# Check services
kubectl get svc -n vcon-server

# Check logs
kubectl logs -f deployment/worker -n vcon-server

# Test API
kubectl port-forward svc/api 8000:8000 -n vcon-server
curl http://localhost:8000/api/health
```

## Scale the deployments

```bash
kubectl scale deployment/worker --replicas=8 -n vcon-server
kubectl scale deployment/api --replicas=4 -n vcon-server
```

The example autoscaler scales workers on CPU. The `conserver.ingress_list.length` metric reports queue depth if you prefer to scale on that. See [Workers](../configuration/workers.md) to balance replicas against `CONSERVER_WORKERS` and `CONSERVER_VCON_CONCURRENCY`.

## Connect monitoring

The server exposes no Prometheus endpoint. It pushes metrics and traces over OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set, so add that variable to both Deployments and point it at your collector:

```yaml
env:
  - name: OTEL_EXPORTER_OTLP_ENDPOINT
    value: "http://otel-collector:4317"
```

See [Monitoring](../operations/monitoring.md) and the [metric list](../reference/metrics.md). [Logging](../operations/logging.md) covers log format, which `LOGGING_CONFIG_FILE` sets.

## Adapt the Ingress to your cloud

### AWS EKS

```yaml
# Use AWS Load Balancer Controller
metadata:
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
```

### Google GKE

```yaml
# Use Google Cloud Load Balancer
metadata:
  annotations:
    kubernetes.io/ingress.class: gce
    kubernetes.io/ingress.global-static-ip-name: vcon-ip
```

### Azure AKS

```yaml
# Use Azure Application Gateway
metadata:
  annotations:
    kubernetes.io/ingress.class: azure/application-gateway
```

## Troubleshoot the cluster

### Diagnose a stuck pod

```bash
# Check pod status
kubectl describe pod <pod-name> -n vcon-server

# Check events
kubectl get events -n vcon-server --sort-by='.lastTimestamp'
```

A pod that logs `Redis not ready yet. Retrying...` cannot reach `REDIS_URL`.

### Diagnose a failed connection

```bash
# Test Redis connectivity
kubectl exec -it deployment/api -n vcon-server -- redis-cli -h redis ping

# Check service endpoints
kubectl get endpoints -n vcon-server
```

### Check resource usage

```bash
# Check resource usage
kubectl top pods -n vcon-server

# Check node resources
kubectl describe nodes
```

## Continue with these guides

- [Configuration guide](../configuration/index.md)
- [Monitoring](../operations/monitoring.md)
- [Workers](../configuration/workers.md)
