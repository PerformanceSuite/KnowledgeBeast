"""
Tests for Docker Compose observability stack configuration.

This module validates the Docker Compose configuration to ensure:
- Service definitions are valid
- Network configuration is correct
- Volume mounts are defined
- Port mappings are correct
"""

import yaml
import pytest
from pathlib import Path


# Path to Docker Compose file
DOCKER_COMPOSE_PATH = Path(__file__).parent.parent.parent / "deployments" / "docker-compose.observability.yml"


@pytest.fixture
def docker_compose_config():
    """Load the Docker Compose configuration."""
    with open(DOCKER_COMPOSE_PATH, 'r') as f:
        return yaml.safe_load(f)


class TestServiceDefinitions:
    """Test Docker Compose service definitions."""

    def test_service_definitions_valid(self, docker_compose_config):
        """Test that service definitions are valid."""
        assert docker_compose_config is not None
        assert isinstance(docker_compose_config, dict)
        assert 'services' in docker_compose_config

        services = docker_compose_config.get('services', {})
        required_services = ['prometheus', 'grafana', 'jaeger']

        for service in required_services:
            assert service in services, f"Service '{service}' should be defined"

    def test_all_services_have_images(self, docker_compose_config):
        """Test that all services have container images defined."""
        services = docker_compose_config.get('services', {})

        for service_name, service_config in services.items():
            # Skip commented out services
            if service_name.startswith('#'):
                continue

            assert 'image' in service_config, f"Service '{service_name}' should have an image"
            image = service_config.get('image')
            assert image, f"Service '{service_name}' image should not be empty"
            assert ':' in image, f"Service '{service_name}' image should have a tag"

    def test_services_have_healthchecks(self, docker_compose_config):
        """Test that critical services have health checks."""
        services = docker_compose_config.get('services', {})
        critical_services = ['prometheus', 'grafana', 'jaeger']

        for service_name in critical_services:
            service = services.get(service_name, {})
            assert 'healthcheck' in service, f"Service '{service_name}' should have a healthcheck"

            healthcheck = service.get('healthcheck', {})
            assert 'test' in healthcheck, f"Service '{service_name}' healthcheck should have a test"
            assert 'interval' in healthcheck, f"Service '{service_name}' healthcheck should have an interval"

    def test_services_have_restart_policies(self, docker_compose_config):
        """Test that services have restart policies."""
        services = docker_compose_config.get('services', {})

        for service_name, service_config in services.items():
            # Skip commented out services
            if service_name.startswith('#'):
                continue

            # node-exporter and others should have restart policies
            if service_name in ['prometheus', 'grafana', 'jaeger', 'node-exporter']:
                assert 'restart' in service_config, \
                    f"Service '{service_name}' should have a restart policy"


class TestNetworkConfiguration:
    """Test Docker Compose network configuration."""

    def test_network_configuration_correct(self, docker_compose_config):
        """Test that networks are configured correctly."""
        assert 'networks' in docker_compose_config
        networks = docker_compose_config.get('networks', {})

        assert 'observability' in networks, "observability network should be defined"

        observability_net = networks.get('observability', {})
        assert observability_net.get('name') == 'knowledgebeast-observability'
        assert observability_net.get('driver') == 'bridge'

    def test_services_connected_to_network(self, docker_compose_config):
        """Test that services are connected to the observability network."""
        services = docker_compose_config.get('services', {})
        critical_services = ['prometheus', 'grafana', 'jaeger']

        for service_name in critical_services:
            service = services.get(service_name, {})
            networks = service.get('networks', [])
            assert 'observability' in networks, \
                f"Service '{service_name}' should be connected to observability network"


class TestVolumeMounts:
    """Test Docker Compose volume mounts."""

    def test_volume_mounts_defined(self, docker_compose_config):
        """Test that volume mounts are defined for data persistence."""
        assert 'volumes' in docker_compose_config
        volumes = docker_compose_config.get('volumes', {})

        required_volumes = [
            'prometheus-data',
            'grafana-data',
            'jaeger-data'
        ]

        for volume in required_volumes:
            assert volume in volumes, f"Volume '{volume}' should be defined"

    def test_services_have_volume_mounts(self, docker_compose_config):
        """Test that services have volume mounts configured."""
        services = docker_compose_config.get('services', {})

        # Prometheus should mount config and data
        prometheus = services.get('prometheus', {})
        prometheus_volumes = prometheus.get('volumes', [])
        assert len(prometheus_volumes) >= 2, "Prometheus should have at least 2 volume mounts"

        # Check for config mounts
        config_mounts = [v for v in prometheus_volumes if 'prometheus.yml' in v]
        assert len(config_mounts) > 0, "Prometheus should mount prometheus.yml"

        # Check for data mount
        data_mounts = [v for v in prometheus_volumes if 'prometheus-data' in v]
        assert len(data_mounts) > 0, "Prometheus should mount prometheus-data volume"

        # Grafana should mount dashboards and datasources
        grafana = services.get('grafana', {})
        grafana_volumes = grafana.get('volumes', [])
        assert len(grafana_volumes) >= 3, "Grafana should have at least 3 volume mounts"

    def test_volume_names_have_prefix(self, docker_compose_config):
        """Test that volumes have knowledgebeast prefix."""
        volumes = docker_compose_config.get('volumes', {})

        for volume_name, volume_config in volumes.items():
            # Skip commented volumes
            if volume_name.startswith('#'):
                continue

            name = volume_config.get('name', '')
            assert name.startswith('knowledgebeast-'), \
                f"Volume '{volume_name}' should have 'knowledgebeast-' prefix"


class TestPortMappings:
    """Test Docker Compose port mappings."""

    def test_port_mappings_correct(self, docker_compose_config):
        """Test that port mappings are correct."""
        services = docker_compose_config.get('services', {})

        # Expected port mappings
        expected_ports = {
            'prometheus': ['9090:9090'],
            'grafana': ['3000:3000'],
            'jaeger': ['16686:16686', '4317:4317', '4318:4318']
        }

        for service_name, expected_port_list in expected_ports.items():
            service = services.get(service_name, {})
            ports = service.get('ports', [])

            for expected_port in expected_port_list:
                # Port can be string or dict format
                port_strings = [
                    p if isinstance(p, str) else f"{p.get('published')}:{p.get('target')}"
                    for p in ports
                ]
                assert expected_port in port_strings, \
                    f"Service '{service_name}' should expose port {expected_port}"

    def test_no_port_conflicts(self, docker_compose_config):
        """Test that there are no port conflicts between services."""
        services = docker_compose_config.get('services', {})

        published_ports = []
        for service_name, service_config in services.items():
            ports = service_config.get('ports', [])
            for port in ports:
                if isinstance(port, str):
                    published = port.split(':')[0]
                else:
                    published = str(port.get('published'))

                assert published not in published_ports, \
                    f"Port {published} is already in use"
                published_ports.append(published)
