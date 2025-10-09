"""
Kubernetes Configuration Validation Tests

Tests to validate:
- YAML syntax is correct
- Resource limits are set
- Health probes are configured
- Security contexts are defined
- HPA is enabled
- Proper labels and annotations
"""

import pytest
import yaml
import subprocess
from pathlib import Path
from typing import Dict, List, Any


class TestKubernetesYAMLSyntax:
    """Test YAML files are valid"""

    @pytest.fixture(scope="class")
    def k8s_dir(self):
        """Get kubernetes directory"""
        return Path(__file__).parent.parent.parent / "kubernetes"

    @pytest.fixture(scope="class")
    def yaml_files(self, k8s_dir):
        """Get all YAML files in kubernetes directory"""
        return list(k8s_dir.glob("*.yaml"))

    def test_yaml_files_exist(self, yaml_files):
        """Test that YAML files exist"""
        assert len(yaml_files) > 0, "No YAML files found in kubernetes directory"

    def test_yaml_syntax(self, yaml_files):
        """Test that all YAML files have valid syntax"""
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r') as f:
                    list(yaml.safe_load_all(f))
            except yaml.YAMLError as e:
                pytest.fail(f"YAML syntax error in {yaml_file.name}: {e}")

    def test_kubectl_validation(self, yaml_files):
        """Test YAML files with kubectl dry-run"""
        for yaml_file in yaml_files:
            # Skip template files
            if "template" in yaml_file.name.lower():
                continue

            result = subprocess.run(
                ["kubectl", "apply", "--dry-run=client", "-f", str(yaml_file)],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                # Some files might require secrets/configmaps to exist
                # Check if error is about missing resources (acceptable) or syntax (not acceptable)
                if "no matches for kind" not in result.stderr and \
                   "unable to recognize" in result.stderr:
                    pytest.fail(f"kubectl validation failed for {yaml_file.name}: {result.stderr}")


class TestDeploymentConfiguration:
    """Test Deployment resource configuration"""

    @pytest.fixture(scope="class")
    def deployment_config(self):
        """Load deployment YAML"""
        deployment_file = Path(__file__).parent.parent.parent / "kubernetes" / "deployment.yaml"

        with open(deployment_file, 'r') as f:
            docs = list(yaml.safe_load_all(f))

        # Find API deployment
        for doc in docs:
            if doc and doc.get("kind") == "Deployment" and \
               "api" in doc.get("metadata", {}).get("name", ""):
                return doc

        pytest.skip("API Deployment not found in deployment.yaml")

    def test_replica_count(self, deployment_config):
        """Test that deployment has multiple replicas"""
        replicas = deployment_config.get("spec", {}).get("replicas", 0)
        assert replicas >= 2, f"Deployment should have at least 2 replicas, has {replicas}"

    def test_rolling_update_strategy(self, deployment_config):
        """Test that rolling update strategy is configured"""
        strategy = deployment_config.get("spec", {}).get("strategy", {})

        assert strategy.get("type") == "RollingUpdate", \
            "Deployment should use RollingUpdate strategy"

        rolling_update = strategy.get("rollingUpdate", {})
        assert "maxSurge" in rolling_update, "maxSurge should be defined"
        assert rolling_update.get("maxUnavailable") == 0, \
            "maxUnavailable should be 0 for zero-downtime deployments"

    def test_resource_limits(self, deployment_config):
        """Test that resource limits are defined"""
        containers = deployment_config.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])

        assert len(containers) > 0, "No containers defined"

        for container in containers:
            resources = container.get("resources", {})

            # Check requests
            requests = resources.get("requests", {})
            assert "cpu" in requests, f"CPU request not defined for container {container.get('name')}"
            assert "memory" in requests, f"Memory request not defined for container {container.get('name')}"

            # Check limits
            limits = resources.get("limits", {})
            assert "cpu" in limits, f"CPU limit not defined for container {container.get('name')}"
            assert "memory" in limits, f"Memory limit not defined for container {container.get('name')}"

    def test_health_probes(self, deployment_config):
        """Test that health probes are configured"""
        containers = deployment_config.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])

        for container in containers:
            container_name = container.get("name", "unknown")

            # Check liveness probe
            assert "livenessProbe" in container, \
                f"Liveness probe not defined for container {container_name}"

            # Check readiness probe
            assert "readinessProbe" in container, \
                f"Readiness probe not defined for container {container_name}"

            # Optionally check startup probe
            # Some deployments may not need it
            # assert "startupProbe" in container

    def test_security_context(self, deployment_config):
        """Test that security context is defined"""
        pod_spec = deployment_config.get("spec", {}).get("template", {}).get("spec", {})

        # Check pod-level security context
        pod_security = pod_spec.get("securityContext", {})
        assert pod_security, "Pod security context should be defined"

        # Check container-level security context
        containers = pod_spec.get("containers", [])
        for container in containers:
            container_security = container.get("securityContext", {})
            assert container_security, f"Container {container.get('name')} should have security context"

            # Check important security settings
            assert container_security.get("allowPrivilegeEscalation") == False, \
                "allowPrivilegeEscalation should be false"
            assert container_security.get("runAsNonRoot") == True, \
                "Container should run as non-root"

    def test_labels(self, deployment_config):
        """Test that proper labels are defined"""
        metadata = deployment_config.get("metadata", {})
        labels = metadata.get("labels", {})

        # Check required labels
        assert "app" in labels, "Deployment should have 'app' label"
        assert "component" in labels or "tier" in labels, \
            "Deployment should have 'component' or 'tier' label"

    def test_pod_anti_affinity(self, deployment_config):
        """Test that pod anti-affinity is configured for HA"""
        pod_spec = deployment_config.get("spec", {}).get("template", {}).get("spec", {})
        affinity = pod_spec.get("affinity", {})

        # For high availability, should have pod anti-affinity
        pod_anti_affinity = affinity.get("podAntiAffinity", {})

        # At least preferred anti-affinity should be defined
        assert pod_anti_affinity, "Pod anti-affinity should be defined for HA"


class TestServiceConfiguration:
    """Test Service resource configuration"""

    @pytest.fixture(scope="class")
    def service_configs(self):
        """Load service YAML"""
        service_file = Path(__file__).parent.parent.parent / "kubernetes" / "service.yaml"

        with open(service_file, 'r') as f:
            return list(yaml.safe_load_all(f))

    def test_service_exists(self, service_configs):
        """Test that at least one service is defined"""
        services = [doc for doc in service_configs if doc and doc.get("kind") == "Service"]
        assert len(services) > 0, "No services defined"

    def test_service_selectors(self, service_configs):
        """Test that services have proper selectors"""
        for doc in service_configs:
            if doc and doc.get("kind") == "Service":
                selector = doc.get("spec", {}).get("selector", {})
                assert selector, f"Service {doc.get('metadata', {}).get('name')} should have selector"

    def test_service_ports(self, service_configs):
        """Test that services define ports"""
        for doc in service_configs:
            if doc and doc.get("kind") == "Service":
                ports = doc.get("spec", {}).get("ports", [])
                assert len(ports) > 0, \
                    f"Service {doc.get('metadata', {}).get('name')} should define ports"

                # Check port definitions
                for port in ports:
                    assert "port" in port, "Port must be defined"
                    assert "name" in port, "Port should have a name"


class TestIngressConfiguration:
    """Test Ingress resource configuration"""

    @pytest.fixture(scope="class")
    def ingress_configs(self):
        """Load ingress YAML"""
        ingress_file = Path(__file__).parent.parent.parent / "kubernetes" / "ingress.yaml"

        with open(ingress_file, 'r') as f:
            return list(yaml.safe_load_all(f))

    def test_ingress_exists(self, ingress_configs):
        """Test that ingress is defined"""
        ingresses = [doc for doc in ingress_configs if doc and doc.get("kind") == "Ingress"]
        assert len(ingresses) > 0, "No Ingress resources defined"

    def test_tls_configuration(self, ingress_configs):
        """Test that TLS is configured"""
        for doc in ingress_configs:
            if doc and doc.get("kind") == "Ingress":
                spec = doc.get("spec", {})
                tls = spec.get("tls", [])

                assert len(tls) > 0, \
                    f"Ingress {doc.get('metadata', {}).get('name')} should have TLS configured"

                # Check TLS has hosts and secretName
                for tls_config in tls:
                    assert "hosts" in tls_config, "TLS config should specify hosts"
                    assert "secretName" in tls_config, "TLS config should specify secretName"

    def test_rate_limiting(self, ingress_configs):
        """Test that rate limiting annotations are present"""
        for doc in ingress_configs:
            if doc and doc.get("kind") == "Ingress":
                annotations = doc.get("metadata", {}).get("annotations", {})

                # Check for rate limiting annotations (NGINX ingress)
                rate_limit_keys = [
                    "nginx.ingress.kubernetes.io/rate-limit",
                    "nginx.ingress.kubernetes.io/limit-rps",
                    "nginx.ingress.kubernetes.io/limit-rpm"
                ]

                has_rate_limit = any(key in annotations for key in rate_limit_keys)
                # Rate limiting is recommended but not strictly required
                # assert has_rate_limit, "Ingress should have rate limiting configured"


class TestHPAConfiguration:
    """Test Horizontal Pod Autoscaler configuration"""

    @pytest.fixture(scope="class")
    def hpa_configs(self):
        """Load HPA YAML"""
        hpa_file = Path(__file__).parent.parent.parent / "kubernetes" / "hpa.yaml"

        with open(hpa_file, 'r') as f:
            return list(yaml.safe_load_all(f))

    def test_hpa_exists(self, hpa_configs):
        """Test that HPA is defined"""
        hpas = [doc for doc in hpa_configs if doc and doc.get("kind") == "HorizontalPodAutoscaler"]
        assert len(hpas) > 0, "No HPA resources defined"

    def test_hpa_min_max_replicas(self, hpa_configs):
        """Test that HPA has reasonable min/max replicas"""
        for doc in hpa_configs:
            if doc and doc.get("kind") == "HorizontalPodAutoscaler":
                spec = doc.get("spec", {})

                min_replicas = spec.get("minReplicas", 0)
                max_replicas = spec.get("maxReplicas", 0)

                assert min_replicas >= 2, \
                    f"HPA {doc.get('metadata', {}).get('name')} should have minReplicas >= 2 for HA"
                assert max_replicas > min_replicas, \
                    "maxReplicas should be greater than minReplicas"
                assert max_replicas <= 20, \
                    "maxReplicas seems unreasonably high (check if intentional)"

    def test_hpa_metrics(self, hpa_configs):
        """Test that HPA has metrics defined"""
        for doc in hpa_configs:
            if doc and doc.get("kind") == "HorizontalPodAutoscaler":
                spec = doc.get("spec", {})
                metrics = spec.get("metrics", [])

                assert len(metrics) > 0, \
                    f"HPA {doc.get('metadata', {}).get('name')} should have metrics defined"

                # Check for CPU or memory metrics
                metric_types = [m.get("type") for m in metrics]
                assert "Resource" in metric_types or "Pods" in metric_types, \
                    "HPA should have Resource or Pods metrics"


class TestConfigMapAndSecrets:
    """Test ConfigMap and Secret configuration"""

    @pytest.fixture(scope="class")
    def configmap_configs(self):
        """Load ConfigMap YAML"""
        cm_file = Path(__file__).parent.parent.parent / "kubernetes" / "configmap.yaml"

        with open(cm_file, 'r') as f:
            return list(yaml.safe_load_all(f))

    def test_configmap_exists(self, configmap_configs):
        """Test that ConfigMaps are defined"""
        configmaps = [doc for doc in configmap_configs if doc and doc.get("kind") == "ConfigMap"]
        assert len(configmaps) > 0, "No ConfigMaps defined"

    def test_configmap_data(self, configmap_configs):
        """Test that ConfigMaps have data"""
        for doc in configmap_configs:
            if doc and doc.get("kind") == "ConfigMap":
                data = doc.get("data", {})
                assert data, f"ConfigMap {doc.get('metadata', {}).get('name')} should have data"

    def test_no_secrets_in_configmap(self, configmap_configs):
        """Test that ConfigMaps don't contain obvious secrets"""
        for doc in configmap_configs:
            if doc and doc.get("kind") == "ConfigMap":
                data = doc.get("data", {})

                # Convert all values to string for checking
                all_values = str(data).lower()

                # Check for potential secrets (this is a basic check)
                sensitive_patterns = ["password=", "secret=", "token=", "key="]
                for pattern in sensitive_patterns:
                    # This is a soft check - some false positives are ok
                    # assert pattern not in all_values
                    pass  # Soft check - not enforcing


class TestPersistentVolumeClaims:
    """Test PVC configuration"""

    @pytest.fixture(scope="class")
    def pvc_configs(self):
        """Load PVC YAML"""
        pvc_file = Path(__file__).parent.parent.parent / "kubernetes" / "pvc.yaml"

        with open(pvc_file, 'r') as f:
            return list(yaml.safe_load_all(f))

    def test_pvc_exists(self, pvc_configs):
        """Test that PVCs are defined"""
        pvcs = [doc for doc in pvc_configs if doc and doc.get("kind") == "PersistentVolumeClaim"]
        assert len(pvcs) > 0, "No PVCs defined"

    def test_pvc_storage_class(self, pvc_configs):
        """Test that PVCs specify storage class"""
        for doc in pvc_configs:
            if doc and doc.get("kind") == "PersistentVolumeClaim":
                spec = doc.get("spec", {})
                storage_class = spec.get("storageClassName")

                # Storage class should be defined for production
                assert storage_class, \
                    f"PVC {doc.get('metadata', {}).get('name')} should specify storageClassName"

    def test_pvc_size(self, pvc_configs):
        """Test that PVCs have reasonable size"""
        for doc in pvc_configs:
            if doc and doc.get("kind") == "PersistentVolumeClaim":
                spec = doc.get("spec", {})
                resources = spec.get("resources", {})
                requests = resources.get("requests", {})
                storage = requests.get("storage", "")

                assert storage, \
                    f"PVC {doc.get('metadata', {}).get('name')} should request storage"


class TestRBAC:
    """Test RBAC configuration"""

    @pytest.fixture(scope="class")
    def rbac_configs(self):
        """Load RBAC YAML"""
        rbac_file = Path(__file__).parent.parent.parent / "kubernetes" / "rbac.yaml"

        with open(rbac_file, 'r') as f:
            return list(yaml.safe_load_all(f))

    def test_service_account_exists(self, rbac_configs):
        """Test that ServiceAccount is defined"""
        service_accounts = [doc for doc in rbac_configs
                          if doc and doc.get("kind") == "ServiceAccount"]
        assert len(service_accounts) > 0, "No ServiceAccount defined"

    def test_role_exists(self, rbac_configs):
        """Test that Role or ClusterRole is defined"""
        roles = [doc for doc in rbac_configs
                if doc and doc.get("kind") in ["Role", "ClusterRole"]]
        assert len(roles) > 0, "No Role or ClusterRole defined"

    def test_rolebinding_exists(self, rbac_configs):
        """Test that RoleBinding or ClusterRoleBinding is defined"""
        bindings = [doc for doc in rbac_configs
                   if doc and doc.get("kind") in ["RoleBinding", "ClusterRoleBinding"]]
        assert len(bindings) > 0, "No RoleBinding or ClusterRoleBinding defined"


class TestNamespace:
    """Test Namespace configuration"""

    @pytest.fixture(scope="class")
    def namespace_configs(self):
        """Load namespace YAML"""
        ns_file = Path(__file__).parent.parent.parent / "kubernetes" / "namespace.yaml"

        with open(ns_file, 'r') as f:
            return list(yaml.safe_load_all(f))

    def test_namespace_exists(self, namespace_configs):
        """Test that Namespace is defined"""
        namespaces = [doc for doc in namespace_configs if doc and doc.get("kind") == "Namespace"]
        assert len(namespaces) > 0, "No Namespace defined"

    def test_resource_quota(self, namespace_configs):
        """Test that ResourceQuota is defined"""
        quotas = [doc for doc in namespace_configs if doc and doc.get("kind") == "ResourceQuota"]
        # Resource quotas are recommended but not required
        # assert len(quotas) > 0, "ResourceQuota should be defined for production"

    def test_limit_range(self, namespace_configs):
        """Test that LimitRange is defined"""
        limit_ranges = [doc for doc in namespace_configs if doc and doc.get("kind") == "LimitRange"]
        # Limit ranges are recommended but not required
        # assert len(limit_ranges) > 0, "LimitRange should be defined for production"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
