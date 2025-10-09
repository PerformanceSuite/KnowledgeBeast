# KnowledgeBeast High Availability Deployment Guide

**Version:** 2.3.0
**Last Updated:** 2025-10-09
**Target Availability:** 99.95% (4.38 hours downtime/year)
**RPO:** < 1 hour
**RTO:** < 4 hours

## Table of Contents

1. [Overview](#overview)
2. [Architecture Patterns](#architecture-patterns)
3. [Multi-Region Deployment](#multi-region-deployment)
4. [Database Replication](#database-replication)
5. [Zero-Downtime Deployments](#zero-downtime-deployments)
6. [Load Balancing Strategies](#load-balancing-strategies)
7. [Failover Automation](#failover-automation)
8. [Disaster Recovery](#disaster-recovery)
9. [Monitoring and Alerting](#monitoring-and-alerting)
10. [Testing HA Configuration](#testing-ha-configuration)

---

## Overview

### High Availability Goals

KnowledgeBeast's high availability architecture is designed to achieve:

- **99.95% uptime** (21.9 minutes downtime/month)
- **Zero data loss** during failover
- **Sub-second failover** for application tier
- **Automatic recovery** from common failure scenarios
- **Geographic redundancy** for disaster recovery

### Availability SLA Targets

| Tier | Availability | Downtime/Year | Downtime/Month | Use Case |
|------|--------------|---------------|----------------|----------|
| Basic | 99.0% | 3.65 days | 7.31 hours | Development |
| Standard | 99.9% | 8.77 hours | 43.83 minutes | Staging |
| Premium | 99.95% | 4.38 hours | 21.9 minutes | Production |
| Enterprise | 99.99% | 52.6 minutes | 4.38 minutes | Mission-critical |

### Failure Modes Handled

1. **Single pod failure** - Automatic restart
2. **Node failure** - Pod rescheduling
3. **Availability zone failure** - Cross-AZ failover
4. **Region failure** - Multi-region failover
5. **Database failure** - Replica promotion
6. **Network partition** - Split-brain prevention

---

## Architecture Patterns

### Active-Active Architecture

```
                    ┌─────────────────────┐
                    │  Global Load        │
                    │  Balancer (Route53) │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
    ┌─────────▼────────┐              ┌────────▼─────────┐
    │  Region 1        │              │  Region 2        │
    │  us-west-2       │              │  us-east-1       │
    │                  │              │                  │
    │  ┌────────────┐  │              │  ┌────────────┐  │
    │  │ API (3x)   │  │              │  │ API (3x)   │  │
    │  └──────┬─────┘  │              │  └──────┬─────┘  │
    │         │        │              │         │        │
    │  ┌──────▼─────┐  │              │  ┌──────▼─────┐  │
    │  │ ChromaDB   │◄─┼──Replication─┼─►│ ChromaDB   │  │
    │  │ (Primary)  │  │              │  │ (Replica)  │  │
    │  └────────────┘  │              │  └────────────┘  │
    └──────────────────┘              └──────────────────┘
```

**Benefits:**
- Both regions actively serve traffic
- Load distributed geographically
- Better resource utilization
- Lower latency for global users

**Challenges:**
- Data consistency across regions
- Conflict resolution needed
- Higher complexity

### Active-Passive Architecture

```
                    ┌─────────────────────┐
                    │  Global Load        │
                    │  Balancer (Route53) │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
    ┌─────────▼────────┐              ┌────────▼─────────┐
    │  Primary Region  │              │  Standby Region  │
    │  us-west-2       │              │  us-east-1       │
    │  (ACTIVE)        │              │  (PASSIVE)       │
    │                  │              │                  │
    │  ┌────────────┐  │              │  ┌────────────┐  │
    │  │ API (5x)   │  │              │  │ API (0x)   │  │
    │  └──────┬─────┘  │              │  └──────┬─────┘  │
    │         │        │              │         │        │
    │  ┌──────▼─────┐  │              │  ┌──────▼─────┐  │
    │  │ ChromaDB   │──┼──Replication─┼─►│ ChromaDB   │  │
    │  │ (Primary)  │  │              │  │ (Standby)  │  │
    │  └────────────┘  │              │  └────────────┘  │
    └──────────────────┘              └──────────────────┘
```

**Benefits:**
- Simpler data consistency
- Clear primary/secondary roles
- Easier to manage

**Challenges:**
- Idle resources in standby
- Longer failover time
- Potential data loss

### Recommended: Hybrid Architecture

```
                    ┌─────────────────────┐
                    │  Global Load        │
                    │  Balancer (Route53) │
                    │  Latency-based      │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
    ┌─────────▼────────┐              ┌────────▼─────────┐
    │  Region 1        │              │  Region 2        │
    │  us-west-2       │              │  us-east-1       │
    │  (PRIMARY)       │              │  (SECONDARY)     │
    │                  │              │                  │
    │  ┌────────────┐  │              │  ┌────────────┐  │
    │  │ API (5x)   │  │              │  │ API (2x)   │  │
    │  └──────┬─────┘  │              │  └──────┬─────┘  │
    │         │        │              │         │        │
    │  ┌──────▼─────┐  │              │  ┌──────▼─────┐  │
    │  │ ChromaDB   │──┼──Replication─┼─►│ ChromaDB   │  │
    │  │ (Primary)  │  │              │  │ (Read-only)│  │
    │  └────────────┘  │              │  └────────────┘  │
    └──────────────────┘              └──────────────────┘
```

**Benefits:**
- Primary handles writes, both handle reads
- Cost-effective (secondary has fewer resources)
- Fast failover capability
- Good balance of complexity and reliability

---

## Multi-Region Deployment

### Cloud Provider Setup

#### AWS Multi-Region

##### Step 1: Create VPCs in Multiple Regions

```bash
# Region 1: us-west-2
aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --region us-west-2 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=knowledgebeast-vpc-west}]'

# Region 2: us-east-1
aws ec2 create-vpc \
  --cidr-block 10.1.0.0/16 \
  --region us-east-1 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=knowledgebeast-vpc-east}]'
```

##### Step 2: Create EKS Clusters

```bash
# Create cluster in us-west-2
eksctl create cluster \
  --name knowledgebeast-west \
  --region us-west-2 \
  --version 1.28 \
  --nodegroup-name standard-workers \
  --node-type t3.xlarge \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 10 \
  --managed

# Create cluster in us-east-1
eksctl create cluster \
  --name knowledgebeast-east \
  --region us-east-1 \
  --version 1.28 \
  --nodegroup-name standard-workers \
  --node-type t3.xlarge \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 10 \
  --managed
```

##### Step 3: Configure VPC Peering

```bash
# Create peering connection
aws ec2 create-vpc-peering-connection \
  --vpc-id vpc-west-id \
  --peer-vpc-id vpc-east-id \
  --peer-region us-east-1 \
  --region us-west-2

# Accept peering connection
aws ec2 accept-vpc-peering-connection \
  --vpc-peering-connection-id pcx-xxx \
  --region us-east-1

# Update route tables
aws ec2 create-route \
  --route-table-id rtb-west \
  --destination-cidr-block 10.1.0.0/16 \
  --vpc-peering-connection-id pcx-xxx \
  --region us-west-2

aws ec2 create-route \
  --route-table-id rtb-east \
  --destination-cidr-block 10.0.0.0/16 \
  --vpc-peering-connection-id pcx-xxx \
  --region us-east-1
```

#### GCP Multi-Region

```bash
# Create GKE clusters in multiple regions
gcloud container clusters create knowledgebeast-west \
  --region=us-west1 \
  --num-nodes=3 \
  --machine-type=n1-standard-4 \
  --enable-autoscaling \
  --min-nodes=2 \
  --max-nodes=10

gcloud container clusters create knowledgebeast-east \
  --region=us-east1 \
  --num-nodes=2 \
  --machine-type=n1-standard-4 \
  --enable-autoscaling \
  --min-nodes=1 \
  --max-nodes=10
```

### Global Load Balancing

#### AWS Route53 Configuration

```bash
# Create health check
aws route53 create-health-check \
  --health-check-config \
    Type=HTTPS,\
    ResourcePath=/health,\
    FullyQualifiedDomainName=api-west.knowledgebeast.com,\
    Port=443,\
    RequestInterval=30,\
    FailureThreshold=3

# Create hosted zone
aws route53 create-hosted-zone \
  --name knowledgebeast.com \
  --caller-reference $(date +%s)

# Create latency-based routing
cat > change-batch.json <<EOF
{
  "Changes": [
    {
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "api.knowledgebeast.com",
        "Type": "A",
        "SetIdentifier": "us-west-2",
        "Region": "us-west-2",
        "AliasTarget": {
          "HostedZoneId": "Z1234567890ABC",
          "DNSName": "api-west-lb.us-west-2.elb.amazonaws.com",
          "EvaluateTargetHealth": true
        }
      }
    },
    {
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "api.knowledgebeast.com",
        "Type": "A",
        "SetIdentifier": "us-east-1",
        "Region": "us-east-1",
        "AliasTarget": {
          "HostedZoneId": "Z0987654321XYZ",
          "DNSName": "api-east-lb.us-east-1.elb.amazonaws.com",
          "EvaluateTargetHealth": true
        }
      }
    }
  ]
}
EOF

aws route53 change-resource-record-sets \
  --hosted-zone-id Z123456 \
  --change-batch file://change-batch.json
```

#### GCP Global Load Balancer

```bash
# Create global IP address
gcloud compute addresses create knowledgebeast-global-ip \
  --global

# Create health check
gcloud compute health-checks create https knowledgebeast-health \
  --request-path=/health \
  --port=443

# Create backend service
gcloud compute backend-services create knowledgebeast-backend \
  --protocol=HTTP \
  --health-checks=knowledgebeast-health \
  --global

# Add backends
gcloud compute backend-services add-backend knowledgebeast-backend \
  --instance-group=knowledgebeast-west-ig \
  --instance-group-region=us-west1 \
  --global

gcloud compute backend-services add-backend knowledgebeast-backend \
  --instance-group=knowledgebeast-east-ig \
  --instance-group-region=us-east1 \
  --global

# Create URL map
gcloud compute url-maps create knowledgebeast-lb \
  --default-service=knowledgebeast-backend

# Create HTTP(S) proxy
gcloud compute target-https-proxies create knowledgebeast-https-proxy \
  --url-map=knowledgebeast-lb \
  --ssl-certificates=knowledgebeast-cert

# Create forwarding rule
gcloud compute forwarding-rules create knowledgebeast-https-rule \
  --address=knowledgebeast-global-ip \
  --global \
  --target-https-proxy=knowledgebeast-https-proxy \
  --ports=443
```

### Traffic Distribution Strategies

#### Latency-Based Routing

Route users to nearest region based on latency:

```yaml
# Route53 latency-based routing
routing_policy:
  type: latency
  regions:
    - region: us-west-2
      weight: 100
      health_check: hc-west
    - region: us-east-1
      weight: 100
      health_check: hc-east
```

#### Geolocation-Based Routing

Route users based on geographic location:

```yaml
# Route53 geolocation routing
routing_policy:
  type: geolocation
  locations:
    - continent: NA
      region: us-west-2
    - continent: EU
      region: eu-west-1
    - continent: AS
      region: ap-southeast-1
    - default: us-west-2
```

#### Weighted Routing (Blue-Green)

```yaml
# Route53 weighted routing
routing_policy:
  type: weighted
  targets:
    - target: blue-environment
      weight: 90
    - target: green-environment
      weight: 10
```

---

## Database Replication

### ChromaDB Replication Strategy

#### Master-Replica Setup

##### Primary Region (us-west-2)

```yaml
# Primary ChromaDB deployment
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: chromadb-primary
  namespace: knowledgebeast
spec:
  serviceName: chromadb-primary
  replicas: 1
  selector:
    matchLabels:
      app: chromadb
      role: primary
  template:
    metadata:
      labels:
        app: chromadb
        role: primary
    spec:
      containers:
        - name: chromadb
          image: chromadb/chroma:0.4.22
          env:
            - name: IS_PERSISTENT
              value: "TRUE"
            - name: PERSIST_DIRECTORY
              value: "/chroma/chroma"
          volumeMounts:
            - name: data
              mountPath: /chroma/chroma
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 100Gi
```

##### Secondary Region (us-east-1)

```yaml
# Replica ChromaDB deployment
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: chromadb-replica
  namespace: knowledgebeast
spec:
  serviceName: chromadb-replica
  replicas: 1
  selector:
    matchLabels:
      app: chromadb
      role: replica
  template:
    metadata:
      labels:
        app: chromadb
        role: replica
    spec:
      containers:
        - name: chromadb
          image: chromadb/chroma:0.4.22
          env:
            - name: IS_PERSISTENT
              value: "TRUE"
            - name: PERSIST_DIRECTORY
              value: "/chroma/chroma"
            - name: READ_ONLY
              value: "TRUE"
          volumeMounts:
            - name: data
              mountPath: /chroma/chroma
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 100Gi
```

#### Continuous Replication

Use a sidecar container or CronJob for replication:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: chromadb-replication
  namespace: knowledgebeast
spec:
  schedule: "*/15 * * * *"  # Every 15 minutes
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: replicator
              image: amazon/aws-cli:latest
              command:
                - /bin/bash
                - -c
                - |
                  # Sync from primary to S3
                  kubectl exec -n knowledgebeast chromadb-primary-0 -- \
                    tar czf /tmp/backup.tar.gz /chroma/chroma

                  kubectl cp knowledgebeast/chromadb-primary-0:/tmp/backup.tar.gz \
                    /tmp/backup.tar.gz

                  aws s3 cp /tmp/backup.tar.gz \
                    s3://knowledgebeast-replication/latest/

                  # Sync from S3 to replica (in other cluster context)
                  kubectl config use-context east-cluster

                  aws s3 cp s3://knowledgebeast-replication/latest/backup.tar.gz \
                    /tmp/backup.tar.gz

                  kubectl cp /tmp/backup.tar.gz \
                    knowledgebeast/chromadb-replica-0:/tmp/backup.tar.gz

                  kubectl exec -n knowledgebeast chromadb-replica-0 -- \
                    tar xzf /tmp/backup.tar.gz -C /
          restartPolicy: OnFailure
```

### Redis Replication

#### Redis Sentinel for HA

```yaml
# Redis Master
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis-master
  namespace: knowledgebeast
spec:
  serviceName: redis-master
  replicas: 1
  selector:
    matchLabels:
      app: redis
      role: master
  template:
    metadata:
      labels:
        app: redis
        role: master
    spec:
      containers:
        - name: redis
          image: redis:7.2-alpine
          command:
            - redis-server
            - --port
            - "6379"
            - --requirepass
            - $(REDIS_PASSWORD)
          env:
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: redis-secret
                  key: password
          ports:
            - containerPort: 6379
          volumeMounts:
            - name: data
              mountPath: /data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 20Gi

---
# Redis Replicas
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis-replica
  namespace: knowledgebeast
spec:
  serviceName: redis-replica
  replicas: 2
  selector:
    matchLabels:
      app: redis
      role: replica
  template:
    metadata:
      labels:
        app: redis
        role: replica
    spec:
      containers:
        - name: redis
          image: redis:7.2-alpine
          command:
            - redis-server
            - --port
            - "6379"
            - --replicaof
            - redis-master-0.redis-master
            - "6379"
            - --requirepass
            - $(REDIS_PASSWORD)
            - --masterauth
            - $(REDIS_PASSWORD)
          env:
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: redis-secret
                  key: password
          ports:
            - containerPort: 6379

---
# Redis Sentinel
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis-sentinel
  namespace: knowledgebeast
spec:
  serviceName: redis-sentinel
  replicas: 3
  selector:
    matchLabels:
      app: redis-sentinel
  template:
    metadata:
      labels:
        app: redis-sentinel
    spec:
      containers:
        - name: sentinel
          image: redis:7.2-alpine
          command:
            - redis-sentinel
            - /etc/redis/sentinel.conf
          ports:
            - containerPort: 26379
          volumeMounts:
            - name: config
              mountPath: /etc/redis
      volumes:
        - name: config
          configMap:
            name: redis-sentinel-config
```

Redis Sentinel configuration:

```conf
# sentinel.conf
port 26379
sentinel monitor knowledgebeast-master redis-master-0.redis-master 6379 2
sentinel down-after-milliseconds knowledgebeast-master 5000
sentinel parallel-syncs knowledgebeast-master 1
sentinel failover-timeout knowledgebeast-master 10000
sentinel auth-pass knowledgebeast-master ${REDIS_PASSWORD}
```

### Cross-Region Database Sync

#### Automated Sync Script

```bash
#!/bin/bash
# cross-region-sync.sh

set -e

PRIMARY_CLUSTER="knowledgebeast-west"
SECONDARY_CLUSTER="knowledgebeast-east"
NAMESPACE="knowledgebeast"
S3_BUCKET="s3://knowledgebeast-replication"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Function to create backup
create_backup() {
    local cluster=$1
    local backup_file="chromadb-${cluster}-${TIMESTAMP}.tar.gz"

    echo "Creating backup from ${cluster}..."

    kubectl --context="${cluster}" exec -n "${NAMESPACE}" \
        statefulset/chromadb-primary -- \
        tar czf "/tmp/${backup_file}" /chroma/chroma

    kubectl --context="${cluster}" cp \
        "${NAMESPACE}/chromadb-primary-0:/tmp/${backup_file}" \
        "/tmp/${backup_file}"

    echo "${backup_file}"
}

# Function to upload to S3
upload_to_s3() {
    local file=$1

    echo "Uploading ${file} to S3..."
    aws s3 cp "/tmp/${file}" "${S3_BUCKET}/${file}"
    aws s3 cp "/tmp/${file}" "${S3_BUCKET}/latest.tar.gz"
}

# Function to restore to replica
restore_to_replica() {
    local file=$1
    local cluster=$2

    echo "Restoring ${file} to ${cluster}..."

    # Download from S3
    aws s3 cp "${S3_BUCKET}/${file}" "/tmp/${file}"

    # Stop replica (if running)
    kubectl --context="${cluster}" scale -n "${NAMESPACE}" \
        statefulset/chromadb-replica --replicas=0

    # Upload to pod
    kubectl --context="${cluster}" cp \
        "/tmp/${file}" \
        "${NAMESPACE}/chromadb-replica-0:/tmp/${file}"

    # Extract backup
    kubectl --context="${cluster}" exec -n "${NAMESPACE}" \
        statefulset/chromadb-replica -- \
        tar xzf "/tmp/${file}" -C /

    # Start replica
    kubectl --context="${cluster}" scale -n "${NAMESPACE}" \
        statefulset/chromadb-replica --replicas=1
}

# Main sync process
main() {
    echo "Starting cross-region sync at ${TIMESTAMP}"

    # Create backup from primary
    BACKUP_FILE=$(create_backup "${PRIMARY_CLUSTER}")

    # Upload to S3
    upload_to_s3 "${BACKUP_FILE}"

    # Restore to secondary
    restore_to_replica "${BACKUP_FILE}" "${SECONDARY_CLUSTER}"

    # Cleanup
    rm -f "/tmp/${BACKUP_FILE}"

    echo "Sync completed successfully at $(date +%Y%m%d-%H%M%S)"
}

# Run main function
main
```

Schedule with CronJob:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: cross-region-sync
  namespace: knowledgebeast
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: replication-sa
          containers:
            - name: sync
              image: knowledgebeast/sync-tool:latest
              command:
                - /bin/bash
                - /scripts/cross-region-sync.sh
              volumeMounts:
                - name: scripts
                  mountPath: /scripts
                - name: kubeconfig
                  mountPath: /root/.kube
          volumes:
            - name: scripts
              configMap:
                name: sync-scripts
            - name: kubeconfig
              secret:
                secretName: kubeconfig
          restartPolicy: OnFailure
```

---

## Zero-Downtime Deployments

### Rolling Update Strategy

#### Kubernetes Rolling Update Configuration

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: knowledgebeast-api
spec:
  replicas: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 2        # Allow 2 extra pods during update
      maxUnavailable: 0  # Never go below desired count
  template:
    spec:
      containers:
        - name: api
          image: knowledgebeast:2.3.0
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 5
            failureThreshold: 3
          lifecycle:
            preStop:
              exec:
                command:
                  - /bin/sh
                  - -c
                  - sleep 15  # Grace period for connection draining
```

#### Deployment Process

```bash
# 1. Update image tag
kubectl -n knowledgebeast set image deployment/knowledgebeast-api \
  api=knowledgebeast:2.3.1

# 2. Monitor rollout
kubectl -n knowledgebeast rollout status deployment/knowledgebeast-api

# 3. Verify health
kubectl -n knowledgebeast get pods -l app=knowledgebeast

# 4. Rollback if needed
kubectl -n knowledgebeast rollout undo deployment/knowledgebeast-api
```

### Blue-Green Deployment

#### Setup

```yaml
---
# Blue deployment (current production)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: knowledgebeast-blue
  namespace: knowledgebeast
  labels:
    version: blue
spec:
  replicas: 5
  selector:
    matchLabels:
      app: knowledgebeast
      version: blue
  template:
    metadata:
      labels:
        app: knowledgebeast
        version: blue
    spec:
      containers:
        - name: api
          image: knowledgebeast:2.3.0

---
# Green deployment (new version)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: knowledgebeast-green
  namespace: knowledgebeast
  labels:
    version: green
spec:
  replicas: 5
  selector:
    matchLabels:
      app: knowledgebeast
      version: green
  template:
    metadata:
      labels:
        app: knowledgebeast
        version: green
    spec:
      containers:
        - name: api
          image: knowledgebeast:2.3.1

---
# Service (controls traffic routing)
apiVersion: v1
kind: Service
metadata:
  name: knowledgebeast-api
  namespace: knowledgebeast
spec:
  selector:
    app: knowledgebeast
    version: blue  # Switch to 'green' for cutover
  ports:
    - port: 80
      targetPort: 8000
```

#### Cutover Process

```bash
# 1. Deploy green environment
kubectl apply -f deployment-green.yaml

# 2. Wait for green to be ready
kubectl -n knowledgebeast rollout status deployment/knowledgebeast-green

# 3. Test green environment
kubectl -n knowledgebeast port-forward deployment/knowledgebeast-green 8080:8000
curl http://localhost:8080/health

# 4. Switch traffic to green
kubectl -n knowledgebeast patch service knowledgebeast-api \
  -p '{"spec":{"selector":{"version":"green"}}}'

# 5. Monitor for issues
kubectl -n knowledgebeast logs -l version=green --tail=100 -f

# 6. If successful, scale down blue
kubectl -n knowledgebeast scale deployment/knowledgebeast-blue --replicas=0

# 7. If issues, rollback to blue
kubectl -n knowledgebeast patch service knowledgebeast-api \
  -p '{"spec":{"selector":{"version":"blue"}}}'
```

### Canary Deployment

#### Istio-Based Canary

```yaml
---
# Virtual Service for traffic splitting
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: knowledgebeast
  namespace: knowledgebeast
spec:
  hosts:
    - api.knowledgebeast.com
  http:
    - match:
        - headers:
            canary:
              exact: "true"
      route:
        - destination:
            host: knowledgebeast-api
            subset: canary
    - route:
        - destination:
            host: knowledgebeast-api
            subset: stable
          weight: 90
        - destination:
            host: knowledgebeast-api
            subset: canary
          weight: 10

---
# Destination Rule
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: knowledgebeast
  namespace: knowledgebeast
spec:
  host: knowledgebeast-api
  subsets:
    - name: stable
      labels:
        version: stable
    - name: canary
      labels:
        version: canary
```

#### Progressive Traffic Shift

```bash
# Start with 10% to canary
kubectl apply -f canary-10.yaml

# Monitor canary metrics
kubectl -n knowledgebeast logs -l version=canary --tail=100 -f

# If healthy, increase to 25%
kubectl apply -f canary-25.yaml

# Continue progressive rollout: 50%, 75%, 100%
kubectl apply -f canary-50.yaml
kubectl apply -f canary-75.yaml
kubectl apply -f canary-100.yaml

# Once at 100%, promote canary to stable
kubectl -n knowledgebeast label deployment knowledgebeast-canary \
  version=stable --overwrite
kubectl -n knowledgebeast delete deployment knowledgebeast-stable
```

---

## Load Balancing Strategies

### Layer 4 (TCP) Load Balancing

#### AWS Network Load Balancer

```bash
# Create target group
aws elbv2 create-target-group \
  --name knowledgebeast-tg \
  --protocol TCP \
  --port 8000 \
  --vpc-id vpc-xxx \
  --health-check-protocol HTTP \
  --health-check-path /health

# Create NLB
aws elbv2 create-load-balancer \
  --name knowledgebeast-nlb \
  --type network \
  --scheme internet-facing \
  --subnets subnet-xxx subnet-yyy

# Create listener
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:... \
  --protocol TCP \
  --port 443 \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:...
```

### Layer 7 (HTTP) Load Balancing

#### NGINX Ingress with Advanced Features

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: knowledgebeast-ingress
  namespace: knowledgebeast
  annotations:
    # Load balancing algorithm
    nginx.ingress.kubernetes.io/load-balance: "ewma"  # Exponentially weighted moving average

    # Session affinity
    nginx.ingress.kubernetes.io/affinity: "cookie"
    nginx.ingress.kubernetes.io/session-cookie-name: "kb-session"
    nginx.ingress.kubernetes.io/session-cookie-expires: "172800"
    nginx.ingress.kubernetes.io/session-cookie-max-age: "172800"
    nginx.ingress.kubernetes.io/session-cookie-samesite: "Strict"

    # Connection limits
    nginx.ingress.kubernetes.io/limit-connections: "20"
    nginx.ingress.kubernetes.io/limit-rps: "100"

    # Upstream keepalive
    nginx.ingress.kubernetes.io/upstream-keepalive-connections: "64"
    nginx.ingress.kubernetes.io/upstream-keepalive-requests: "100"
    nginx.ingress.kubernetes.io/upstream-keepalive-timeout: "60"

    # Health checks
    nginx.ingress.kubernetes.io/health-check-path: "/health"
    nginx.ingress.kubernetes.io/health-check-interval: "10s"
    nginx.ingress.kubernetes.io/health-check-timeout: "5s"
    nginx.ingress.kubernetes.io/health-check-success-threshold: "1"
    nginx.ingress.kubernetes.io/health-check-failure-threshold: "3"
spec:
  ingressClassName: nginx
  rules:
    - host: api.knowledgebeast.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: knowledgebeast-api
                port:
                  number: 80
```

### Service Mesh Load Balancing (Istio)

```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: knowledgebeast-lb
  namespace: knowledgebeast
spec:
  host: knowledgebeast-api
  trafficPolicy:
    loadBalancer:
      consistentHash:
        httpHeaderName: "x-user-id"
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        http1MaxPendingRequests: 100
        http2MaxRequests: 100
        maxRequestsPerConnection: 2
    outlierDetection:
      consecutiveErrors: 5
      interval: 30s
      baseEjectionTime: 30s
      maxEjectionPercent: 50
      minHealthPercent: 50
```

---

## Failover Automation

### Automated Failover with Route53

#### Health Check Configuration

```bash
# Create detailed health check
aws route53 create-health-check \
  --health-check-config \
    Type=HTTPS,\
    ResourcePath=/health,\
    FullyQualifiedDomainName=api-west.knowledgebeast.com,\
    Port=443,\
    RequestInterval=30,\
    FailureThreshold=3,\
    MeasureLatency=true,\
    EnableSNI=true

# Create alarm for health check
aws cloudwatch put-metric-alarm \
  --alarm-name knowledgebeast-west-unhealthy \
  --alarm-description "Trigger when west region is unhealthy" \
  --metric-name HealthCheckStatus \
  --namespace AWS/Route53 \
  --statistic Minimum \
  --period 60 \
  --threshold 1 \
  --comparison-operator LessThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-west-2:123456789012:failover-alerts
```

#### Automated Failover Script

```python
#!/usr/bin/env python3
# automated-failover.py

import boto3
import time
from datetime import datetime

route53 = boto3.client('route53')
cloudwatch = boto3.client('cloudwatch')

def check_health(health_check_id):
    """Check if health check is passing"""
    response = route53.get_health_check_status(
        HealthCheckId=health_check_id
    )
    for checker in response['HealthCheckObservations']:
        if checker['StatusReport']['Status'] == 'Success':
            return True
    return False

def update_dns(hosted_zone_id, primary_healthy, secondary_healthy):
    """Update DNS routing based on health"""

    if not primary_healthy and secondary_healthy:
        print(f"{datetime.now()}: PRIMARY DOWN - Failing over to secondary")

        # Update weights to route all traffic to secondary
        route53.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': 'api.knowledgebeast.com',
                            'Type': 'A',
                            'SetIdentifier': 'us-west-2',
                            'Weight': 0,
                            'AliasTarget': {
                                'HostedZoneId': 'Z1234567890ABC',
                                'DNSName': 'api-west-lb.us-west-2.elb.amazonaws.com',
                                'EvaluateTargetHealth': True
                            }
                        }
                    },
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': 'api.knowledgebeast.com',
                            'Type': 'A',
                            'SetIdentifier': 'us-east-1',
                            'Weight': 100,
                            'AliasTarget': {
                                'HostedZoneId': 'Z0987654321XYZ',
                                'DNSName': 'api-east-lb.us-east-1.elb.amazonaws.com',
                                'EvaluateTargetHealth': True
                            }
                        }
                    }
                ]
            }
        )

        # Send alert
        sns = boto3.client('sns')
        sns.publish(
            TopicArn='arn:aws:sns:us-west-2:123456789012:failover-alerts',
            Subject='KnowledgeBeast Failover: PRIMARY DOWN',
            Message=f'Automatic failover executed at {datetime.now()}. All traffic routed to us-east-1.'
        )

    elif primary_healthy and not secondary_healthy:
        print(f"{datetime.now()}: SECONDARY DOWN - All traffic on primary")

    elif not primary_healthy and not secondary_healthy:
        print(f"{datetime.now()}: BOTH REGIONS DOWN - CRITICAL ALERT!")
        # Send critical alert

    else:
        print(f"{datetime.now()}: Both regions healthy")

def main():
    """Main monitoring loop"""
    PRIMARY_HC_ID = 'abc123-primary'
    SECONDARY_HC_ID = 'xyz789-secondary'
    HOSTED_ZONE_ID = 'Z123456'

    while True:
        primary_healthy = check_health(PRIMARY_HC_ID)
        secondary_healthy = check_health(SECONDARY_HC_ID)

        update_dns(HOSTED_ZONE_ID, primary_healthy, secondary_healthy)

        time.sleep(30)  # Check every 30 seconds

if __name__ == '__main__':
    main()
```

### Kubernetes-Based Failover

#### External DNS Automatic Updates

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: external-dns
  namespace: kube-system

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: external-dns
rules:
  - apiGroups: [""]
    resources: ["services", "endpoints", "pods"]
    verbs: ["get", "watch", "list"]
  - apiGroups: ["extensions", "networking.k8s.io"]
    resources: ["ingresses"]
    verbs: ["get", "watch", "list"]
  - apiGroups: [""]
    resources: ["nodes"]
    verbs: ["list"]

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: external-dns
  namespace: kube-system
spec:
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: external-dns
  template:
    metadata:
      labels:
        app: external-dns
    spec:
      serviceAccountName: external-dns
      containers:
        - name: external-dns
          image: k8s.gcr.io/external-dns/external-dns:v0.13.5
          args:
            - --source=service
            - --source=ingress
            - --domain-filter=knowledgebeast.com
            - --provider=aws
            - --policy=sync
            - --aws-zone-type=public
            - --registry=txt
            - --txt-owner-id=knowledgebeast-k8s
```

---

## Disaster Recovery

### DR Strategy Overview

#### Recovery Objectives

| Tier | RPO | RTO | Data Loss | Downtime |
|------|-----|-----|-----------|----------|
| Bronze | 24 hours | 24 hours | Up to 1 day | Up to 1 day |
| Silver | 4 hours | 8 hours | Up to 4 hours | Up to 8 hours |
| Gold | 1 hour | 4 hours | Up to 1 hour | Up to 4 hours |
| Platinum | 15 minutes | 1 hour | Up to 15 min | Up to 1 hour |

**KnowledgeBeast Target:** Gold Tier (RPO < 1h, RTO < 4h)

### DR Procedures

#### Scenario 1: Region Failure

```bash
#!/bin/bash
# dr-region-failover.sh

set -e

echo "=== Disaster Recovery: Region Failover ==="
echo "Timestamp: $(date)"

# 1. Verify secondary region is ready
echo "Checking secondary region..."
kubectl --context=knowledgebeast-east get nodes

# 2. Restore latest backup to secondary
echo "Restoring latest backup..."
LATEST_BACKUP=$(aws s3 ls s3://knowledgebeast-backups/ --recursive | sort | tail -n 1 | awk '{print $4}')
aws s3 cp "s3://knowledgebeast-backups/${LATEST_BACKUP}" /tmp/restore.tar.gz

# 3. Scale up secondary region
echo "Scaling up secondary region..."
kubectl --context=knowledgebeast-east scale -n knowledgebeast \
  deployment/knowledgebeast-api --replicas=5

# 4. Wait for pods to be ready
echo "Waiting for pods..."
kubectl --context=knowledgebeast-east rollout status -n knowledgebeast \
  deployment/knowledgebeast-api

# 5. Update DNS to point to secondary
echo "Updating DNS..."
aws route53 change-resource-record-sets \
  --hosted-zone-id Z123456 \
  --change-batch file://failover-dns.json

# 6. Verify health
echo "Verifying health..."
sleep 30
curl -f https://api.knowledgebeast.com/health || {
  echo "Health check failed!"
  exit 1
}

echo "=== Failover complete ==="
```

#### Scenario 2: Data Corruption

```bash
#!/bin/bash
# dr-data-restore.sh

RESTORE_POINT="2025-10-09-12-00"
NAMESPACE="knowledgebeast"

echo "=== Data Restore from ${RESTORE_POINT} ==="

# 1. Stop application
kubectl -n ${NAMESPACE} scale deployment/knowledgebeast-api --replicas=0

# 2. Restore database
velero restore create --from-backup knowledgebeast-daily-${RESTORE_POINT} \
  --include-resources pvc,persistentvolume \
  --wait

# 3. Verify data
kubectl -n ${NAMESPACE} exec statefulset/chromadb-primary -- \
  python3 /scripts/verify-data.py

# 4. Restart application
kubectl -n ${NAMESPACE} scale deployment/knowledgebeast-api --replicas=3

echo "=== Restore complete ==="
```

### DR Testing Schedule

| Test Type | Frequency | Duration | Scope |
|-----------|-----------|----------|-------|
| Backup Verification | Weekly | 1 hour | Verify backups complete successfully |
| Partial Restore | Monthly | 2 hours | Restore single service to test environment |
| Full DR Drill | Quarterly | 4 hours | Complete region failover |
| Chaos Engineering | Monthly | 2 hours | Inject failures to test resilience |

---

## Monitoring and Alerting

### SLI/SLO/SLA Definition

#### Service Level Indicators (SLIs)

- **Availability:** Percentage of successful requests
- **Latency:** P50, P95, P99 response times
- **Error Rate:** Percentage of failed requests
- **Throughput:** Requests per second

#### Service Level Objectives (SLOs)

| Metric | SLO | Measurement Window |
|--------|-----|-------------------|
| Availability | 99.95% | 30 days |
| P95 Latency | < 500ms | 24 hours |
| P99 Latency | < 1s | 24 hours |
| Error Rate | < 0.1% | 24 hours |

#### Service Level Agreements (SLAs)

| Availability | Credits |
|--------------|---------|
| < 99.95% | 10% |
| < 99.9% | 25% |
| < 99.0% | 50% |
| < 95.0% | 100% |

### Critical Alerts

```yaml
# alerts.yml
groups:
  - name: high_availability
    interval: 30s
    rules:
      # Region down
      - alert: RegionDown
        expr: up{job="knowledgebeast-api",region="us-west-2"} == 0
        for: 5m
        labels:
          severity: critical
          tier: infrastructure
        annotations:
          summary: "Primary region is down"
          description: "us-west-2 region has been down for 5 minutes"
          runbook: "https://docs.knowledgebeast.com/runbooks/region-down"

      # SLO breach
      - alert: SLOBreachAvailability
        expr: (sum(rate(http_requests_total{status!~"5.."}[30d])) / sum(rate(http_requests_total[30d]))) < 0.9995
        for: 1h
        labels:
          severity: critical
          tier: slo
        annotations:
          summary: "Availability SLO breached"
          description: "30-day availability is {{ $value | humanizePercentage }}"

      # Latency SLO
      - alert: SLOBreachLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[24h])) > 0.5
        for: 1h
        labels:
          severity: warning
          tier: slo
        annotations:
          summary: "P95 latency SLO breached"
          description: "24h P95 latency is {{ $value }}s"

      # Failover needed
      - alert: FailoverRequired
        expr: (sum by (region) (up{job="knowledgebeast-api"}) / count by (region) (up{job="knowledgebeast-api"})) < 0.5
        for: 2m
        labels:
          severity: critical
          tier: infrastructure
        annotations:
          summary: "More than 50% of pods down in {{ $labels.region }}"
          description: "Consider failing over to secondary region"
```

---

## Testing HA Configuration

### Chaos Engineering

#### Chaos Mesh Setup

```bash
# Install Chaos Mesh
curl -sSL https://mirrors.chaos-mesh.org/v2.6.0/install.sh | bash -s -- --local kind

# Create pod failure experiment
cat <<EOF | kubectl apply -f -
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: pod-failure-test
  namespace: knowledgebeast
spec:
  action: pod-failure
  mode: one
  selector:
    namespaces:
      - knowledgebeast
    labelSelectors:
      app: knowledgebeast
      component: api
  scheduler:
    cron: '@every 1h'
  duration: '5m'
EOF
```

#### Network Partition Test

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-partition
  namespace: knowledgebeast
spec:
  action: partition
  mode: all
  selector:
    namespaces:
      - knowledgebeast
    labelSelectors:
      app: knowledgebeast
  direction: both
  duration: '2m'
```

### Load Testing for HA

```javascript
// ha-load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';

const errors = new Counter('errors');
const latency = new Trend('latency');

export const options = {
  stages: [
    { duration: '5m', target: 100 },
    { duration: '10m', target: 100 },
    { duration: '5m', target: 0 },
  ],
  thresholds: {
    'http_req_duration': ['p(95)<500'],
    'http_req_failed': ['rate<0.01'],
    'errors': ['count<100'],
  },
};

export default function () {
  const res = http.get('https://api.knowledgebeast.com/health');

  const success = check(res, {
    'status is 200': (r) => r.status === 200,
    'response time OK': (r) => r.timings.duration < 500,
  });

  if (!success) {
    errors.add(1);
  }

  latency.add(res.timings.duration);
  sleep(1);
}
```

---

## Conclusion

This high availability guide provides comprehensive strategies for deploying and maintaining KnowledgeBeast with 99.95%+ uptime. Key takeaways:

1. **Use hybrid active-passive architecture** for cost-effective HA
2. **Implement automated failover** to minimize downtime
3. **Regular DR testing** ensures procedures work when needed
4. **Monitor SLOs** to maintain service quality
5. **Chaos engineering** validates resilience

For questions or support, contact the KnowledgeBeast team or file an issue on GitHub.

---

**Document Version:** 1.0.0
**Last Updated:** 2025-10-09
**Next Review:** 2025-11-09
