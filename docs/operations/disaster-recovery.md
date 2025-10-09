# KnowledgeBeast Disaster Recovery Plan

## Overview

This document outlines comprehensive disaster recovery procedures for KnowledgeBeast production environments, ensuring business continuity and data protection.

**Last Updated**: 2025-10-08
**Disaster Recovery Owner**: SRE Team
**Business Continuity Owner**: VP Engineering

### Recovery Objectives

- **RPO (Recovery Point Objective)**: < 1 hour
  - Maximum acceptable data loss: 1 hour of data

- **RTO (Recovery Time Objective)**: < 4 hours
  - Maximum acceptable downtime: 4 hours from disaster to full recovery

---

## Table of Contents

1. [Backup Strategy](#backup-strategy)
2. [Disaster Scenarios](#disaster-scenarios)
3. [Recovery Procedures](#recovery-procedures)
4. [Failover Procedures](#failover-procedures)
5. [Testing & Validation](#testing--validation)
6. [Communication Plan](#communication-plan)

---

## Backup Strategy

### 1. ChromaDB Vector Database Backups

**Frequency**: Daily full backups
**Retention**: 30 days
**Storage**: AWS S3 (cross-region replication)
**Encryption**: AES-256

**Backup Script**:
```bash
#!/bin/bash
# /scripts/backup_chromadb.sh

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/chromadb"
S3_BUCKET="s3://knowledgebeast-backups/chromadb"

echo "[$(date)] Starting ChromaDB backup: $TIMESTAMP"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup each collection
for collection in $(python -c "
from chromadb import Client
client = Client()
collections = client.list_collections()
for col in collections:
    print(col.name)
"); do
    echo "Backing up collection: $collection"
    python -c "
from chromadb import Client
import pickle

client = Client()
collection = client.get_collection('$collection')
data = collection.get(include=['embeddings', 'metadatas', 'documents'])

with open('$BACKUP_DIR/${collection}_$TIMESTAMP.pkl', 'wb') as f:
    pickle.dump(data, f)
"
done

# Create tarball
tar -czf "$BACKUP_DIR/chromadb_$TIMESTAMP.tar.gz" -C "$BACKUP_DIR" .

# Upload to S3
aws s3 cp "$BACKUP_DIR/chromadb_$TIMESTAMP.tar.gz" "$S3_BUCKET/" \
    --storage-class STANDARD_IA \
    --server-side-encryption AES256

# Verify upload
if aws s3 ls "$S3_BUCKET/chromadb_$TIMESTAMP.tar.gz" > /dev/null; then
    echo "[$(date)] Backup uploaded successfully: $TIMESTAMP"
else
    echo "[$(date)] ERROR: Backup upload failed: $TIMESTAMP"
    exit 1
fi

# Clean up local backup files older than 7 days
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete

# Clean up S3 backups older than 30 days
aws s3 ls "$S3_BUCKET/" | awk '{print $4}' | while read file; do
    file_date=$(echo "$file" | grep -oP '\d{8}')
    if [ -n "$file_date" ]; then
        days_old=$(( ($(date +%s) - $(date -d "$file_date" +%s)) / 86400 ))
        if [ $days_old -gt 30 ]; then
            echo "Deleting old backup: $file"
            aws s3 rm "$S3_BUCKET/$file"
        fi
    fi
done

echo "[$(date)] Backup complete: $TIMESTAMP"
```

**Kubernetes CronJob**:
```yaml
# deployments/kubernetes/chromadb-backup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: chromadb-backup
  namespace: production
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  successfulJobsHistoryLimit: 7
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: backup
            image: knowledgebeast:latest
            command: ["/scripts/backup_chromadb.sh"]
            env:
            - name: AWS_ACCESS_KEY_ID
              valueFrom:
                secretKeyRef:
                  name: aws-credentials
                  key: access_key_id
            - name: AWS_SECRET_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: aws-credentials
                  key: secret_access_key
            volumeMounts:
            - name: chromadb-data
              mountPath: /data/chromadb
            - name: backup-storage
              mountPath: /backups
          volumes:
          - name: chromadb-data
            persistentVolumeClaim:
              claimName: chromadb-data
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-storage
```

---

### 2. SQLite Database Backups

**Frequency**: Hourly incremental, daily full
**Retention**: 7 days (hourly), 30 days (daily)
**Storage**: AWS S3 + local PersistentVolume
**Encryption**: AES-256

**Backup Script**:
```bash
#!/bin/bash
# /scripts/backup_sqlite.sh

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/sqlite"
S3_BUCKET="s3://knowledgebeast-backups/sqlite"
DB_PATH="/data/knowledgebeast.db"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting SQLite backup: $TIMESTAMP"

# Online backup using SQLite .backup command (safe for active database)
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/knowledgebeast_$TIMESTAMP.db'"

# Verify backup integrity
if sqlite3 "$BACKUP_DIR/knowledgebeast_$TIMESTAMP.db" "PRAGMA integrity_check;" | grep -q "ok"; then
    echo "[$(date)] Backup integrity verified: $TIMESTAMP"
else
    echo "[$(date)] ERROR: Backup integrity check failed: $TIMESTAMP"
    exit 1
fi

# Compress backup
gzip "$BACKUP_DIR/knowledgebeast_$TIMESTAMP.db"

# Upload to S3
aws s3 cp "$BACKUP_DIR/knowledgebeast_$TIMESTAMP.db.gz" "$S3_BUCKET/" \
    --storage-class STANDARD_IA \
    --server-side-encryption AES256

# Tag as hourly or daily
HOUR=$(date +%H)
if [ "$HOUR" == "02" ]; then
    # Daily backup at 2 AM
    aws s3 cp "$BACKUP_DIR/knowledgebeast_$TIMESTAMP.db.gz" \
        "$S3_BUCKET/daily/knowledgebeast_$TIMESTAMP.db.gz" \
        --storage-class STANDARD_IA \
        --server-side-encryption AES256
fi

# Clean up local backups (keep last 24 hours)
find "$BACKUP_DIR" -name "*.db.gz" -mtime +1 -delete

# Clean up S3 hourly backups (keep last 7 days)
aws s3 ls "$S3_BUCKET/" | awk '{print $4}' | grep -v "daily" | while read file; do
    file_date=$(echo "$file" | grep -oP '\d{8}')
    if [ -n "$file_date" ]; then
        days_old=$(( ($(date +%s) - $(date -d "$file_date" +%s)) / 86400 ))
        if [ $days_old -gt 7 ]; then
            aws s3 rm "$S3_BUCKET/$file"
        fi
    fi
done

# Clean up S3 daily backups (keep last 30 days)
aws s3 ls "$S3_BUCKET/daily/" | awk '{print $4}' | while read file; do
    file_date=$(echo "$file" | grep -oP '\d{8}')
    if [ -n "$file_date" ]; then
        days_old=$(( ($(date +%s) - $(date -d "$file_date" +%s)) / 86400 ))
        if [ $days_old -gt 30 ]; then
            aws s3 rm "$S3_BUCKET/daily/$file"
        fi
    fi
done

echo "[$(date)] Backup complete: $TIMESTAMP"
```

**Kubernetes CronJob**:
```yaml
# deployments/kubernetes/sqlite-backup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: sqlite-backup
  namespace: production
spec:
  schedule: "0 * * * *"  # Every hour
  successfulJobsHistoryLimit: 24
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: backup
            image: knowledgebeast:latest
            command: ["/scripts/backup_sqlite.sh"]
            env:
            - name: AWS_ACCESS_KEY_ID
              valueFrom:
                secretKeyRef:
                  name: aws-credentials
                  key: access_key_id
            - name: AWS_SECRET_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: aws-credentials
                  key: secret_access_key
            volumeMounts:
            - name: app-data
              mountPath: /data
            - name: backup-storage
              mountPath: /backups
          volumes:
          - name: app-data
            persistentVolumeClaim:
              claimName: knowledgebeast-data
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-storage
```

---

### 3. Configuration Backups

**Frequency**: Git-based versioning (continuous)
**Retention**: Indefinite (Git history)
**Storage**: GitHub (private repository)
**Encryption**: Not required (no secrets stored)

**Files Backed Up**:
- Kubernetes manifests (`deployments/kubernetes/*.yaml`)
- Helm charts (`deployments/helm/`)
- Prometheus configuration (`deployments/prometheus/`)
- Grafana dashboards (`deployments/grafana/dashboards/`)
- Environment variables (templates only, no actual secrets)
- Scripts (`scripts/*.sh`, `scripts/*.py`)

**Process**:
```bash
# Automated commit on configuration changes
git add deployments/ scripts/
git commit -m "chore: Backup configuration - $(date +%Y%m%d_%H%M%S)"
git push origin main
```

---

### 4. Secrets Backup

**Frequency**: Manual (on change)
**Retention**: Encrypted vault (1Password/HashiCorp Vault)
**Storage**: Encrypted vault + offline secure storage
**Encryption**: AES-256

**Secrets to Backup**:
- API keys (OpenAI, Hugging Face, etc.)
- Database credentials
- SSL/TLS certificates
- AWS credentials
- Service account tokens
- Encryption keys

**Process**:
1. Store all secrets in 1Password/Vault
2. Export encrypted backup monthly
3. Store offline copy in secure physical location (safe)
4. Document secret rotation procedures

---

## Disaster Scenarios

### Scenario 1: Data Center Outage

**Impact**: Complete loss of primary availability zone
**Probability**: Low (< 1% per year)
**RTO**: 2 hours
**RPO**: 1 hour

**Detection**:
- All health checks failing
- Kubernetes cluster unreachable
- Multi-region monitoring alerts

**Response**: See [Data Center Outage Recovery](#data-center-outage-recovery)

---

### Scenario 2: Database Corruption

**Impact**: SQLite or ChromaDB data integrity compromised
**Probability**: Medium (2-5% per year)
**RTO**: 4 hours
**RPO**: 1 hour

**Detection**:
- `PRAGMA integrity_check` fails
- Application errors on database operations
- Automated integrity check alerts

**Response**: See [Database Corruption Recovery](#database-corruption-recovery)

---

### Scenario 3: Complete System Failure

**Impact**: All components down (application, database, vector store)
**Probability**: Very Low (< 0.1% per year)
**RTO**: 4 hours
**RPO**: 1 hour

**Detection**:
- Total service outage
- Multiple component failures
- Infrastructure-level alerts

**Response**: See [Complete System Failure Recovery](#complete-system-failure-recovery)

---

### Scenario 4: Accidental Data Deletion

**Impact**: Customer data accidentally deleted
**Probability**: Medium (5-10% per year)
**RTO**: 2 hours
**RPO**: 1 hour

**Detection**:
- Customer report
- Sudden drop in document count
- Audit log review

**Response**: See [Accidental Data Deletion Recovery](#accidental-data-deletion-recovery)

---

### Scenario 5: Security Breach

**Impact**: Unauthorized access, potential data exfiltration
**Probability**: Low (1-2% per year)
**RTO**: 1 hour (isolation), 8 hours (full recovery)
**RPO**: 0 (no acceptable data loss)

**Detection**:
- Intrusion detection alerts
- Unusual API access patterns
- Security audit findings

**Response**: See [Security Breach Response](#security-breach-response)

---

## Recovery Procedures

### Data Center Outage Recovery

**Prerequisites**:
- Multi-region setup (Primary: us-east-1, Secondary: us-west-2)
- Cross-region S3 replication
- DNS failover configured (Route 53)

**Step-by-Step Procedure**:

1. **Confirm Outage** (5 minutes)
   ```bash
   # Verify primary region is unreachable
   curl https://api.us-east-1.knowledgebeast.com/health
   # Timeout expected

   # Check AWS status page
   open https://status.aws.amazon.com/

   # Verify secondary region is healthy
   curl https://api.us-west-2.knowledgebeast.com/health
   # Expected: {"status": "healthy"}
   ```

2. **Activate Disaster Recovery Plan** (2 minutes)
   ```bash
   # Page on-call team
   pagerduty-cli incident create --title "DR: Data Center Outage" --service knowledgebeast

   # Notify stakeholders
   slack-cli post -c incidents "🚨 DR activated: us-east-1 outage. Failing over to us-west-2."
   ```

3. **Initiate DNS Failover** (10 minutes)
   ```bash
   # Update Route 53 to point to secondary region
   aws route53 change-resource-record-sets \
     --hosted-zone-id Z1234567890ABC \
     --change-batch '{
       "Changes": [{
         "Action": "UPSERT",
         "ResourceRecordSet": {
           "Name": "api.knowledgebeast.com",
           "Type": "CNAME",
           "TTL": 60,
           "ResourceRecords": [{"Value": "api.us-west-2.knowledgebeast.com"}]
         }
       }]
     }'

   # Verify DNS propagation
   dig api.knowledgebeast.com
   # Should resolve to us-west-2
   ```

4. **Verify Secondary Region** (15 minutes)
   ```bash
   # Scale up secondary region replicas
   kubectl scale deployment/knowledgebeast -n production --replicas=10 --context us-west-2

   # Verify all pods are ready
   kubectl get pods -n production --context us-west-2

   # Run smoke tests
   curl https://api.us-west-2.knowledgebeast.com/api/v1/projects
   curl https://api.us-west-2.knowledgebeast.com/api/v1/query/test-project?q=test
   ```

5. **Restore Latest Data** (60 minutes)
   ```bash
   # Download latest backups from S3
   aws s3 sync s3://knowledgebeast-backups/chromadb/ /tmp/backups/chromadb/ --region us-west-2
   aws s3 sync s3://knowledgebeast-backups/sqlite/ /tmp/backups/sqlite/ --region us-west-2

   # Restore ChromaDB
   /scripts/restore_chromadb.sh --backup /tmp/backups/chromadb/latest.tar.gz

   # Restore SQLite
   /scripts/restore_sqlite.sh --backup /tmp/backups/sqlite/latest.db.gz

   # Verify restoration
   curl https://api.us-west-2.knowledgebeast.com/api/v1/stats
   ```

6. **Update Status Page** (5 minutes)
   ```bash
   # Update status.knowledgebeast.com
   statuspage-cli update --status "partial_outage" \
     --message "Primary data center experiencing outage. Service operating from backup data center."
   ```

7. **Monitor Service** (30 minutes)
   ```bash
   # Watch metrics
   open https://grafana.knowledgebeast.com/d/knowledgebeast-overview

   # Monitor error rate
   watch -n 10 'curl -s https://api.us-west-2.knowledgebeast.com/metrics | grep error_rate'

   # Check query latency
   watch -n 10 'curl -s https://api.us-west-2.knowledgebeast.com/metrics | grep p99_latency'
   ```

8. **Post-Recovery Actions** (after primary region recovers)
   ```bash
   # Verify primary region is back online
   curl https://api.us-east-1.knowledgebeast.com/health

   # Sync data from secondary to primary
   /scripts/sync_regions.sh --source us-west-2 --destination us-east-1

   # Fail back to primary region (during low-traffic window)
   aws route53 change-resource-record-sets \
     --hosted-zone-id Z1234567890ABC \
     --change-batch '{...}'  # Point back to us-east-1

   # Update status page to "operational"
   statuspage-cli update --status "operational"
   ```

**Total RTO**: ~2 hours (from detection to full service restoration)

---

### Database Corruption Recovery

**Prerequisites**:
- Recent database backup (< 1 hour old)
- Database backup integrity verified

**Step-by-Step Procedure**:

1. **Detect and Confirm Corruption** (5 minutes)
   ```bash
   # Run integrity check
   kubectl exec -n production deployment/knowledgebeast -- \
     sqlite3 /data/knowledgebeast.db "PRAGMA integrity_check;"

   # Output: List of errors (not "ok")
   ```

2. **Stop Application** (2 minutes)
   ```bash
   # Scale down to prevent further corruption
   kubectl scale deployment/knowledgebeast -n production --replicas=0

   # Wait for pods to terminate
   kubectl wait --for=delete pod -l app=knowledgebeast -n production --timeout=60s
   ```

3. **Backup Corrupted Database** (5 minutes)
   ```bash
   # Copy for forensic analysis
   kubectl exec -n production deployment/knowledgebeast -- \
     cp /data/knowledgebeast.db /data/corrupted_$(date +%Y%m%d_%H%M%S).db
   ```

4. **Identify Latest Valid Backup** (10 minutes)
   ```bash
   # List recent backups
   aws s3 ls s3://knowledgebeast-backups/sqlite/ | tail -20

   # Download and verify each backup until we find a valid one
   for backup in $(aws s3 ls s3://knowledgebeast-backups/sqlite/ | tail -10 | awk '{print $4}'); do
       echo "Testing backup: $backup"
       aws s3 cp "s3://knowledgebeast-backups/sqlite/$backup" /tmp/test_backup.db.gz
       gunzip /tmp/test_backup.db.gz
       if sqlite3 /tmp/test_backup.db "PRAGMA integrity_check;" | grep -q "ok"; then
           echo "✅ Valid backup found: $backup"
           VALID_BACKUP=$backup
           break
       fi
   done
   ```

5. **Restore Database** (15 minutes)
   ```bash
   # Download valid backup
   aws s3 cp "s3://knowledgebeast-backups/sqlite/$VALID_BACKUP" /tmp/restore.db.gz

   # Decompress
   gunzip /tmp/restore.db.gz

   # Copy to production
   kubectl cp /tmp/restore.db production/knowledgebeast-pod:/data/knowledgebeast.db

   # Verify restoration
   kubectl exec -n production deployment/knowledgebeast -- \
     sqlite3 /data/knowledgebeast.db "PRAGMA integrity_check;"
   # Expected: "ok"

   kubectl exec -n production deployment/knowledgebeast -- \
     sqlite3 /data/knowledgebeast.db "SELECT COUNT(*) FROM projects;"
   # Verify count is reasonable
   ```

6. **Restart Application** (5 minutes)
   ```bash
   # Scale back up
   kubectl scale deployment/knowledgebeast -n production --replicas=3

   # Wait for ready
   kubectl wait --for=condition=ready pod -l app=knowledgebeast -n production --timeout=300s

   # Verify health
   curl https://api.knowledgebeast.com/health
   ```

7. **Verify Data Integrity** (20 minutes)
   ```bash
   # Run automated tests
   pytest tests/integration/test_database_integrity.py

   # Manual spot checks
   curl https://api.knowledgebeast.com/api/v1/projects | jq '.projects | length'
   curl https://api.knowledgebeast.com/api/v1/query/test-project?q=sample | jq '.results | length'

   # Check recent documents (may be missing if backup is old)
   curl https://api.knowledgebeast.com/api/v1/documents?since=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)
   ```

8. **Assess Data Loss** (10 minutes)
   ```bash
   # Compare backup timestamp to corruption time
   BACKUP_TIME=$(echo $VALID_BACKUP | grep -oP '\d{8}_\d{6}')
   echo "Backup timestamp: $BACKUP_TIME"
   echo "Corruption detected: $(date)"
   echo "Estimated data loss window: $(calculate_time_diff)"

   # Notify affected customers (if any)
   ```

**Total RTO**: ~1.5 hours

---

### Complete System Failure Recovery

**Prerequisites**:
- Infrastructure-as-Code (Terraform/Helm)
- Container images in registry
- Backups in S3

**Step-by-Step Procedure**:

1. **Assess Damage** (10 minutes)
   ```bash
   # Check Kubernetes cluster
   kubectl cluster-info
   # If unreachable, cluster is down

   # Check AWS infrastructure
   aws ec2 describe-instances --filters "Name=tag:Name,Values=knowledgebeast-*"

   # Check S3 backups
   aws s3 ls s3://knowledgebeast-backups/
   ```

2. **Rebuild Infrastructure** (60 minutes)
   ```bash
   # Clone infrastructure repo
   git clone https://github.com/org/knowledgebeast-infrastructure
   cd knowledgebeast-infrastructure

   # Initialize Terraform
   terraform init

   # Plan infrastructure
   terraform plan -out=tfplan

   # Apply (creates VPC, EKS cluster, RDS, etc.)
   terraform apply tfplan

   # Wait for cluster to be ready
   aws eks wait cluster-active --name knowledgebeast-prod
   ```

3. **Deploy Application** (30 minutes)
   ```bash
   # Update kubeconfig
   aws eks update-kubeconfig --name knowledgebeast-prod --region us-east-1

   # Deploy using Helm
   helm install knowledgebeast ./deployments/helm/knowledgebeast \
     -f ./deployments/helm/values.production.yaml \
     --namespace production \
     --create-namespace

   # Wait for deployment
   kubectl wait --for=condition=available deployment/knowledgebeast -n production --timeout=600s
   ```

4. **Restore Data** (90 minutes)
   ```bash
   # Download latest backups
   aws s3 sync s3://knowledgebeast-backups/sqlite/daily/ /tmp/restore/sqlite/
   aws s3 sync s3://knowledgebeast-backups/chromadb/ /tmp/restore/chromadb/

   # Restore SQLite
   LATEST_SQLITE=$(ls -t /tmp/restore/sqlite/*.db.gz | head -1)
   gunzip $LATEST_SQLITE
   kubectl cp ${LATEST_SQLITE%.gz} production/knowledgebeast-0:/data/knowledgebeast.db

   # Restore ChromaDB
   LATEST_CHROMADB=$(ls -t /tmp/restore/chromadb/*.tar.gz | head -1)
   kubectl exec -n production chromadb-0 -- tar -xzf - -C /data < $LATEST_CHROMADB

   # Verify data
   kubectl exec -n production deployment/knowledgebeast -- \
     sqlite3 /data/knowledgebeast.db "SELECT COUNT(*) FROM projects;"
   ```

5. **Restore Configuration** (15 minutes)
   ```bash
   # Apply ConfigMaps and Secrets
   kubectl apply -f ./deployments/kubernetes/configmaps/
   kubectl apply -f ./deployments/kubernetes/secrets/  # From 1Password/Vault

   # Restart pods to pick up config
   kubectl rollout restart deployment/knowledgebeast -n production
   ```

6. **Update DNS** (10 minutes)
   ```bash
   # Get new load balancer address
   LB_ADDRESS=$(kubectl get svc knowledgebeast -n production -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

   # Update Route 53
   aws route53 change-resource-record-sets \
     --hosted-zone-id Z1234567890ABC \
     --change-batch "{
       \"Changes\": [{
         \"Action\": \"UPSERT\",
         \"ResourceRecordSet\": {
           \"Name\": \"api.knowledgebeast.com\",
           \"Type\": \"CNAME\",
           \"TTL\": 300,
           \"ResourceRecords\": [{\"Value\": \"$LB_ADDRESS\"}]
         }
       }]
     }"
   ```

7. **Verify and Test** (30 minutes)
   ```bash
   # Health check
   curl https://api.knowledgebeast.com/health

   # Run smoke tests
   pytest tests/smoke/

   # Monitor metrics
   open https://grafana.knowledgebeast.com
   ```

**Total RTO**: ~4 hours

---

### Accidental Data Deletion Recovery

**Prerequisites**:
- Soft delete enabled (30-day grace period)
- Audit logs available

**Step-by-Step Procedure**:

1. **Identify Deleted Data** (10 minutes)
   ```bash
   # Check audit logs
   kubectl logs -n production deployment/knowledgebeast | grep "DELETE" | tail -100

   # Query soft-deleted items
   sqlite3 /data/knowledgebeast.db "
     SELECT id, project, deleted_at FROM documents WHERE deleted_at IS NOT NULL;
   "
   ```

2. **Restore from Soft Delete** (5 minutes - if within 30 days)
   ```bash
   # Restore specific project
   curl -X POST https://api.knowledgebeast.com/api/v1/admin/restore \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -d '{"project": "project-id", "before": "2025-10-08T12:00:00Z"}'

   # Verify restoration
   curl https://api.knowledgebeast.com/api/v1/projects | jq '.projects[] | select(.id=="project-id")'
   ```

3. **Restore from Backup** (60 minutes - if hard deleted)
   ```bash
   # Identify backup containing deleted data
   BACKUP_BEFORE_DELETE=$(find_backup_before --timestamp "2025-10-08T10:00:00Z")

   # Extract specific project data
   gunzip -c $BACKUP_BEFORE_DELETE | \
     sqlite3 :memory: ".mode insert" \
     "SELECT * FROM documents WHERE project='deleted-project-id'" > restore.sql

   # Import to production (careful not to overwrite newer data)
   kubectl exec -n production deployment/knowledgebeast -- \
     sqlite3 /data/knowledgebeast.db < restore.sql

   # Verify restoration
   curl https://api.knowledgebeast.com/api/v1/projects/deleted-project-id
   ```

**Total RTO**: 5 minutes (soft delete) or 60 minutes (backup restore)

---

### Security Breach Response

**Prerequisites**:
- Incident response team assembled
- Forensic tools ready
- Communication plan active

**Step-by-Step Procedure**:

1. **Contain Breach** (15 minutes)
   ```bash
   # Isolate affected systems
   kubectl scale deployment/knowledgebeast -n production --replicas=0

   # Revoke all API keys
   python scripts/revoke_all_api_keys.py

   # Change all passwords
   python scripts/rotate_all_credentials.py

   # Block suspicious IPs
   kubectl apply -f deployments/kubernetes/emergency-firewall-rules.yaml
   ```

2. **Assess Damage** (60 minutes)
   ```bash
   # Review access logs
   kubectl logs -n production deployment/knowledgebeast --since=24h | grep "UNAUTHORIZED\|SUSPICIOUS"

   # Check for data exfiltration
   aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=GetObject

   # Identify compromised accounts
   python scripts/identify_compromised_accounts.py
   ```

3. **Eradicate Threat** (120 minutes)
   ```bash
   # Rebuild all containers from clean images
   docker pull knowledgebeast:latest-clean
   kubectl set image deployment/knowledgebeast knowledgebeast=knowledgebeast:latest-clean -n production

   # Restore from pre-breach backup
   CLEAN_BACKUP=$(find_backup_before --timestamp "$BREACH_TIME")
   /scripts/restore_sqlite.sh --backup $CLEAN_BACKUP

   # Patch vulnerabilities
   kubectl apply -f deployments/kubernetes/security-patches/
   ```

4. **Notify Affected Parties** (30 minutes)
   ```bash
   # Notify customers
   python scripts/send_breach_notification.py --template security-incident

   # Regulatory notifications (GDPR, etc.)
   python scripts/regulatory_notification.py

   # Public disclosure (if required)
   # Update status.knowledgebeast.com
   ```

5. **Restore Service** (60 minutes)
   ```bash
   # Enable enhanced monitoring
   kubectl apply -f deployments/kubernetes/enhanced-monitoring.yaml

   # Restore service with new credentials
   kubectl scale deployment/knowledgebeast -n production --replicas=3

   # Verify security posture
   python scripts/security_audit.py

   # Monitor for continued suspicious activity
   watch -n 30 'kubectl logs -n production deployment/knowledgebeast | grep "UNAUTHORIZED"'
   ```

6. **Post-Incident Analysis** (Post-recovery)
   ```bash
   # Conduct forensic analysis
   # Document attack vector
   # Implement additional security controls
   # Update incident response plan
   ```

**Total RTO**: 1 hour (containment) + 8 hours (full recovery)

---

## Failover Procedures

### Automatic Failover

**Kubernetes-Level Failover**:
- Liveness/Readiness probes automatically restart unhealthy pods
- Horizontal Pod Autoscaler (HPA) scales based on load
- Service mesh (Istio) routes traffic away from failing instances

**DNS-Level Failover**:
- Route 53 health checks monitor primary endpoint
- If health check fails, automatically route to secondary region
- TTL set to 60 seconds for fast propagation

**Configuration**:
```yaml
# Route 53 Health Check
Type: HTTPS
Path: /health
Interval: 30 seconds
Failure Threshold: 3
```

### Manual Failover

**When to Use**:
- Planned maintenance
- Degraded performance in primary region
- Partial outage requiring manual intervention

**Procedure**:
```bash
# 1. Verify secondary region is ready
curl https://api.us-west-2.knowledgebeast.com/health

# 2. Update DNS (see Data Center Outage Recovery)
aws route53 change-resource-record-sets ...

# 3. Monitor traffic shift
watch -n 10 'curl -s https://api.knowledgebeast.com/metrics | grep request_count'

# 4. Verify no errors
watch -n 10 'curl -s https://api.knowledgebeast.com/metrics | grep error_rate'
```

---

## Testing & Validation

### DR Test Schedule

**Quarterly Full DR Test**:
- Simulate complete data center outage
- Execute full recovery procedure
- Measure RTO/RPO compliance
- Document findings and improvements

**Monthly Partial DR Test**:
- Test database restore from backup
- Verify backup integrity
- Test failover to secondary region (non-production)

**Weekly Backup Validation**:
- Automated integrity checks on all backups
- Restore to test environment
- Verify data completeness

### DR Test Procedure

**Preparation** (1 week before):
```bash
# 1. Schedule test in low-traffic window (Sunday 2 AM)
# 2. Notify stakeholders
slack-cli post -c announcements "DR test scheduled for Sunday 2025-10-15 at 2 AM"

# 3. Prepare test environment
terraform workspace select dr-test
terraform apply
```

**Execution** (4 hours):
```bash
# 1. Take snapshot of production
aws ec2 create-snapshot --volume-id vol-prod-xxx --description "DR test baseline"

# 2. Simulate disaster (on test environment)
kubectl delete namespace production --context dr-test

# 3. Execute recovery procedure (follow steps above)
# 4. Measure time for each step

# 5. Validate recovered system
pytest tests/dr-validation/
```

**Post-Test** (1 day after):
```bash
# 1. Document RTO/RPO achieved
# 2. Identify gaps or delays
# 3. Update DR plan
# 4. Conduct lessons-learned session
```

### Success Criteria

**Test Passes If**:
- ✅ RTO < 4 hours
- ✅ RPO < 1 hour
- ✅ All data integrity checks pass
- ✅ No manual intervention required (except DR trigger)
- ✅ All runbook steps are accurate

**Test Fails If**:
- ❌ RTO > 4 hours
- ❌ RPO > 1 hour
- ❌ Data corruption detected
- ❌ Runbook steps are outdated or incorrect

---

## Communication Plan

### Incident Severity Levels

| Severity | Description | Communication Frequency |
|----------|-------------|-------------------------|
| P0 (Critical) | Complete outage, data loss | Every 30 minutes |
| P1 (High) | Major degradation | Every 1 hour |
| P2 (Medium) | Minor degradation | Every 4 hours |
| P3 (Low) | No customer impact | Daily |

### Stakeholder Communication

**Internal**:
- **Engineering Team**: Slack #incidents (real-time updates)
- **Leadership**: Email + Slack #leadership (hourly updates)
- **Support Team**: Slack #support (updates every 30 min)

**External**:
- **Customers**: Email blast + status page (https://status.knowledgebeast.com)
- **Partners**: Dedicated email + phone call (for P0/P1)
- **Press** (if public): PR team handles communication

### Communication Templates

**Initial Notification** (within 15 minutes of DR activation):
```
Subject: [P0] KnowledgeBeast Service Disruption

We are experiencing a service disruption affecting all KnowledgeBeast users.

Impact: [Describe impact]
Status: Our team is actively investigating and implementing disaster recovery procedures.
Expected Resolution: We are targeting full service restoration within 4 hours.

We will provide updates every 30 minutes.

Status Page: https://status.knowledgebeast.com/incidents/[ID]
```

**Progress Update** (every 30 minutes for P0):
```
Subject: [P0] KnowledgeBeast Service Disruption - Update [N]

Current Status: [In Progress / Partially Restored / Resolved]

Progress:
- [Completed step 1]
- [Completed step 2]
- [Currently working on step 3]

Next Steps: [What we're doing next]

Revised ETA: [Updated timeline if changed]

Next update in 30 minutes.
```

**Resolution Notification**:
```
Subject: [RESOLVED] KnowledgeBeast Service Disruption

The KnowledgeBeast service disruption has been fully resolved.

Summary:
- Incident Start: [Time]
- Incident End: [Time]
- Total Duration: [Duration]
- Root Cause: [Brief description]

Actions Taken:
- [Action 1]
- [Action 2]

Data Impact:
- RPO Achieved: [Actual data loss]
- RTO Achieved: [Actual downtime]

We apologize for the inconvenience. A detailed postmortem will be published within 48 hours.

Thank you for your patience.
```

---

## Appendix: Recovery Scripts

### restore_chromadb.sh

```bash
#!/bin/bash
# Restore ChromaDB from backup

set -euo pipefail

BACKUP_FILE=$1
RESTORE_DIR="/data/chromadb"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "[$(date)] Starting ChromaDB restoration from $BACKUP_FILE"

# Stop ChromaDB service
kubectl scale deployment/chromadb -n production --replicas=0

# Extract backup
tar -xzf "$BACKUP_FILE" -C "$RESTORE_DIR"

# Restart ChromaDB
kubectl scale deployment/chromadb -n production --replicas=3

# Wait for ready
kubectl wait --for=condition=ready pod -l app=chromadb -n production --timeout=300s

echo "[$(date)] ChromaDB restoration complete"
```

### restore_sqlite.sh

```bash
#!/bin/bash
# Restore SQLite database from backup

set -euo pipefail

BACKUP_FILE=$1
RESTORE_PATH="/data/knowledgebeast.db"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "[$(date)] Starting SQLite restoration from $BACKUP_FILE"

# Stop application
kubectl scale deployment/knowledgebeast -n production --replicas=0

# Decompress if needed
if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" > /tmp/restore.db
    BACKUP_FILE=/tmp/restore.db
fi

# Verify backup integrity
if ! sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" | grep -q "ok"; then
    echo "Error: Backup integrity check failed"
    exit 1
fi

# Restore
cp "$BACKUP_FILE" "$RESTORE_PATH"

# Restart application
kubectl scale deployment/knowledgebeast -n production --replicas=3

echo "[$(date)] SQLite restoration complete"
```

---

## Revision History

| Version | Date       | Changes                                   |
|---------|------------|-------------------------------------------|
| 1.0     | 2025-10-08 | Initial disaster recovery plan            |

**Maintained by**: SRE Team
**Review Frequency**: Quarterly (after each DR test)
**Next Review**: 2026-01-08
