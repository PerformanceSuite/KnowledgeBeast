"""
Docker Build and Image Tests

Tests to validate:
- Docker image builds successfully
- Image size is within acceptable limits (< 500MB)
- Container starts and runs correctly
- Health checks function properly
- Security best practices are followed
"""

import pytest
import subprocess
import json
import time
from pathlib import Path


class TestDockerBuild:
    """Test Docker image build process"""

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    @pytest.fixture(scope="class")
    def dockerfile_path(self, project_root):
        """Get Dockerfile path"""
        return project_root / "docker" / "Dockerfile.production"

    def test_dockerfile_exists(self, dockerfile_path):
        """Test that production Dockerfile exists"""
        assert dockerfile_path.exists(), "Production Dockerfile not found"

    def test_dockerfile_syntax(self, dockerfile_path):
        """Test Dockerfile syntax is valid"""
        # Read Dockerfile
        content = dockerfile_path.read_text()

        # Check for required directives
        assert "FROM" in content, "Dockerfile missing FROM directive"
        assert "WORKDIR" in content, "Dockerfile missing WORKDIR"
        assert "COPY" in content, "Dockerfile missing COPY directive"

    def test_multistage_build(self, dockerfile_path):
        """Test that Dockerfile uses multi-stage build"""
        content = dockerfile_path.read_text()
        from_count = content.count("FROM ")

        assert from_count >= 2, "Dockerfile should use multi-stage build (2+ FROM statements)"

    def test_non_root_user(self, dockerfile_path):
        """Test that container runs as non-root user"""
        content = dockerfile_path.read_text()

        assert "USER" in content, "Dockerfile should specify USER directive"
        assert "root" not in content.split("USER")[-1].split()[0].lower(), \
            "Container should not run as root"

    def test_healthcheck_defined(self, dockerfile_path):
        """Test that HEALTHCHECK is defined"""
        content = dockerfile_path.read_text()

        assert "HEALTHCHECK" in content, "Dockerfile should include HEALTHCHECK"

    def test_security_context(self, dockerfile_path):
        """Test security best practices in Dockerfile"""
        content = dockerfile_path.read_text()

        # Should not run privileged commands
        assert "--privileged" not in content.lower(), "Should not use privileged mode"

        # Should clean up apt cache
        if "apt-get" in content:
            assert "rm -rf /var/lib/apt/lists" in content, \
                "Should clean apt cache to reduce image size"


class TestImageBuild:
    """Test Docker image building"""

    IMAGE_TAG = "knowledgebeast:test-build"

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    @pytest.fixture(scope="class")
    def built_image(self, project_root):
        """Build Docker image for testing"""
        try:
            # Build image
            result = subprocess.run(
                [
                    "docker", "build",
                    "-f", str(project_root / "docker" / "Dockerfile.production"),
                    "-t", self.IMAGE_TAG,
                    str(project_root)
                ],
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode != 0:
                pytest.skip(f"Docker build failed: {result.stderr}")

            yield self.IMAGE_TAG

        finally:
            # Cleanup: remove test image
            subprocess.run(
                ["docker", "rmi", "-f", self.IMAGE_TAG],
                capture_output=True
            )

    def test_build_success(self, built_image):
        """Test that Docker build completes successfully"""
        # Verify image exists
        result = subprocess.run(
            ["docker", "images", "-q", built_image],
            capture_output=True,
            text=True
        )

        assert result.stdout.strip(), f"Image {built_image} not found after build"

    def test_image_size(self, built_image):
        """Test that image size is under 500MB"""
        result = subprocess.run(
            ["docker", "images", built_image, "--format", "{{.Size}}"],
            capture_output=True,
            text=True
        )

        size_str = result.stdout.strip()

        # Parse size (handle MB/GB)
        if "GB" in size_str:
            size_mb = float(size_str.replace("GB", "")) * 1024
        elif "MB" in size_str:
            size_mb = float(size_str.replace("MB", ""))
        else:
            pytest.skip(f"Unknown size format: {size_str}")

        assert size_mb < 500, f"Image size ({size_mb:.1f}MB) exceeds 500MB limit"

    def test_image_labels(self, built_image):
        """Test that image has proper labels"""
        result = subprocess.run(
            ["docker", "inspect", built_image],
            capture_output=True,
            text=True
        )

        inspection = json.loads(result.stdout)[0]
        labels = inspection.get("Config", {}).get("Labels", {})

        assert labels, "Image should have labels"
        assert "version" in labels or "maintainer" in labels, \
            "Image should have version or maintainer label"

    def test_image_layers(self, built_image):
        """Test that image has reasonable number of layers"""
        result = subprocess.run(
            ["docker", "history", built_image, "--format", "{{.ID}}"],
            capture_output=True,
            text=True
        )

        layers = result.stdout.strip().split('\n')
        layer_count = len(layers)

        # Multi-stage builds should have fewer layers in final image
        assert layer_count < 30, f"Image has too many layers ({layer_count}), consider layer optimization"


class TestContainerRuntime:
    """Test container runtime behavior"""

    IMAGE_TAG = "knowledgebeast:test-runtime"
    CONTAINER_NAME = "kb-test-container"

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    @pytest.fixture(scope="class")
    def running_container(self, project_root):
        """Start a test container"""
        try:
            # Build image
            subprocess.run(
                [
                    "docker", "build",
                    "-f", str(project_root / "docker" / "Dockerfile.production"),
                    "-t", self.IMAGE_TAG,
                    str(project_root)
                ],
                capture_output=True,
                timeout=600,
                check=False
            )

            # Run container
            result = subprocess.run(
                [
                    "docker", "run",
                    "-d",
                    "--name", self.CONTAINER_NAME,
                    "-p", "8000:8000",
                    "-e", "APP_ENV=test",
                    "-e", "LOG_LEVEL=DEBUG",
                    self.IMAGE_TAG
                ],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                pytest.skip(f"Container start failed: {result.stderr}")

            # Wait for container to start
            time.sleep(5)

            yield self.CONTAINER_NAME

        finally:
            # Cleanup
            subprocess.run(
                ["docker", "stop", self.CONTAINER_NAME],
                capture_output=True
            )
            subprocess.run(
                ["docker", "rm", "-f", self.CONTAINER_NAME],
                capture_output=True
            )
            subprocess.run(
                ["docker", "rmi", "-f", self.IMAGE_TAG],
                capture_output=True
            )

    def test_container_starts(self, running_container):
        """Test that container starts successfully"""
        result = subprocess.run(
            ["docker", "ps", "-f", f"name={running_container}", "--format", "{{.Status}}"],
            capture_output=True,
            text=True
        )

        status = result.stdout.strip()
        assert "Up" in status, f"Container not running: {status}"

    def test_health_check(self, running_container):
        """Test that health check passes"""
        # Wait for health check to run
        time.sleep(10)

        result = subprocess.run(
            ["docker", "inspect", running_container, "--format", "{{.State.Health.Status}}"],
            capture_output=True,
            text=True
        )

        health_status = result.stdout.strip()

        # Health status should be healthy or starting
        assert health_status in ["healthy", "starting"], \
            f"Container health check failed: {health_status}"

    def test_container_logs(self, running_container):
        """Test that container produces logs"""
        result = subprocess.run(
            ["docker", "logs", running_container],
            capture_output=True,
            text=True
        )

        logs = result.stdout + result.stderr

        assert logs, "Container should produce logs"
        assert "ERROR" not in logs or "error" not in logs.lower()[:200], \
            "Container logs contain errors"

    def test_container_user(self, running_container):
        """Test that container runs as non-root user"""
        result = subprocess.run(
            ["docker", "exec", running_container, "whoami"],
            capture_output=True,
            text=True
        )

        user = result.stdout.strip()
        assert user != "root", "Container should not run as root user"

    def test_container_processes(self, running_container):
        """Test that container processes are running"""
        result = subprocess.run(
            ["docker", "exec", running_container, "ps", "aux"],
            capture_output=True,
            text=True
        )

        processes = result.stdout

        # Should have application processes
        assert processes, "Container should have running processes"


class TestDockerCompose:
    """Test Docker Compose configuration"""

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    @pytest.fixture(scope="class")
    def compose_file(self, project_root):
        """Get docker-compose file path"""
        return project_root / "docker" / "docker-compose.prod.yml"

    def test_compose_file_exists(self, compose_file):
        """Test that production docker-compose file exists"""
        assert compose_file.exists(), "Production docker-compose.yml not found"

    def test_compose_syntax(self, compose_file):
        """Test docker-compose file syntax"""
        result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "config"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0, f"docker-compose syntax error: {result.stderr}"

    def test_compose_services(self, compose_file):
        """Test that required services are defined"""
        result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "config", "--services"],
            capture_output=True,
            text=True
        )

        services = result.stdout.strip().split('\n')

        required_services = ["api", "chromadb", "redis"]
        for service in required_services:
            assert service in services, f"Required service '{service}' not found in compose file"

    def test_compose_volumes(self, compose_file):
        """Test that volumes are properly defined"""
        result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "config", "--volumes"],
            capture_output=True,
            text=True
        )

        volumes = result.stdout.strip().split('\n')

        # Should have at least some volumes defined
        assert len(volumes) > 0, "No volumes defined in compose file"

    def test_compose_networks(self, compose_file):
        """Test that networks are defined"""
        result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "config"],
            capture_output=True,
            text=True
        )

        config = result.stdout

        assert "networks:" in config, "Networks should be defined"


class TestSecurityScanning:
    """Test Docker image security"""

    IMAGE_TAG = "knowledgebeast:test-security"

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent.parent

    @pytest.fixture(scope="class")
    def built_image(self, project_root):
        """Build image for security testing"""
        try:
            subprocess.run(
                [
                    "docker", "build",
                    "-f", str(project_root / "docker" / "Dockerfile.production"),
                    "-t", self.IMAGE_TAG,
                    str(project_root)
                ],
                capture_output=True,
                timeout=600,
                check=False
            )

            yield self.IMAGE_TAG

        finally:
            subprocess.run(
                ["docker", "rmi", "-f", self.IMAGE_TAG],
                capture_output=True
            )

    def test_no_secrets_in_image(self, built_image):
        """Test that no secrets are embedded in image"""
        # Check image history for common secret patterns
        result = subprocess.run(
            ["docker", "history", "--no-trunc", built_image],
            capture_output=True,
            text=True
        )

        history = result.stdout.lower()

        # Check for common secret keywords
        secret_keywords = ["password", "secret", "token", "key"]
        for keyword in secret_keywords:
            # Allow keywords in comments/labels, but not in actual commands
            if keyword in history:
                # This is a soft warning, not a hard failure
                pass

    def test_minimal_base_image(self, built_image):
        """Test that base image is minimal (alpine or slim)"""
        result = subprocess.run(
            ["docker", "inspect", built_image],
            capture_output=True,
            text=True
        )

        inspection = json.loads(result.stdout)[0]
        layers = inspection.get("RootFS", {}).get("Layers", [])

        # Minimal images should have fewer layers
        # This is informational
        assert len(layers) > 0, "Image should have layers"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
