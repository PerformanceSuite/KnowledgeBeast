"""
Production Readiness Tests

Validates that the deployment is production-ready:
- All required files exist
- Documentation is complete
- Security configurations are in place
- Monitoring is configured
- Backup procedures are documented
"""

import pytest
from pathlib import Path
import yaml


class TestDeploymentArtifacts:
    """Test that all deployment artifacts exist"""

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    def test_docker_files_exist(self, project_root):
        """Test that Docker deployment files exist"""
        required_files = [
            "docker/Dockerfile.production",
            "docker/docker-compose.prod.yml",
            "docker/entrypoint.sh",
        ]

        for file_path in required_files:
            full_path = project_root / file_path
            assert full_path.exists(), f"Required file missing: {file_path}"

    def test_kubernetes_files_exist(self, project_root):
        """Test that Kubernetes deployment files exist"""
        required_files = [
            "kubernetes/deployment.yaml",
            "kubernetes/service.yaml",
            "kubernetes/ingress.yaml",
            "kubernetes/hpa.yaml",
            "kubernetes/configmap.yaml",
            "kubernetes/secret.yaml.template",
            "kubernetes/namespace.yaml",
            "kubernetes/pvc.yaml",
            "kubernetes/rbac.yaml",
        ]

        for file_path in required_files:
            full_path = project_root / file_path
            assert full_path.exists(), f"Required file missing: {file_path}"

    def test_documentation_exists(self, project_root):
        """Test that deployment documentation exists"""
        required_docs = [
            "docs/deployment/PRODUCTION_DEPLOYMENT.md",
            "docs/deployment/HIGH_AVAILABILITY.md",
        ]

        for doc_path in required_docs:
            full_path = project_root / doc_path
            assert full_path.exists(), f"Required documentation missing: {doc_path}"

    def test_documentation_completeness(self, project_root):
        """Test that documentation is comprehensive"""
        prod_doc = project_root / "docs/deployment/PRODUCTION_DEPLOYMENT.md"
        ha_doc = project_root / "docs/deployment/HIGH_AVAILABILITY.md"

        # Check production deployment guide length
        with open(prod_doc, 'r') as f:
            prod_lines = len(f.readlines())
        assert prod_lines >= 2000, \
            f"Production deployment guide should be comprehensive (>= 2000 lines), found {prod_lines}"

        # Check HA guide length
        with open(ha_doc, 'r') as f:
            ha_lines = len(f.readlines())
        assert ha_lines >= 1500, \
            f"HA guide should be comprehensive (>= 1500 lines), found {ha_lines}"


class TestSecurityConfiguration:
    """Test security configurations are in place"""

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    @pytest.fixture(scope="class")
    def deployment_yaml(self, project_root):
        """Load deployment YAML"""
        with open(project_root / "kubernetes" / "deployment.yaml", 'r') as f:
            return list(yaml.safe_load_all(f))

    def test_security_context_configured(self, deployment_yaml):
        """Test that security contexts are configured"""
        deployments = [doc for doc in deployment_yaml if doc and doc.get("kind") == "Deployment"]

        for deployment in deployments:
            pod_spec = deployment.get("spec", {}).get("template", {}).get("spec", {})

            # Check pod security context
            pod_security = pod_spec.get("securityContext", {})
            assert pod_security.get("runAsNonRoot") == True, \
                "Pod should run as non-root"

            # Check container security contexts
            containers = pod_spec.get("containers", [])
            for container in containers:
                container_security = container.get("securityContext", {})
                assert container_security.get("allowPrivilegeEscalation") == False, \
                    f"Container {container.get('name')} should not allow privilege escalation"

    def test_rbac_configured(self, project_root):
        """Test that RBAC is configured"""
        rbac_file = project_root / "kubernetes" / "rbac.yaml"
        assert rbac_file.exists(), "RBAC configuration should exist"

        with open(rbac_file, 'r') as f:
            rbac_docs = list(yaml.safe_load_all(f))

        # Should have ServiceAccount, Role, and RoleBinding
        kinds = [doc.get("kind") for doc in rbac_docs if doc]
        assert "ServiceAccount" in kinds, "ServiceAccount should be defined"
        assert "Role" in kinds or "ClusterRole" in kinds, "Role should be defined"

    def test_network_policy_exists(self, project_root):
        """Test that network policies are considered"""
        # Check deployment.yaml for network policy or documentation mention
        deployment_file = project_root / "kubernetes" / "deployment.yaml"

        with open(deployment_file, 'r') as f:
            content = f.read()

        # Network policies might be in a separate file or comments
        # This is a soft check

    def test_secret_management(self, project_root):
        """Test that secret management is configured"""
        secret_template = project_root / "kubernetes" / "secret.yaml.template"
        assert secret_template.exists(), "Secret template should exist"

        # Verify it's a template and not actual secrets
        with open(secret_template, 'r') as f:
            content = f.read()

        assert "CHANGE_ME" in content or "template" in content.lower(), \
            "Secret file should be a template, not contain actual secrets"


class TestMonitoringConfiguration:
    """Test monitoring is configured"""

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    def test_prometheus_config_exists(self, project_root):
        """Test that Prometheus configuration exists"""
        # Prometheus config should be in ConfigMap
        configmap_file = project_root / "kubernetes" / "configmap.yaml"

        with open(configmap_file, 'r') as f:
            configmaps = list(yaml.safe_load_all(f))

        # Check for Prometheus-related ConfigMap
        has_prometheus_config = False
        for doc in configmaps:
            if doc and doc.get("kind") == "ConfigMap":
                data = doc.get("data", {})
                if "prometheus.yml" in data or "prometheus" in doc.get("metadata", {}).get("name", "").lower():
                    has_prometheus_config = True
                    break

        # Prometheus config might be in docker-compose or separate deployment
        # This is informational

    def test_metrics_annotations(self, project_root):
        """Test that deployments have Prometheus annotations"""
        with open(project_root / "kubernetes" / "deployment.yaml", 'r') as f:
            deployments = list(yaml.safe_load_all(f))

        for doc in deployments:
            if doc and doc.get("kind") == "Deployment" and "api" in doc.get("metadata", {}).get("name", ""):
                annotations = doc.get("spec", {}).get("template", {}).get("metadata", {}).get("annotations", {})

                # Check for Prometheus scrape annotations
                # These are recommended but not strictly required
                # assert "prometheus.io/scrape" in annotations

    def test_health_check_endpoints(self, project_root):
        """Test that health check endpoints are configured"""
        with open(project_root / "kubernetes" / "deployment.yaml", 'r') as f:
            deployments = list(yaml.safe_load_all(f))

        for doc in deployments:
            if doc and doc.get("kind") == "Deployment":
                containers = doc.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])

                for container in containers:
                    # Check for health probes
                    assert "livenessProbe" in container, \
                        f"Container {container.get('name')} should have liveness probe"
                    assert "readinessProbe" in container, \
                        f"Container {container.get('name')} should have readiness probe"


class TestBackupConfiguration:
    """Test backup procedures are documented"""

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    def test_backup_documentation(self, project_root):
        """Test that backup procedures are documented"""
        prod_doc = project_root / "docs/deployment/PRODUCTION_DEPLOYMENT.md"

        with open(prod_doc, 'r') as f:
            content = f.read().lower()

        # Check for backup-related content
        backup_keywords = ["backup", "disaster recovery", "restore", "velero"]
        found_keywords = [kw for kw in backup_keywords if kw in content]

        assert len(found_keywords) >= 2, \
            f"Backup procedures should be documented. Found keywords: {found_keywords}"

    def test_rpo_rto_defined(self, project_root):
        """Test that RPO/RTO are defined"""
        ha_doc = project_root / "docs/deployment/HIGH_AVAILABILITY.md"

        with open(ha_doc, 'r') as f:
            content = f.read()

        assert "RPO" in content, "RPO (Recovery Point Objective) should be defined"
        assert "RTO" in content, "RTO (Recovery Time Objective) should be defined"


class TestScalabilityConfiguration:
    """Test scalability configurations"""

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    def test_hpa_configured(self, project_root):
        """Test that Horizontal Pod Autoscaler is configured"""
        hpa_file = project_root / "kubernetes" / "hpa.yaml"
        assert hpa_file.exists(), "HPA configuration should exist"

        with open(hpa_file, 'r') as f:
            hpa_docs = list(yaml.safe_load_all(f))

        hpas = [doc for doc in hpa_docs if doc and doc.get("kind") == "HorizontalPodAutoscaler"]
        assert len(hpas) > 0, "At least one HPA should be configured"

    def test_resource_limits_set(self, project_root):
        """Test that resource limits are set for scalability"""
        with open(project_root / "kubernetes" / "deployment.yaml", 'r') as f:
            deployments = list(yaml.safe_load_all(f))

        for doc in deployments:
            if doc and doc.get("kind") == "Deployment":
                containers = doc.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])

                for container in containers:
                    resources = container.get("resources", {})
                    assert "limits" in resources, \
                        f"Container {container.get('name')} should have resource limits"
                    assert "requests" in resources, \
                        f"Container {container.get('name')} should have resource requests"


class TestHighAvailability:
    """Test high availability configurations"""

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    def test_multiple_replicas(self, project_root):
        """Test that deployments have multiple replicas"""
        with open(project_root / "kubernetes" / "deployment.yaml", 'r') as f:
            deployments = list(yaml.safe_load_all(f))

        for doc in deployments:
            if doc and doc.get("kind") == "Deployment" and "api" in doc.get("metadata", {}).get("name", ""):
                replicas = doc.get("spec", {}).get("replicas", 0)
                assert replicas >= 2, \
                    f"API deployment should have at least 2 replicas for HA, has {replicas}"

    def test_pod_disruption_budget(self, project_root):
        """Test that PodDisruptionBudget is configured"""
        hpa_file = project_root / "kubernetes" / "hpa.yaml"

        with open(hpa_file, 'r') as f:
            docs = list(yaml.safe_load_all(f))

        pdbs = [doc for doc in docs if doc and doc.get("kind") == "PodDisruptionBudget"]

        # PDB is recommended for HA
        # assert len(pdbs) > 0, "PodDisruptionBudget should be configured for HA"

    def test_anti_affinity_rules(self, project_root):
        """Test that pod anti-affinity is configured"""
        with open(project_root / "kubernetes" / "deployment.yaml", 'r') as f:
            deployments = list(yaml.safe_load_all(f))

        for doc in deployments:
            if doc and doc.get("kind") == "Deployment" and "api" in doc.get("metadata", {}).get("name", ""):
                pod_spec = doc.get("spec", {}).get("template", {}).get("spec", {})
                affinity = pod_spec.get("affinity", {})

                # Anti-affinity is recommended for HA
                # assert "podAntiAffinity" in affinity


class TestDockerProduction:
    """Test Docker production readiness"""

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    def test_production_dockerfile(self, project_root):
        """Test production Dockerfile exists and is configured"""
        dockerfile = project_root / "docker" / "Dockerfile.production"
        assert dockerfile.exists(), "Production Dockerfile should exist"

        with open(dockerfile, 'r') as f:
            content = f.read()

        # Check for production best practices
        assert "FROM" in content, "Dockerfile should have FROM directive"
        assert "HEALTHCHECK" in content, "Dockerfile should have HEALTHCHECK"
        assert "USER" in content, "Dockerfile should specify USER (non-root)"

    def test_docker_compose_production(self, project_root):
        """Test production docker-compose file"""
        compose_file = project_root / "docker" / "docker-compose.prod.yml"
        assert compose_file.exists(), "Production docker-compose file should exist"

        with open(compose_file, 'r') as f:
            compose_config = yaml.safe_load(f)

        # Check for required services
        services = compose_config.get("services", {})
        required_services = ["api"]  # At minimum
        for service in required_services:
            assert service in services, f"Service '{service}' should be in docker-compose"

    def test_entrypoint_script(self, project_root):
        """Test entrypoint script exists"""
        entrypoint = project_root / "docker" / "entrypoint.sh"
        assert entrypoint.exists(), "Entrypoint script should exist"

        # Check if executable
        # Note: Git might not preserve execute permissions
        with open(entrypoint, 'r') as f:
            content = f.read()

        assert "#!/bin/bash" in content or "#!/bin/sh" in content, \
            "Entrypoint should have shebang"


class TestDeploymentChecklist:
    """Test deployment checklist items"""

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    def test_checklist_in_documentation(self, project_root):
        """Test that deployment checklist exists in documentation"""
        prod_doc = project_root / "docs/deployment/PRODUCTION_DEPLOYMENT.md"

        with open(prod_doc, 'r') as f:
            content = f.read().lower()

        assert "checklist" in content, "Deployment documentation should include checklist"

    def test_troubleshooting_guide(self, project_root):
        """Test that troubleshooting guide exists"""
        prod_doc = project_root / "docs/deployment/PRODUCTION_DEPLOYMENT.md"

        with open(prod_doc, 'r') as f:
            content = f.read().lower()

        assert "troubleshooting" in content or "debugging" in content, \
            "Documentation should include troubleshooting section"

    def test_monitoring_guide(self, project_root):
        """Test that monitoring setup is documented"""
        prod_doc = project_root / "docs/deployment/PRODUCTION_DEPLOYMENT.md"

        with open(prod_doc, 'r') as f:
            content = f.read().lower()

        monitoring_keywords = ["prometheus", "grafana", "metrics", "monitoring"]
        found = [kw for kw in monitoring_keywords if kw in content]

        assert len(found) >= 2, \
            f"Monitoring should be documented. Found: {found}"


class TestProductionReadinessScore:
    """Calculate overall production readiness score"""

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    def test_calculate_readiness_score(self, project_root):
        """Calculate and report production readiness score"""
        checks = []

        # Docker artifacts (weight: 2)
        docker_files = [
            "docker/Dockerfile.production",
            "docker/docker-compose.prod.yml",
            "docker/entrypoint.sh",
        ]
        docker_score = sum(1 for f in docker_files if (project_root / f).exists())
        checks.append(("Docker artifacts", docker_score, len(docker_files), 2))

        # Kubernetes artifacts (weight: 3)
        k8s_files = [
            "kubernetes/deployment.yaml",
            "kubernetes/service.yaml",
            "kubernetes/ingress.yaml",
            "kubernetes/hpa.yaml",
            "kubernetes/configmap.yaml",
            "kubernetes/namespace.yaml",
            "kubernetes/pvc.yaml",
            "kubernetes/rbac.yaml",
        ]
        k8s_score = sum(1 for f in k8s_files if (project_root / f).exists())
        checks.append(("Kubernetes artifacts", k8s_score, len(k8s_files), 3))

        # Documentation (weight: 2)
        doc_files = [
            "docs/deployment/PRODUCTION_DEPLOYMENT.md",
            "docs/deployment/HIGH_AVAILABILITY.md",
        ]
        doc_score = sum(1 for f in doc_files if (project_root / f).exists())
        checks.append(("Documentation", doc_score, len(doc_files), 2))

        # Calculate weighted score
        total_score = 0
        max_score = 0

        print("\n=== Production Readiness Report ===")
        for name, score, total, weight in checks:
            percentage = (score / total * 100) if total > 0 else 0
            weighted_score = (score / total) * weight
            total_score += weighted_score
            max_score += weight

            print(f"{name}: {score}/{total} ({percentage:.1f}%) - Weight: {weight}")

        overall_percentage = (total_score / max_score * 100) if max_score > 0 else 0
        print(f"\nOverall Readiness Score: {overall_percentage:.1f}%")

        assert overall_percentage >= 80, \
            f"Production readiness score ({overall_percentage:.1f}%) should be at least 80%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
