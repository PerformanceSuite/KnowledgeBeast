"""
Tests for Prometheus configuration.

This module validates the Prometheus configuration to ensure:
- Config file is valid YAML
- Scrape targets are defined
- Alert rules syntax is correct
- Retention period is set
- Evaluation interval is configured
"""

import yaml
import pytest
from pathlib import Path


# Paths to Prometheus configuration files
PROMETHEUS_CONFIG_PATH = Path(__file__).parent.parent.parent / "deployments" / "prometheus" / "prometheus.yml"
ALERTS_CONFIG_PATH = Path(__file__).parent.parent.parent / "deployments" / "prometheus" / "alerts.yml"


@pytest.fixture
def prometheus_config():
    """Load the Prometheus configuration."""
    with open(PROMETHEUS_CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)


@pytest.fixture
def alerts_config():
    """Load the Prometheus alerts configuration."""
    with open(ALERTS_CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)


class TestPrometheusConfig:
    """Test Prometheus main configuration."""

    def test_config_file_valid_yaml(self, prometheus_config):
        """Test that prometheus.yml is valid YAML."""
        assert prometheus_config is not None
        assert isinstance(prometheus_config, dict)
        assert 'global' in prometheus_config
        assert 'scrape_configs' in prometheus_config

    def test_scrape_targets_defined(self, prometheus_config):
        """Test that scrape targets are defined."""
        scrape_configs = prometheus_config.get('scrape_configs', [])
        assert len(scrape_configs) >= 2, "Should have at least 2 scrape configs (knowledgebeast, prometheus)"

        # Check for KnowledgeBeast job
        kb_job = next(
            (job for job in scrape_configs if job.get('job_name') == 'knowledgebeast'),
            None
        )
        assert kb_job is not None, "knowledgebeast job should be defined"
        assert kb_job.get('metrics_path') == '/metrics'

        # Check static configs
        static_configs = kb_job.get('static_configs', [])
        assert len(static_configs) > 0
        assert 'targets' in static_configs[0]

    def test_retention_period_set(self, prometheus_config):
        """Test that retention period is configured."""
        storage = prometheus_config.get('storage', {})
        tsdb = storage.get('tsdb', {})

        # Check for retention time
        retention_time = tsdb.get('retention.time')
        assert retention_time == '30d', "Retention period should be 30 days"

    def test_evaluation_interval_configured(self, prometheus_config):
        """Test that evaluation interval is configured."""
        global_config = prometheus_config.get('global', {})

        scrape_interval = global_config.get('scrape_interval')
        assert scrape_interval == '15s', "Scrape interval should be 15s"

        evaluation_interval = global_config.get('evaluation_interval')
        assert evaluation_interval == '15s', "Evaluation interval should be 15s"

    def test_rule_files_configured(self, prometheus_config):
        """Test that rule files are configured."""
        rule_files = prometheus_config.get('rule_files', [])
        assert len(rule_files) > 0, "Rule files should be configured"
        assert '/etc/prometheus/alerts.yml' in rule_files

    def test_external_labels_configured(self, prometheus_config):
        """Test that external labels are configured."""
        global_config = prometheus_config.get('global', {})
        external_labels = global_config.get('external_labels', {})

        assert 'cluster' in external_labels
        assert 'environment' in external_labels


class TestPrometheusAlerts:
    """Test Prometheus alert rules."""

    def test_alert_rules_syntax_correct(self, alerts_config):
        """Test that alert rules have correct syntax."""
        assert alerts_config is not None
        assert isinstance(alerts_config, dict)
        assert 'groups' in alerts_config

        groups = alerts_config.get('groups', [])
        assert len(groups) > 0, "Should have at least one alert group"

    def test_all_required_alerts_defined(self, alerts_config):
        """Test that all 7 required alerts are defined."""
        groups = alerts_config.get('groups', [])
        all_rules = []
        for group in groups:
            all_rules.extend(group.get('rules', []))

        alert_names = [rule.get('alert') for rule in all_rules]

        # Check for required alerts
        required_alerts = [
            'HighLatency_Warning',
            'HighLatency_Critical',
            'HighErrorRate',
            'ChromaDBDown',
            'LowCacheHitRatio',
            'DiskSpaceWarning',
            'DiskSpaceCritical'
        ]

        for alert in required_alerts:
            assert alert in alert_names, f"Alert '{alert}' should be defined"

    def test_critical_alerts_have_correct_severity(self, alerts_config):
        """Test that critical alerts have severity: critical label."""
        groups = alerts_config.get('groups', [])
        all_rules = []
        for group in groups:
            all_rules.extend(group.get('rules', []))

        critical_alerts = ['HighLatency_Critical', 'ChromaDBDown', 'DiskSpaceCritical']

        for rule in all_rules:
            alert_name = rule.get('alert')
            if alert_name in critical_alerts:
                labels = rule.get('labels', {})
                assert labels.get('severity') == 'critical', \
                    f"Alert '{alert_name}' should have severity: critical"

    def test_alerts_have_annotations(self, alerts_config):
        """Test that all alerts have annotations."""
        groups = alerts_config.get('groups', [])
        all_rules = []
        for group in groups:
            all_rules.extend(group.get('rules', []))

        for rule in all_rules:
            alert_name = rule.get('alert')
            if alert_name:  # Only check alert rules, not recording rules
                annotations = rule.get('annotations', {})
                assert 'summary' in annotations, f"Alert '{alert_name}' should have summary annotation"
                assert 'description' in annotations, f"Alert '{alert_name}' should have description annotation"

    def test_alerts_have_proper_durations(self, alerts_config):
        """Test that alerts have appropriate 'for' durations."""
        groups = alerts_config.get('groups', [])
        all_rules = []
        for group in groups:
            all_rules.extend(group.get('rules', []))

        # Critical alerts should have shorter durations
        critical_alerts = {
            'HighLatency_Critical': '2m',
            'ChromaDBDown': '0m',  # Immediate
            'DiskSpaceCritical': '2m'
        }

        for rule in all_rules:
            alert_name = rule.get('alert')
            if alert_name in critical_alerts:
                expected_duration = critical_alerts[alert_name]
                actual_duration = rule.get('for', '0m')
                assert actual_duration == expected_duration, \
                    f"Alert '{alert_name}' should have duration '{expected_duration}'"

    def test_alert_groups_have_intervals(self, alerts_config):
        """Test that alert groups have evaluation intervals."""
        groups = alerts_config.get('groups', [])

        for group in groups:
            group_name = group.get('name')
            interval = group.get('interval')
            assert interval is not None, f"Group '{group_name}' should have an interval"
