# Kubernetes Deployment

Deploy KnowledgeBeast on Kubernetes.

## Deployment YAML

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: knowledgebeast
spec:
  replicas: 2
  selector:
    matchLabels:
      app: knowledgebeast
  template:
    metadata:
      labels:
        app: knowledgebeast
    spec:
      containers:
      - name: knowledgebeast
        image: knowledgebeast:latest
        ports:
        - containerPort: 8000
        env:
        - name: KB_MAX_CACHE_SIZE
          value: "200"
        volumeMounts:
        - name: data
          mountPath: /app/data
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: kb-data-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: knowledgebeast
spec:
  selector:
    app: knowledgebeast
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

## PersistentVolumeClaim

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: kb-data-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

## ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: kb-config
data:
  KB_MAX_CACHE_SIZE: "200"
  KB_HEARTBEAT_INTERVAL: "300"
```

## Deploy

```bash
kubectl apply -f deployment.yaml
kubectl apply -f pvc.yaml
kubectl apply -f configmap.yaml
```

## Monitoring

```bash
kubectl get pods
kubectl logs -f deployment/knowledgebeast
kubectl describe deployment knowledgebeast
```
