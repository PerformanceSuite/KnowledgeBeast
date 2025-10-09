# KnowledgeBeast Production Deployment Guide

**Version:** 2.3.0
**Last Updated:** 2025-10-09
**Status:** Production Ready
**Estimated Deployment Time:** 2-4 hours

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Architecture](#architecture)
4. [Docker Deployment](#docker-deployment)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [Configuration Management](#configuration-management)
7. [Monitoring and Observability](#monitoring-and-observability)
8. [Security Hardening](#security-hardening)
9. [Performance Tuning](#performance-tuning)
10. [Backup and Disaster Recovery](#backup-and-disaster-recovery)
11. [Troubleshooting](#troubleshooting)
12. [Production Checklist](#production-checklist)
13. [Appendix](#appendix)

---

## Overview

### Introduction

This comprehensive guide walks you through deploying KnowledgeBeast v2.3.0 in production environments. It covers Docker and Kubernetes deployments, security best practices, monitoring setup, and operational procedures.

### Deployment Options

KnowledgeBeast supports three production deployment strategies:

1. **Docker Compose** - Best for small to medium deployments (< 10k requests/day)
2. **Kubernetes** - Recommended for large-scale, high-availability deployments
3. **Hybrid** - Docker for development, Kubernetes for production

### Key Features

- **Zero-downtime deployments** with rolling updates
- **Auto-scaling** based on CPU, memory, and custom metrics
- **Multi-region support** for global availability
- **Comprehensive monitoring** with Prometheus and Grafana
- **Security hardening** with non-root containers, network policies, and TLS

---

## Prerequisites

### System Requirements

#### Minimum Requirements

- **CPU:** 4 cores
- **RAM:** 8 GB
- **Storage:** 100 GB SSD
- **Network:** 100 Mbps
- **OS:** Linux (Ubuntu 20.04+, CentOS 8+, RHEL 8+)

#### Recommended Requirements

- **CPU:** 8+ cores
- **RAM:** 16+ GB
- **Storage:** 500+ GB NVMe SSD
- **Network:** 1 Gbps
- **OS:** Ubuntu 22.04 LTS

#### Kubernetes Requirements

- **Kubernetes Version:** 1.26+
- **Nodes:** 3+ worker nodes (for high availability)
- **Node Resources:** 4 CPU, 8 GB RAM per node
- **Storage Class:** Fast SSD (gp3, pd-ssd, or equivalent)
- **Ingress Controller:** NGINX Ingress Controller
- **Cert Manager:** For automated TLS certificate management

### Software Dependencies

#### Required

- Docker 24.0+ or containerd 1.6+
- Kubernetes 1.26+ (for K8s deployments)
- kubectl 1.26+
- Helm 3.10+ (optional, for chart-based deployments)

#### Optional

- Terraform 1.5+ (for infrastructure as code)
- Ansible 2.14+ (for configuration management)
- Prometheus Operator (for advanced monitoring)
- cert-manager (for automatic TLS certificate management)

### Accounts and Access

- **Container Registry:** Docker Hub, ECR, GCR, or ACR
- **Cloud Provider:** AWS, GCP, Azure, or DigitalOcean (for managed Kubernetes)
- **Monitoring:** Grafana Cloud (optional)
- **Logging:** ELK Stack or cloud-based logging service
- **Secret Management:** HashiCorp Vault, AWS Secrets Manager, or similar

### Network Requirements

#### Ports

- **8000** - API HTTP endpoint
- **8001** - Metrics endpoint
- **6379** - Redis (internal)
- **8001** - ChromaDB (internal)
- **9090** - Prometheus (internal)
- **3000** - Grafana
- **443** - HTTPS (public-facing)

#### Firewall Rules

```bash
# Allow HTTPS traffic
sudo ufw allow 443/tcp

# Allow API traffic (if needed)
sudo ufw allow 8000/tcp

# Allow monitoring (restricted to specific IPs)
sudo ufw allow from 10.0.0.0/8 to any port 3000
sudo ufw allow from 10.0.0.0/8 to any port 9090
```

---

## Architecture

### High-Level Architecture

```
                        ┌─────────────────┐
                        │  Load Balancer  │
                        │  (NGINX/ALB)    │
                        └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
              ┌─────▼─────┐           ┌──────▼──────┐
              │   API     │           │    API      │
              │  Pod 1    │           │   Pod 2     │
              └─────┬─────┘           └──────┬──────┘
                    │                         │
                    └────────────┬────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
            ┌───────▼────────┐       ┌───────▼────────┐
            │   ChromaDB     │       │     Redis      │
            │   (Vector DB)  │       │    (Cache)     │
            └────────────────┘       └────────────────┘
```

### Component Architecture

#### API Layer

- **Technology:** FastAPI + Uvicorn + Gunicorn
- **Replicas:** 3+ (auto-scaled)
- **Resources:** 500m CPU, 512Mi RAM (request), 1 CPU, 1Gi RAM (limit)
- **Health Checks:** Liveness, Readiness, Startup probes

#### Data Layer

##### ChromaDB (Vector Database)

- **Technology:** ChromaDB 0.4.22
- **Replicas:** 1 (stateful)
- **Persistence:** Persistent Volume (100 GB)
- **Backup:** Daily snapshots

##### Redis (Cache & Session Store)

- **Technology:** Redis 7.2 Alpine
- **Replicas:** 1 (with optional Redis Sentinel for HA)
- **Persistence:** AOF + RDB snapshots
- **Backup:** Hourly snapshots

#### Observability Layer

##### Prometheus (Metrics)

- **Retention:** 30 days
- **Storage:** 50 GB
- **Scrape Interval:** 15 seconds

##### Grafana (Visualization)

- **Dashboards:** Pre-configured for KnowledgeBeast
- **Alerts:** 20+ pre-configured alerts

##### Jaeger (Tracing)

- **Storage:** Badger (local) or Elasticsearch (production)
- **Retention:** 7 days

### Network Architecture

#### Internal Network

- **Subnet:** 172.20.0.0/16
- **Service Discovery:** Kubernetes DNS or Docker DNS
- **Service Mesh:** (Optional) Istio or Linkerd

#### External Access

- **Ingress:** NGINX Ingress Controller with TLS
- **Rate Limiting:** 100 requests/minute per IP
- **DDoS Protection:** Cloudflare or AWS Shield

---

## Docker Deployment

### Quick Start (Single-Node)

#### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/knowledgebeast.git
cd knowledgebeast
git checkout v2.3.0
```

#### Step 2: Configure Environment

```bash
# Copy environment template
cp .env.production.template .env.production

# Edit configuration
nano .env.production
```

Required environment variables:

```bash
# Application
APP_ENV=production
LOG_LEVEL=INFO
SECRET_KEY=your_random_64_char_secret_key_here
JWT_SECRET=your_random_64_char_jwt_secret_here

# Redis
REDIS_PASSWORD=your_secure_redis_password

# ChromaDB
CHROMA_AUTH_TOKEN=your_chromadb_auth_token

# Observability
GRAFANA_USER=admin
GRAFANA_PASSWORD=your_secure_grafana_password
```

#### Step 3: Build Production Image

```bash
# Build the production image
docker build -f docker/Dockerfile.production -t knowledgebeast:2.3.0 .

# Verify image size (should be < 500MB)
docker images knowledgebeast:2.3.0
```

Expected output:
```
REPOSITORY       TAG     IMAGE ID       CREATED          SIZE
knowledgebeast   2.3.0   abc123def456   10 seconds ago   450MB
```

#### Step 4: Deploy with Docker Compose

```bash
# Deploy the full stack
docker-compose -f docker/docker-compose.prod.yml up -d

# Verify all services are running
docker-compose -f docker/docker-compose.prod.yml ps
```

Expected output:
```
NAME                          STATUS   PORTS
knowledgebeast-api            Up       0.0.0.0:8000->8000/tcp
knowledgebeast-chromadb       Up       8001:8000/tcp
knowledgebeast-redis          Up       6379:6379/tcp
knowledgebeast-prometheus     Up       9090:9090/tcp
knowledgebeast-grafana        Up       3000:3000/tcp
knowledgebeast-jaeger         Up       16686:16686/tcp
```

#### Step 5: Verify Deployment

```bash
# Check API health
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"2.3.0","timestamp":"2025-10-09T12:00:00Z"}

# Check metrics endpoint
curl http://localhost:8001/metrics

# Run a test query
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is KnowledgeBeast?", "top_k": 5}'
```

### Multi-Node Docker Swarm Deployment

#### Step 1: Initialize Docker Swarm

```bash
# On manager node
docker swarm init --advertise-addr <MANAGER-IP>

# Save the join token
docker swarm join-token worker
```

#### Step 2: Add Worker Nodes

```bash
# On each worker node, run the join command
docker swarm join --token <TOKEN> <MANAGER-IP>:2377
```

#### Step 3: Create Overlay Network

```bash
# Create overlay network for multi-host communication
docker network create --driver overlay --attachable knowledgebeast-net
```

#### Step 4: Deploy Stack

```bash
# Convert docker-compose to swarm stack
docker stack deploy -c docker/docker-compose.prod.yml knowledgebeast

# Verify services
docker service ls
```

#### Step 5: Scale Services

```bash
# Scale API to 5 replicas
docker service scale knowledgebeast_api=5

# Verify scaling
docker service ps knowledgebeast_api
```

### Advanced Docker Configuration

#### Custom Logging Driver

```yaml
services:
  api:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
        labels: "app,environment"
```

#### Resource Constraints

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

#### Health Check Configuration

```yaml
services:
  api:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 40s
```

---

## Kubernetes Deployment

### Prerequisites

#### Install kubectl

```bash
# Linux
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Verify installation
kubectl version --client
```

#### Configure kubectl

```bash
# For AWS EKS
aws eks update-kubeconfig --region us-west-2 --name knowledgebeast-cluster

# For GCP GKE
gcloud container clusters get-credentials knowledgebeast-cluster --region us-west1

# For Azure AKS
az aks get-credentials --resource-group knowledgebeast-rg --name knowledgebeast-cluster

# Verify connection
kubectl cluster-info
kubectl get nodes
```

### Quick Start (Single-Command Deployment)

```bash
# Clone repository
git clone https://github.com/yourusername/knowledgebeast.git
cd knowledgebeast/kubernetes

# Create namespace
kubectl apply -f namespace.yaml

# Create secrets (edit secret.yaml first!)
cp secret.yaml.template secret.yaml
# IMPORTANT: Edit secret.yaml with actual secret values
kubectl apply -f secret.yaml

# Deploy all resources
kubectl apply -f .

# Verify deployment
kubectl -n knowledgebeast get all
```

### Step-by-Step Kubernetes Deployment

#### Step 1: Create Namespace

```bash
kubectl apply -f kubernetes/namespace.yaml

# Verify namespace
kubectl get namespace knowledgebeast
```

#### Step 2: Create Secrets

```bash
# Generate random secrets
export SECRET_KEY=$(openssl rand -hex 32)
export JWT_SECRET=$(openssl rand -hex 32)
export REDIS_PASSWORD=$(openssl rand -hex 16)

# Create secret from template
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: knowledgebeast-secrets
  namespace: knowledgebeast
type: Opaque
stringData:
  SECRET_KEY: "$SECRET_KEY"
  JWT_SECRET: "$JWT_SECRET"
  redis-password: "$REDIS_PASSWORD"
EOF

# Verify secret creation
kubectl -n knowledgebeast get secrets
```

#### Step 3: Create ConfigMaps

```bash
# Apply configuration
kubectl apply -f kubernetes/configmap.yaml

# Verify ConfigMap
kubectl -n knowledgebeast describe configmap knowledgebeast-config
```

#### Step 4: Create Persistent Volumes

```bash
# Create storage class (if not exists)
kubectl apply -f kubernetes/pvc.yaml

# Verify PVCs
kubectl -n knowledgebeast get pvc
```

Expected output:
```
NAME                       STATUS   VOLUME                 CAPACITY   ACCESS MODES
knowledgebeast-data-pvc    Bound    pvc-xxx-yyy-zzz        50Gi       RWO
chromadb-data-pvc          Bound    pvc-aaa-bbb-ccc        100Gi      RWO
redis-data-pvc             Bound    pvc-ddd-eee-fff        20Gi       RWO
```

#### Step 5: Deploy Application

```bash
# Deploy all components
kubectl apply -f kubernetes/deployment.yaml

# Watch deployment progress
kubectl -n knowledgebeast rollout status deployment/knowledgebeast-api

# Verify pods are running
kubectl -n knowledgebeast get pods
```

Expected output:
```
NAME                                     READY   STATUS    RESTARTS   AGE
knowledgebeast-api-7d8f9b5c4-abc12      1/1     Running   0          2m
knowledgebeast-api-7d8f9b5c4-def34      1/1     Running   0          2m
knowledgebeast-api-7d8f9b5c4-ghi56      1/1     Running   0          2m
knowledgebeast-chromadb-5c8d9f6a-jkl78  1/1     Running   0          2m
knowledgebeast-redis-6d9e0a7b-mno90     1/1     Running   0          2m
```

#### Step 6: Create Services

```bash
# Create services
kubectl apply -f kubernetes/service.yaml

# Verify services
kubectl -n knowledgebeast get svc
```

Expected output:
```
NAME                          TYPE           EXTERNAL-IP      PORT(S)
knowledgebeast-api            LoadBalancer   34.123.45.67     80:30000/TCP,443:30001/TCP
knowledgebeast-api-internal   ClusterIP      None             8000/TCP
knowledgebeast-chromadb       ClusterIP      10.100.10.10     8000/TCP
knowledgebeast-redis          ClusterIP      10.100.10.11     6379/TCP
```

#### Step 7: Configure Ingress

```bash
# Install NGINX Ingress Controller (if not already installed)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.9.4/deploy/static/provider/cloud/deploy.yaml

# Install cert-manager for TLS
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.2/cert-manager.yaml

# Create ClusterIssuer for Let's Encrypt
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF

# Apply ingress configuration
kubectl apply -f kubernetes/ingress.yaml

# Get ingress IP
kubectl -n knowledgebeast get ingress
```

#### Step 8: Enable Auto-Scaling

```bash
# Install Metrics Server (if not already installed)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Apply HPA configuration
kubectl apply -f kubernetes/hpa.yaml

# Verify HPA
kubectl -n knowledgebeast get hpa
```

Expected output:
```
NAME                      REFERENCE                       TARGETS         MINPODS   MAXPODS   REPLICAS
knowledgebeast-api-hpa    Deployment/knowledgebeast-api   45%/70%         2         10        3
```

#### Step 9: Verify Deployment

```bash
# Check all resources
kubectl -n knowledgebeast get all

# Check pod logs
kubectl -n knowledgebeast logs -l app=knowledgebeast,component=api --tail=100

# Test API endpoint
export API_ENDPOINT=$(kubectl -n knowledgebeast get ingress knowledgebeast-ingress -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl http://$API_ENDPOINT/health
```

### Helm Chart Deployment (Alternative)

#### Step 1: Add Helm Repository

```bash
# Add KnowledgeBeast Helm repository
helm repo add knowledgebeast https://charts.knowledgebeast.com
helm repo update
```

#### Step 2: Create values.yaml

```yaml
# values.yaml
image:
  repository: knowledgebeast
  tag: "2.3.0"
  pullPolicy: IfNotPresent

replicaCount: 3

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 500m
    memory: 512Mi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: api.knowledgebeast.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: knowledgebeast-tls
      hosts:
        - api.knowledgebeast.com

chromadb:
  enabled: true
  persistence:
    size: 100Gi

redis:
  enabled: true
  auth:
    enabled: true
  persistence:
    size: 20Gi
```

#### Step 3: Install Chart

```bash
# Install KnowledgeBeast
helm install knowledgebeast knowledgebeast/knowledgebeast \
  --namespace knowledgebeast \
  --create-namespace \
  --values values.yaml

# Verify installation
helm list -n knowledgebeast
kubectl -n knowledgebeast get all
```

#### Step 4: Upgrade Deployment

```bash
# Upgrade to new version
helm upgrade knowledgebeast knowledgebeast/knowledgebeast \
  --namespace knowledgebeast \
  --values values.yaml \
  --set image.tag=2.3.1

# Rollback if needed
helm rollback knowledgebeast -n knowledgebeast
```

### Multi-Region Kubernetes Deployment

#### Architecture Overview

```
Region 1 (us-west-2)          Region 2 (us-east-1)
┌──────────────────┐          ┌──────────────────┐
│  K8s Cluster 1   │          │  K8s Cluster 2   │
│  ┌────────────┐  │          │  ┌────────────┐  │
│  │ API Pods   │  │          │  │ API Pods   │  │
│  └────────────┘  │          │  └────────────┘  │
│  ┌────────────┐  │          │  ┌────────────┐  │
│  │ ChromaDB   │  │          │  │ ChromaDB   │  │
│  └────────────┘  │          │  └────────────┘  │
└────────┬─────────┘          └─────────┬────────┘
         │                              │
         └──────────┬───────────────────┘
                    │
              ┌─────▼─────┐
              │  Global   │
              │    LB     │
              └───────────┘
```

#### Step 1: Deploy to First Region

```bash
# Configure kubectl for first cluster
aws eks update-kubeconfig --region us-west-2 --name knowledgebeast-us-west-2

# Deploy application
kubectl apply -f kubernetes/
```

#### Step 2: Deploy to Second Region

```bash
# Configure kubectl for second cluster
aws eks update-kubeconfig --region us-east-1 --name knowledgebeast-us-east-1

# Deploy application
kubectl apply -f kubernetes/
```

#### Step 3: Configure Global Load Balancer

For AWS:
```bash
# Create Route53 health checks and routing
aws route53 create-health-check \
  --health-check-config "IPAddress=<CLUSTER1-IP>,Port=443,Type=HTTPS,ResourcePath=/health"

# Create latency-based routing
# See AWS Route53 documentation for complete setup
```

For GCP:
```bash
# Create global HTTP(S) load balancer
gcloud compute backend-services create knowledgebeast-backend \
  --global \
  --protocol=HTTP \
  --health-checks=knowledgebeast-health-check
```

---

## Configuration Management

### Environment Variables

#### Application Configuration

```bash
# Core application settings
APP_ENV=production                    # Environment: production, staging, development
LOG_LEVEL=INFO                        # Logging level: DEBUG, INFO, WARN, ERROR
WORKERS=4                             # Number of worker processes
PYTHONUNBUFFERED=1                    # Disable Python output buffering

# Security
SECRET_KEY=<64-char-random-string>    # Application secret key
JWT_SECRET=<64-char-random-string>    # JWT signing secret
API_KEY=<your-api-key>                # API authentication key
ALLOWED_HOSTS=*                       # Comma-separated allowed hosts
CORS_ORIGINS=https://app.example.com  # Comma-separated CORS origins

# Database configuration
CHROMA_HOST=chromadb                  # ChromaDB hostname
CHROMA_PORT=8000                      # ChromaDB port
CHROMA_AUTH_TOKEN=<auth-token>        # ChromaDB authentication token

# Redis configuration
REDIS_HOST=redis                      # Redis hostname
REDIS_PORT=6379                       # Redis port
REDIS_PASSWORD=<password>             # Redis password
REDIS_DB=0                            # Redis database number

# Performance tuning
CACHE_TTL=3600                        # Cache TTL in seconds
MAX_CONCURRENT_QUERIES=100            # Max concurrent queries
QUERY_TIMEOUT=30                      # Query timeout in seconds
CONNECTION_POOL_SIZE=20               # Database connection pool size

# Observability
PROMETHEUS_ENABLED=true               # Enable Prometheus metrics
PROMETHEUS_PORT=8001                  # Metrics port
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318  # OpenTelemetry endpoint
```

### Configuration Files

#### app.yaml

Location: `/app/config/app.yaml`

```yaml
# KnowledgeBeast Application Configuration
version: "2.3.0"

server:
  host: "0.0.0.0"
  port: 8000
  workers: 4
  timeout: 60
  keepalive: 5

database:
  chromadb:
    host: "chromadb"
    port: 8000
    collection_name: "knowledgebeast"
    batch_size: 100

cache:
  redis:
    host: "redis"
    port: 6379
    db: 0
    max_connections: 50
    socket_timeout: 5

chunking:
  default_strategy: "semantic"
  default_chunk_size: 512
  default_overlap: 50
  max_chunk_size: 2048

embedding:
  model: "all-MiniLM-L6-v2"
  dimension: 384
  batch_size: 32

reranking:
  enabled: true
  model: "cross-encoder/ms-marco-MiniLM-L-6-v2"
  top_k: 10

observability:
  metrics:
    enabled: true
    port: 8001
  tracing:
    enabled: true
    sample_rate: 0.1
  logging:
    level: "INFO"
    format: "json"
```

### Secret Management

#### Using Kubernetes Secrets

```bash
# Create secret from literal values
kubectl create secret generic knowledgebeast-secrets \
  --from-literal=SECRET_KEY=your-secret-key \
  --from-literal=JWT_SECRET=your-jwt-secret \
  --from-literal=REDIS_PASSWORD=your-redis-password \
  -n knowledgebeast

# Create secret from file
kubectl create secret generic knowledgebeast-secrets \
  --from-file=secret-key=./secret-key.txt \
  --from-file=jwt-secret=./jwt-secret.txt \
  -n knowledgebeast

# Create TLS secret
kubectl create secret tls knowledgebeast-tls \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key \
  -n knowledgebeast
```

#### Using HashiCorp Vault

```bash
# Install Vault Helm chart
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault -n vault --create-namespace

# Enable Kubernetes authentication
vault auth enable kubernetes

# Create policy
vault policy write knowledgebeast - <<EOF
path "secret/data/knowledgebeast/*" {
  capabilities = ["read"]
}
EOF

# Store secrets
vault kv put secret/knowledgebeast/production \
  SECRET_KEY="your-secret-key" \
  JWT_SECRET="your-jwt-secret"
```

#### Using AWS Secrets Manager

```bash
# Create secret
aws secretsmanager create-secret \
  --name knowledgebeast/production/credentials \
  --secret-string '{"SECRET_KEY":"your-key","JWT_SECRET":"your-jwt"}'

# Create IAM role for pod
aws iam create-role --role-name KnowledgeBeastPodRole \
  --assume-role-policy-document file://trust-policy.json

# Attach policy
aws iam attach-role-policy \
  --role-name KnowledgeBeastPodRole \
  --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite
```

---

## Monitoring and Observability

### Prometheus Setup

#### Install Prometheus

```bash
# Using Helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/prometheus \
  --namespace knowledgebeast \
  --set server.persistentVolume.size=50Gi \
  --set server.retention=30d
```

#### Configure Scrape Jobs

Edit `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'knowledgebeast-api'
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
            - knowledgebeast
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
```

#### Key Metrics to Monitor

```promql
# Request rate
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# Request latency (P95)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# CPU usage
rate(process_cpu_seconds_total[5m])

# Memory usage
process_resident_memory_bytes

# Cache hit rate
rate(cache_hits_total[5m]) / rate(cache_requests_total[5m])
```

### Grafana Setup

#### Install Grafana

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm install grafana grafana/grafana \
  --namespace knowledgebeast \
  --set persistence.enabled=true \
  --set persistence.size=10Gi \
  --set adminPassword='your-secure-password'
```

#### Import Dashboards

```bash
# Get Grafana admin password
kubectl get secret --namespace knowledgebeast grafana \
  -o jsonpath="{.data.admin-password}" | base64 --decode ; echo

# Port-forward to access Grafana
kubectl port-forward -n knowledgebeast svc/grafana 3000:80
```

Access Grafana at `http://localhost:3000` and import pre-built dashboards:

1. **KnowledgeBeast Overview** (ID: 1001)
   - Request rate, latency, error rate
   - Resource utilization (CPU, memory)
   - Cache performance

2. **API Performance** (ID: 1002)
   - Endpoint-specific metrics
   - Slow query analysis
   - Error breakdown

3. **Infrastructure** (ID: 1003)
   - Pod health and status
   - Node resource usage
   - Network traffic

### Alerting Configuration

#### Prometheus Alerts

Create `alerts.yml`:

```yaml
groups:
  - name: knowledgebeast_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} requests/sec"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
          description: "P95 latency is {{ $value }}s"

      - alert: PodCrashLooping
        expr: rate(kube_pod_container_status_restarts_total{namespace="knowledgebeast"}[15m]) > 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Pod is crash looping"
```

#### Alertmanager Configuration

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
    - match:
        severity: warning
      receiver: 'slack'

receivers:
  - name: 'default'
    email_configs:
      - to: 'alerts@example.com'
        from: 'alertmanager@example.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'alertmanager@example.com'
        auth_password: 'password'

  - name: 'slack'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#alerts'
        title: 'KnowledgeBeast Alert'

  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: 'your-pagerduty-service-key'
```

### Distributed Tracing

#### Jaeger Setup

```bash
# Deploy Jaeger
kubectl apply -f https://raw.githubusercontent.com/jaegertracing/jaeger-operator/main/deploy/crds/jaegertracing.io_jaegers_crd.yaml
kubectl apply -f https://raw.githubusercontent.com/jaegertracing/jaeger-operator/main/deploy/operator.yaml

# Create Jaeger instance
cat <<EOF | kubectl apply -f -
apiVersion: jaegertracing.io/v1
kind: Jaeger
metadata:
  name: knowledgebeast-jaeger
  namespace: knowledgebeast
spec:
  strategy: production
  storage:
    type: elasticsearch
    options:
      es:
        server-urls: http://elasticsearch:9200
EOF
```

#### Instrument Application

Ensure OpenTelemetry is configured in your application:

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configure tracer
trace.set_tracer_provider(TracerProvider())
otlp_exporter = OTLPSpanExporter(
    endpoint="http://jaeger:4318/v1/traces"
)
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(otlp_exporter)
)
```

### Log Aggregation

#### ELK Stack Setup

```bash
# Install Elasticsearch
helm repo add elastic https://helm.elastic.co
helm install elasticsearch elastic/elasticsearch \
  --namespace knowledgebeast \
  --set replicas=1 \
  --set volumeClaimTemplate.resources.requests.storage=100Gi

# Install Kibana
helm install kibana elastic/kibana \
  --namespace knowledgebeast

# Install Filebeat for log collection
helm install filebeat elastic/filebeat \
  --namespace knowledgebeast \
  --set filebeatConfig."filebeat\.yml"='
filebeat.inputs:
- type: container
  paths:
    - /var/log/containers/*.log
  processors:
    - add_kubernetes_metadata:
        host: ${NODE_NAME}
        matchers:
        - logs_path:
            logs_path: "/var/log/containers/"

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
'
```

---

## Security Hardening

### Container Security

#### Non-Root User

Ensure containers run as non-root (already configured in Dockerfile):

```dockerfile
# Create non-root user
RUN groupadd -r appuser --gid=1000 && \
    useradd -r -g appuser --uid=1000 appuser

USER appuser
```

#### Read-Only Root Filesystem

```yaml
securityContext:
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
```

#### Security Scanning

```bash
# Scan Docker image with Trivy
trivy image knowledgebeast:2.3.0

# Scan for vulnerabilities
docker scan knowledgebeast:2.3.0

# Use Snyk
snyk container test knowledgebeast:2.3.0
```

### Network Security

#### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: knowledgebeast-network-policy
  namespace: knowledgebeast
spec:
  podSelector:
    matchLabels:
      app: knowledgebeast
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow from ingress controller
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8000
    # Allow from same namespace
    - from:
        - podSelector: {}
  egress:
    # Allow to ChromaDB
    - to:
        - podSelector:
            matchLabels:
              component: chromadb
      ports:
        - protocol: TCP
          port: 8000
    # Allow to Redis
    - to:
        - podSelector:
            matchLabels:
              component: redis
      ports:
        - protocol: TCP
          port: 6379
    # Allow DNS
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
```

#### TLS/SSL Configuration

```bash
# Generate self-signed certificate (for testing)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=api.knowledgebeast.com"

# Create TLS secret
kubectl create secret tls knowledgebeast-tls \
  --cert=tls.crt \
  --key=tls.key \
  -n knowledgebeast

# Use Let's Encrypt (recommended for production)
# Ensure cert-manager is installed and configured
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: knowledgebeast-cert
  namespace: knowledgebeast
spec:
  secretName: knowledgebeast-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - api.knowledgebeast.com
EOF
```

### Authentication and Authorization

#### API Key Authentication

```python
# Configure API key middleware
from fastapi import Security, HTTPException
from fastapi.security.api_key import APIKeyHeader

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key != settings.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key
```

#### JWT Authentication

```python
from jose import JWTError, jwt
from datetime import datetime, timedelta

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
    return encoded_jwt
```

#### RBAC in Kubernetes

See `kubernetes/rbac.yaml` for complete RBAC configuration.

### Data Encryption

#### At Rest

```yaml
# Enable encryption for PVCs
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: encrypted-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
  storageClassName: encrypted-gp3  # Use encrypted storage class
```

#### In Transit

All internal communication should use TLS:

```yaml
# ChromaDB with TLS
env:
  - name: CHROMA_SERVER_SSL_ENABLED
    value: "true"
  - name: CHROMA_SERVER_SSL_CERT
    value: "/certs/tls.crt"
  - name: CHROMA_SERVER_SSL_KEY
    value: "/certs/tls.key"
```

### Security Checklist

- [ ] All containers run as non-root
- [ ] Read-only root filesystem enabled
- [ ] Network policies configured
- [ ] TLS enabled for all external endpoints
- [ ] Secrets stored in secret management system (not in code)
- [ ] Regular security scans performed
- [ ] RBAC configured with least privilege
- [ ] Pod Security Policies/Standards enforced
- [ ] Audit logging enabled
- [ ] Regular security updates applied

---

## Performance Tuning

### Application-Level Tuning

#### Worker Configuration

```bash
# Optimal worker count = (2 x CPU cores) + 1
WORKERS=9  # For 4-core system

# Connection limits
MAX_CONCURRENT_QUERIES=100
QUERY_TIMEOUT=30
```

#### Connection Pooling

```python
# Redis connection pool
REDIS_POOL_SIZE=50
REDIS_POOL_MAX_OVERFLOW=10

# Database connection pool
DB_POOL_SIZE=20
DB_POOL_MAX_OVERFLOW=10
```

#### Caching Strategy

```python
# Query cache configuration
CACHE_TTL=3600  # 1 hour
QUERY_CACHE_SIZE=1000  # Number of queries to cache

# Redis cache configuration
REDIS_CACHE_TTL=7200  # 2 hours
```

### Database Tuning

#### ChromaDB Optimization

```yaml
# Batch size for bulk operations
CHROMA_BATCH_SIZE=100

# Index parameters
HNSW_M=16  # Number of connections per element
HNSW_EF_CONSTRUCTION=200  # Construction-time search parameter
HNSW_EF_SEARCH=100  # Search-time parameter
```

#### Redis Optimization

```conf
# Memory management
maxmemory 512mb
maxmemory-policy allkeys-lru

# Persistence
save 900 1    # Save after 900 seconds if at least 1 key changed
save 300 10   # Save after 300 seconds if at least 10 keys changed
save 60 10000 # Save after 60 seconds if at least 10000 keys changed

# AOF configuration
appendonly yes
appendfsync everysec
```

### Kubernetes Resource Optimization

#### CPU and Memory Requests/Limits

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

Best practices:
- Set requests to typical usage
- Set limits to maximum acceptable usage
- Monitor actual usage and adjust accordingly

#### Horizontal Pod Autoscaling

```yaml
metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70

  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### Vertical Pod Autoscaling

```yaml
updatePolicy:
  updateMode: "Auto"

resourcePolicy:
  containerPolicies:
    - containerName: api
      minAllowed:
        cpu: 250m
        memory: 256Mi
      maxAllowed:
        cpu: 2000m
        memory: 2Gi
```

### Load Balancing

#### NGINX Configuration

```nginx
upstream knowledgebeast_backend {
    least_conn;  # Use least connections algorithm
    server 10.0.1.10:8000 max_fails=3 fail_timeout=30s;
    server 10.0.1.11:8000 max_fails=3 fail_timeout=30s;
    server 10.0.1.12:8000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

server {
    listen 80;
    server_name api.knowledgebeast.com;

    location / {
        proxy_pass http://knowledgebeast_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Buffering
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }
}
```

### Performance Benchmarking

#### Load Testing with k6

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 100 },  // Ramp up to 100 users
    { duration: '5m', target: 100 },  // Stay at 100 users
    { duration: '2m', target: 200 },  // Ramp up to 200 users
    { duration: '5m', target: 200 },  // Stay at 200 users
    { duration: '2m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% of requests under 500ms
    http_req_failed: ['rate<0.01'],    // Less than 1% errors
  },
};

export default function () {
  const payload = JSON.stringify({
    query: 'What is KnowledgeBeast?',
    top_k: 5,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': 'your-api-key',
    },
  };

  const res = http.post('https://api.knowledgebeast.com/api/v1/query', payload, params);

  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });

  sleep(1);
}
```

Run the test:
```bash
k6 run --vus 100 --duration 30s load-test.js
```

---

## Backup and Disaster Recovery

### Backup Strategy

#### Data Backup Schedule

- **Full Backups:** Daily at 2 AM UTC
- **Incremental Backups:** Every 6 hours
- **Retention:** 30 days for daily, 7 days for incremental
- **Backup Location:** S3/GCS/Azure Blob Storage (encrypted)

#### Backup Components

1. **ChromaDB Data**
   - Vector embeddings
   - Metadata
   - Collections

2. **Configuration**
   - Kubernetes ConfigMaps
   - Secrets (encrypted)
   - Application config files

3. **Logs** (optional)
   - Application logs
   - Audit logs

### Kubernetes Backup with Velero

#### Install Velero

```bash
# Download Velero
wget https://github.com/vmware-tanzu/velero/releases/download/v1.12.0/velero-v1.12.0-linux-amd64.tar.gz
tar -xvf velero-v1.12.0-linux-amd64.tar.gz
sudo mv velero-v1.12.0-linux-amd64/velero /usr/local/bin/

# Install Velero in cluster (AWS example)
velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:v1.8.0 \
  --bucket knowledgebeast-backups \
  --secret-file ./credentials-velero \
  --backup-location-config region=us-west-2 \
  --snapshot-location-config region=us-west-2
```

#### Create Backup Schedule

```bash
# Create daily backup schedule
velero schedule create knowledgebeast-daily \
  --schedule="0 2 * * *" \
  --include-namespaces knowledgebeast \
  --ttl 720h0m0s

# Create hourly backup for critical data
velero schedule create knowledgebeast-hourly \
  --schedule="0 * * * *" \
  --include-namespaces knowledgebeast \
  --include-resources pvc,secrets,configmaps \
  --ttl 168h0m0s

# Verify schedules
velero schedule get
```

#### Manual Backup

```bash
# Create on-demand backup
velero backup create knowledgebeast-manual-$(date +%Y%m%d-%H%M%S) \
  --include-namespaces knowledgebeast \
  --wait

# Check backup status
velero backup describe knowledgebeast-manual-<timestamp>

# List all backups
velero backup get
```

### Restore Procedures

#### Full Cluster Restore

```bash
# List available backups
velero backup get

# Restore from backup
velero restore create --from-backup knowledgebeast-daily-20251009

# Monitor restore progress
velero restore describe <restore-name>

# Verify restoration
kubectl -n knowledgebeast get all
```

#### Selective Restore

```bash
# Restore only specific resources
velero restore create --from-backup knowledgebeast-daily-20251009 \
  --include-resources deployment,service,pvc

# Restore to different namespace
velero restore create --from-backup knowledgebeast-daily-20251009 \
  --namespace-mappings knowledgebeast:knowledgebeast-restore
```

### Database Backup

#### ChromaDB Backup

```bash
# Create snapshot of ChromaDB PVC
kubectl exec -n knowledgebeast deployment/knowledgebeast-chromadb -- \
  tar -czf /tmp/chromadb-backup-$(date +%Y%m%d).tar.gz /chroma/chroma

# Copy backup to local machine
kubectl cp knowledgebeast/knowledgebeast-chromadb-pod:/tmp/chromadb-backup-*.tar.gz \
  ./chromadb-backup-$(date +%Y%m%d).tar.gz

# Upload to S3
aws s3 cp chromadb-backup-$(date +%Y%m%d).tar.gz \
  s3://knowledgebeast-backups/chromadb/
```

#### Redis Backup

```bash
# Trigger Redis BGSAVE
kubectl exec -n knowledgebeast deployment/knowledgebeast-redis -- redis-cli BGSAVE

# Copy RDB file
kubectl cp knowledgebeast/knowledgebeast-redis-pod:/data/dump.rdb \
  ./redis-backup-$(date +%Y%m%d).rdb

# Upload to S3
aws s3 cp redis-backup-$(date +%Y%m%d).rdb \
  s3://knowledgebeast-backups/redis/
```

### Automated Backup Script

```bash
#!/bin/bash
# automated-backup.sh

set -e

NAMESPACE="knowledgebeast"
BACKUP_DIR="/backups/$(date +%Y%m%d)"
S3_BUCKET="s3://knowledgebeast-backups"

mkdir -p "$BACKUP_DIR"

# Backup ChromaDB
echo "Backing up ChromaDB..."
kubectl exec -n "$NAMESPACE" deployment/knowledgebeast-chromadb -- \
  tar -czf /tmp/chromadb.tar.gz /chroma/chroma
kubectl cp "$NAMESPACE"/$(kubectl get pod -n "$NAMESPACE" -l component=chromadb -o jsonpath='{.items[0].metadata.name}'):/tmp/chromadb.tar.gz \
  "$BACKUP_DIR/chromadb.tar.gz"

# Backup Redis
echo "Backing up Redis..."
kubectl exec -n "$NAMESPACE" deployment/knowledgebeast-redis -- redis-cli BGSAVE
sleep 10
kubectl cp "$NAMESPACE"/$(kubectl get pod -n "$NAMESPACE" -l component=redis -o jsonpath='{.items[0].metadata.name}'):/data/dump.rdb \
  "$BACKUP_DIR/dump.rdb"

# Backup Kubernetes resources
echo "Backing up Kubernetes resources..."
kubectl get all,pvc,secrets,configmaps -n "$NAMESPACE" -o yaml > "$BACKUP_DIR/k8s-resources.yaml"

# Upload to S3
echo "Uploading to S3..."
aws s3 sync "$BACKUP_DIR" "$S3_BUCKET/$(date +%Y%m%d)/" --storage-class STANDARD_IA

# Cleanup old local backups (keep 7 days)
find /backups -type d -mtime +7 -exec rm -rf {} \;

echo "Backup completed successfully!"
```

### Disaster Recovery Plan

#### RPO and RTO Targets

- **RPO (Recovery Point Objective):** < 1 hour
- **RTO (Recovery Time Objective):** < 4 hours

#### Recovery Procedures

##### Scenario 1: Single Pod Failure

```bash
# Kubernetes will automatically restart failed pods
# Verify pod status
kubectl -n knowledgebeast get pods

# If needed, manually delete pod to trigger recreation
kubectl -n knowledgebeast delete pod <pod-name>
```

##### Scenario 2: Node Failure

```bash
# Kubernetes will automatically reschedule pods to healthy nodes
# Monitor rescheduling
kubectl -n knowledgebeast get pods -o wide

# If nodes don't recover, cordon failed node
kubectl cordon <node-name>

# Drain node to force pod rescheduling
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
```

##### Scenario 3: Data Corruption

```bash
# Restore from latest backup
velero restore create --from-backup knowledgebeast-daily-<date>

# Verify data integrity
kubectl exec -n knowledgebeast deployment/knowledgebeast-api -- \
  python -m knowledgebeast.tools.verify_data
```

##### Scenario 4: Complete Cluster Failure

```bash
# 1. Provision new cluster
eksctl create cluster -f cluster-config.yaml

# 2. Install Velero
velero install --provider aws --bucket knowledgebeast-backups

# 3. Restore from backup
velero restore create --from-backup knowledgebeast-daily-<latest>

# 4. Verify services
kubectl -n knowledgebeast get all

# 5. Update DNS to point to new cluster
```

### Testing Disaster Recovery

```bash
# Schedule regular DR drills
# 1. Create test namespace
kubectl create namespace knowledgebeast-dr-test

# 2. Restore backup to test namespace
velero restore create --from-backup knowledgebeast-daily-<date> \
  --namespace-mappings knowledgebeast:knowledgebeast-dr-test

# 3. Run validation tests
kubectl -n knowledgebeast-dr-test get all

# 4. Cleanup
kubectl delete namespace knowledgebeast-dr-test
```

---

## Troubleshooting

### Common Issues

#### Issue 1: Pods Not Starting

**Symptoms:**
```bash
kubectl -n knowledgebeast get pods
# Shows pods in Pending or CrashLoopBackOff state
```

**Diagnosis:**
```bash
# Check pod events
kubectl -n knowledgebeast describe pod <pod-name>

# Check logs
kubectl -n knowledgebeast logs <pod-name>

# Check resource availability
kubectl describe nodes
```

**Common Causes:**

1. **Insufficient Resources**
   ```bash
   # Check node capacity
   kubectl describe nodes | grep -A 5 "Allocated resources"

   # Solution: Scale down other workloads or add nodes
   kubectl scale deployment <other-deployment> --replicas=1
   ```

2. **Image Pull Errors**
   ```bash
   # Check image pull secrets
   kubectl -n knowledgebeast get secrets

   # Solution: Create image pull secret
   kubectl create secret docker-registry regcred \
     --docker-server=<registry> \
     --docker-username=<username> \
     --docker-password=<password>
   ```

3. **Failed Health Checks**
   ```bash
   # Check health check configuration
   kubectl -n knowledgebeast get deployment <name> -o yaml | grep -A 10 "livenessProbe"

   # Solution: Adjust health check timings or fix application
   ```

#### Issue 2: High Latency

**Symptoms:**
- API responses taking > 1 second
- Timeouts on client side

**Diagnosis:**
```bash
# Check Prometheus metrics
curl http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,rate(http_request_duration_seconds_bucket[5m]))

# Check pod resource usage
kubectl -n knowledgebeast top pods

# Check database performance
kubectl -n knowledgebeast exec deployment/knowledgebeast-chromadb -- \
  curl localhost:8000/api/v1/heartbeat -w "@curl-format.txt"
```

**Solutions:**

1. **Scale up pods**
   ```bash
   kubectl -n knowledgebeast scale deployment knowledgebeast-api --replicas=5
   ```

2. **Increase resource limits**
   ```bash
   kubectl -n knowledgebeast patch deployment knowledgebeast-api \
     -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"cpu":"2","memory":"2Gi"}}}]}}}}'
   ```

3. **Check cache hit rate**
   ```bash
   # If cache hit rate is low, increase cache size
   kubectl -n knowledgebeast set env deployment/knowledgebeast-api \
     QUERY_CACHE_SIZE=2000
   ```

#### Issue 3: Out of Memory (OOM)

**Symptoms:**
```bash
# Pod killed with OOMKilled status
kubectl -n knowledgebeast get pods
# Shows STATUS: OOMKilled
```

**Diagnosis:**
```bash
# Check memory usage
kubectl -n knowledgebeast top pod <pod-name>

# Check memory limits
kubectl -n knowledgebeast get pod <pod-name> -o jsonpath='{.spec.containers[0].resources}'

# Check OOM events
kubectl -n knowledgebeast get events | grep OOM
```

**Solutions:**

1. **Increase memory limits**
   ```bash
   kubectl -n knowledgebeast patch deployment knowledgebeast-api \
     -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"2Gi"}}}]}}}}'
   ```

2. **Check for memory leaks**
   ```bash
   # Use memory profiler
   kubectl -n knowledgebeast exec deployment/knowledgebeast-api -- \
     python -m memory_profiler /app/app.py
   ```

#### Issue 4: Database Connection Errors

**Symptoms:**
- Errors like "Connection refused" or "Timeout connecting to database"

**Diagnosis:**
```bash
# Test ChromaDB connectivity
kubectl -n knowledgebeast exec deployment/knowledgebeast-api -- \
  curl http://knowledgebeast-chromadb:8000/api/v1/heartbeat

# Test Redis connectivity
kubectl -n knowledgebeast exec deployment/knowledgebeast-api -- \
  redis-cli -h knowledgebeast-redis ping

# Check network policies
kubectl -n knowledgebeast get networkpolicies
```

**Solutions:**

1. **Verify service endpoints**
   ```bash
   kubectl -n knowledgebeast get endpoints
   ```

2. **Check DNS resolution**
   ```bash
   kubectl -n knowledgebeast exec deployment/knowledgebeast-api -- \
     nslookup knowledgebeast-chromadb
   ```

3. **Review network policies**
   ```bash
   kubectl -n knowledgebeast describe networkpolicy
   ```

### Debugging Commands

#### Pod Debugging

```bash
# Get pod details
kubectl -n knowledgebeast describe pod <pod-name>

# View logs
kubectl -n knowledgebeast logs <pod-name> --tail=100 -f

# View previous container logs (if pod crashed)
kubectl -n knowledgebeast logs <pod-name> --previous

# Execute commands in pod
kubectl -n knowledgebeast exec -it <pod-name> -- /bin/bash

# Copy files from pod
kubectl -n knowledgebeast cp <pod-name>:/path/to/file ./local-file
```

#### Service Debugging

```bash
# Check service
kubectl -n knowledgebeast get svc <service-name>

# Describe service
kubectl -n knowledgebeast describe svc <service-name>

# Check endpoints
kubectl -n knowledgebeast get endpoints <service-name>

# Test service from another pod
kubectl -n knowledgebeast run debug --image=curlimages/curl --rm -it -- \
  curl http://<service-name>:8000/health
```

#### Network Debugging

```bash
# Check ingress
kubectl -n knowledgebeast get ingress

# Describe ingress
kubectl -n knowledgebeast describe ingress <ingress-name>

# Check network policies
kubectl -n knowledgebeast get networkpolicies

# Test connectivity
kubectl -n knowledgebeast run netshoot --image=nicolaka/netshoot --rm -it -- /bin/bash
```

### Log Analysis

#### Application Logs

```bash
# Search for errors
kubectl -n knowledgebeast logs -l app=knowledgebeast --tail=1000 | grep ERROR

# Filter by timestamp
kubectl -n knowledgebeast logs <pod-name> --since=1h

# Export logs
kubectl -n knowledgebeast logs <pod-name> > app.log
```

#### Aggregated Logging with ELK

```bash
# Query Elasticsearch
curl -X GET "localhost:9200/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "bool": {
      "must": [
        { "match": { "kubernetes.namespace": "knowledgebeast" }},
        { "match": { "level": "ERROR" }}
      ]
    }
  },
  "sort": [{ "@timestamp": { "order": "desc" }}],
  "size": 100
}
'
```

### Performance Profiling

#### CPU Profiling

```bash
# Install py-spy
kubectl -n knowledgebeast exec deployment/knowledgebeast-api -- \
  pip install py-spy

# Profile running process
kubectl -n knowledgebeast exec deployment/knowledgebeast-api -- \
  py-spy top --pid 1

# Generate flame graph
kubectl -n knowledgebeast exec deployment/knowledgebeast-api -- \
  py-spy record -o profile.svg --pid 1 --duration 60
```

#### Memory Profiling

```bash
# Install memory-profiler
kubectl -n knowledgebeast exec deployment/knowledgebeast-api -- \
  pip install memory-profiler

# Profile memory usage
kubectl -n knowledgebeast exec deployment/knowledgebeast-api -- \
  python -m memory_profiler /app/app.py
```

---

## Production Checklist

### Pre-Deployment Checklist

#### Infrastructure

- [ ] Kubernetes cluster provisioned and configured
- [ ] Storage classes configured (SSD for performance)
- [ ] LoadBalancer/Ingress controller installed
- [ ] DNS configured and tested
- [ ] TLS certificates obtained (Let's Encrypt or commercial)
- [ ] Firewall rules configured
- [ ] VPC/Network configured with proper subnets

#### Security

- [ ] All secrets stored in secret management system
- [ ] RBAC configured with least privilege principle
- [ ] Network policies defined and tested
- [ ] Pod security policies/standards enforced
- [ ] Container images scanned for vulnerabilities
- [ ] Non-root containers configured
- [ ] TLS enabled for all external endpoints
- [ ] API authentication configured
- [ ] Rate limiting configured

#### Monitoring & Observability

- [ ] Prometheus installed and configured
- [ ] Grafana installed with dashboards imported
- [ ] Alertmanager configured with notification channels
- [ ] Jaeger/distributed tracing configured
- [ ] Log aggregation setup (ELK or similar)
- [ ] Uptime monitoring configured
- [ ] Synthetic monitoring configured

#### Backup & DR

- [ ] Velero installed and configured
- [ ] Backup schedules created
- [ ] Backup storage configured (S3/GCS/Azure)
- [ ] Disaster recovery plan documented
- [ ] DR drill scheduled
- [ ] RPO/RTO targets defined

#### Performance

- [ ] Resource requests and limits configured
- [ ] HPA configured and tested
- [ ] Load testing performed
- [ ] Performance benchmarks documented
- [ ] Caching strategy implemented
- [ ] Database indexes optimized

### Post-Deployment Checklist

#### Verification

- [ ] All pods running and healthy
- [ ] Health checks passing
- [ ] API endpoints accessible
- [ ] Database connections working
- [ ] Cache functioning correctly
- [ ] Metrics being collected
- [ ] Logs being aggregated

#### Testing

- [ ] Smoke tests passed
- [ ] Integration tests passed
- [ ] Load tests passed
- [ ] Failover tests passed
- [ ] Backup/restore tested

#### Documentation

- [ ] Runbook created
- [ ] Architecture diagram updated
- [ ] Configuration documented
- [ ] Operational procedures documented
- [ ] Troubleshooting guide updated
- [ ] Team training completed

#### Operational

- [ ] On-call rotation defined
- [ ] Escalation procedures documented
- [ ] Maintenance window scheduled
- [ ] Capacity planning completed
- [ ] Cost monitoring configured
- [ ] Compliance requirements met

---

## Appendix

### A. Environment Variables Reference

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `APP_ENV` | Application environment | `production` | Yes |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `WORKERS` | Number of workers | `4` | No |
| `SECRET_KEY` | Application secret | - | Yes |
| `JWT_SECRET` | JWT signing secret | - | Yes |
| `CHROMA_HOST` | ChromaDB hostname | `chromadb` | Yes |
| `CHROMA_PORT` | ChromaDB port | `8000` | Yes |
| `REDIS_HOST` | Redis hostname | `redis` | Yes |
| `REDIS_PORT` | Redis port | `6379` | Yes |
| `REDIS_PASSWORD` | Redis password | - | Yes |

### B. Port Reference

| Port | Service | Protocol | Purpose |
|------|---------|----------|---------|
| 8000 | API | HTTP | Main API endpoint |
| 8001 | Metrics | HTTP | Prometheus metrics |
| 6379 | Redis | TCP | Cache and sessions |
| 8000 | ChromaDB | HTTP | Vector database |
| 9090 | Prometheus | HTTP | Metrics collection |
| 3000 | Grafana | HTTP | Dashboards |
| 16686 | Jaeger | HTTP | Trace visualization |

### C. Resource Requirements

| Component | Min CPU | Min RAM | Min Storage | Recommended CPU | Recommended RAM | Recommended Storage |
|-----------|---------|---------|-------------|-----------------|-----------------|---------------------|
| API Pod | 250m | 256Mi | 1Gi | 500m | 512Mi | 10Gi |
| ChromaDB | 500m | 512Mi | 50Gi | 1000m | 1Gi | 100Gi |
| Redis | 250m | 256Mi | 10Gi | 500m | 512Mi | 20Gi |
| Prometheus | 500m | 512Mi | 20Gi | 1000m | 1Gi | 50Gi |
| Grafana | 250m | 256Mi | 5Gi | 500m | 512Mi | 10Gi |

### D. Useful Commands

#### Docker

```bash
# Build production image
docker build -f docker/Dockerfile.production -t knowledgebeast:2.3.0 .

# Run container
docker run -d -p 8000:8000 knowledgebeast:2.3.0

# View logs
docker logs -f <container-id>

# Execute command in container
docker exec -it <container-id> /bin/bash

# Remove all stopped containers
docker container prune
```

#### Kubernetes

```bash
# Apply all configs
kubectl apply -f kubernetes/

# Get all resources
kubectl -n knowledgebeast get all

# Scale deployment
kubectl -n knowledgebeast scale deployment knowledgebeast-api --replicas=5

# Rollout status
kubectl -n knowledgebeast rollout status deployment/knowledgebeast-api

# Rollback deployment
kubectl -n knowledgebeast rollout undo deployment/knowledgebeast-api

# Port forward
kubectl -n knowledgebeast port-forward svc/knowledgebeast-api 8000:80
```

### E. Health Check Endpoints

| Endpoint | Method | Description | Expected Response |
|----------|--------|-------------|-------------------|
| `/health` | GET | Basic health check | `{"status":"healthy"}` |
| `/health/ready` | GET | Readiness check | `{"status":"ready"}` |
| `/health/live` | GET | Liveness check | `{"status":"alive"}` |
| `/metrics` | GET | Prometheus metrics | Prometheus format |

### F. Support and Contact

- **Documentation:** https://docs.knowledgebeast.com
- **GitHub:** https://github.com/yourusername/knowledgebeast
- **Issues:** https://github.com/yourusername/knowledgebeast/issues
- **Discussions:** https://github.com/yourusername/knowledgebeast/discussions
- **Email:** support@knowledgebeast.com
- **Slack:** https://knowledgebeast.slack.com

### G. License

This project is licensed under the MIT License. See the [LICENSE](../../LICENSE) file for details.

---

**Document Version:** 1.0.0
**Last Updated:** 2025-10-09
**Next Review:** 2025-11-09
