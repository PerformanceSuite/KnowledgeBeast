"""
Tests for Grafana dashboard configuration.

This module validates the Grafana dashboard JSON configuration to ensure:
- Valid JSON syntax
- All 8 required panels are configured
- Panel queries use valid PromQL
- Time ranges are configured
- Auto-refresh is enabled
- Variables are defined correctly
"""

import json
import os
import re
import pytest
from pathlib import Path


# Path to the Grafana dashboard JSON
DASHBOARD_PATH = Path(__file__).parent.parent.parent / "deployments" / "grafana" / "dashboards" / "knowledgebeast-overview.json"


@pytest.fixture
def dashboard_config():
    """Load the Grafana dashboard JSON configuration."""
    with open(DASHBOARD_PATH, 'r') as f:
        return json.load(f)


class TestDashboardStructure:
    """Test the overall structure of the Grafana dashboard."""

    def test_dashboard_json_is_valid(self, dashboard_config):
        """Test that the dashboard JSON is valid and can be parsed."""
        assert dashboard_config is not None
        assert isinstance(dashboard_config, dict)
        assert 'panels' in dashboard_config
        assert 'title' in dashboard_config
        assert dashboard_config['title'] == 'KnowledgeBeast Overview'

    def test_all_8_panels_configured(self, dashboard_config):
        """Test that all 8 required panels are configured."""
        panels = dashboard_config.get('panels', [])
        assert len(panels) == 8, f"Expected 8 panels, found {len(panels)}"

        # Verify panel IDs are unique and sequential
        panel_ids = [p['id'] for p in panels]
        assert panel_ids == [1, 2, 3, 4, 5, 6, 7, 8]

        # Verify panel titles
        expected_titles = [
            "Query Latency (P50, P95, P99)",
            "Throughput (queries/sec)",
            "Cache Hit Ratio (%)",
            "Active Projects",
            "Vector Search Performance (Heatmap)",
            "Error Rate (errors/sec)",
            "ChromaDB Collection Sizes",
            "API Response Codes (2xx, 4xx, 5xx)"
        ]
        actual_titles = [p['title'] for p in panels]
        assert actual_titles == expected_titles


class TestPanelQueries:
    """Test that panel queries use valid PromQL."""

    def test_panel_queries_use_valid_promql(self, dashboard_config):
        """Test that all panel queries contain valid PromQL expressions."""
        panels = dashboard_config.get('panels', [])
        promql_functions = [
            'histogram_quantile', 'rate', 'sum', 'count',
            'avg', 'min', 'max', 'stddev', 'topk', 'bottomk'
        ]

        for panel in panels:
            targets = panel.get('targets', [])
            assert len(targets) > 0, f"Panel '{panel['title']}' has no targets"

            for target in targets:
                expr = target.get('expr', '')
                assert expr, f"Panel '{panel['title']}' has empty query"

                # Check for basic PromQL syntax
                # Should contain metric names or PromQL functions
                has_promql = any(func in expr for func in promql_functions) or \
                           'knowledgebeast_' in expr
                assert has_promql, f"Panel '{panel['title']}' query doesn't appear to be valid PromQL: {expr}"

    def test_latency_panel_has_three_percentiles(self, dashboard_config):
        """Test that the Query Latency panel has P50, P95, and P99 series."""
        panels = dashboard_config.get('panels', [])
        latency_panel = panels[0]  # First panel is Query Latency

        assert latency_panel['title'] == "Query Latency (P50, P95, P99)"
        targets = latency_panel.get('targets', [])
        assert len(targets) == 3, "Latency panel should have 3 targets (P50, P95, P99)"

        legend_formats = [t.get('legendFormat', '') for t in targets]
        assert 'P50' in legend_formats
        assert 'P95' in legend_formats
        assert 'P99' in legend_formats

    def test_pie_chart_has_three_series(self, dashboard_config):
        """Test that the API Response Codes panel has 2xx, 4xx, and 5xx series."""
        panels = dashboard_config.get('panels', [])
        pie_panel = panels[7]  # Last panel is API Response Codes

        assert pie_panel['title'] == "API Response Codes (2xx, 4xx, 5xx)"
        targets = pie_panel.get('targets', [])
        assert len(targets) == 3, "Pie chart should have 3 targets (2xx, 4xx, 5xx)"

        legend_formats = [t.get('legendFormat', '') for t in targets]
        assert '2xx' in legend_formats
        assert '4xx' in legend_formats
        assert '5xx' in legend_formats


class TestTimeConfiguration:
    """Test time range and refresh configuration."""

    def test_time_ranges_configured(self, dashboard_config):
        """Test that time ranges are configured correctly."""
        time_config = dashboard_config.get('time', {})
        assert time_config.get('from') == 'now-6h'
        assert time_config.get('to') == 'now'

    def test_auto_refresh_enabled(self, dashboard_config):
        """Test that auto-refresh is enabled."""
        refresh = dashboard_config.get('refresh', '')
        assert refresh == '30s', "Auto-refresh should be set to 30 seconds"

        timepicker = dashboard_config.get('timepicker', {})
        refresh_intervals = timepicker.get('refresh_intervals', [])
        assert '30s' in refresh_intervals
        assert len(refresh_intervals) > 0


class TestVariables:
    """Test dashboard variables and templating."""

    def test_variables_defined_correctly(self, dashboard_config):
        """Test that dashboard variables are defined."""
        templating = dashboard_config.get('templating', {})
        variable_list = templating.get('list', [])

        assert len(variable_list) > 0, "Dashboard should have at least one variable"

        # Check for time_range variable
        time_range_var = next(
            (v for v in variable_list if v.get('name') == 'time_range'),
            None
        )
        assert time_range_var is not None, "time_range variable should exist"
        assert time_range_var.get('type') == 'custom'

    def test_time_range_variable_has_options(self, dashboard_config):
        """Test that time_range variable has multiple options."""
        templating = dashboard_config.get('templating', {})
        variable_list = templating.get('list', [])
        time_range_var = next(v for v in variable_list if v.get('name') == 'time_range')

        options = time_range_var.get('options', [])
        assert len(options) >= 5, "time_range should have at least 5 options"

        # Check for common time ranges
        option_values = [opt.get('value') for opt in options]
        assert '1m' in option_values
        assert '5m' in option_values
        assert '15m' in option_values
        assert '1h' in option_values


class TestPanelConfiguration:
    """Test individual panel configurations."""

    def test_gauge_panel_configured(self, dashboard_config):
        """Test that the Cache Hit Ratio gauge panel is configured correctly."""
        panels = dashboard_config.get('panels', [])
        cache_panel = panels[2]  # Third panel is Cache Hit Ratio

        assert cache_panel['title'] == "Cache Hit Ratio (%)"
        assert cache_panel['type'] == 'gauge'

        field_config = cache_panel.get('fieldConfig', {})
        defaults = field_config.get('defaults', {})

        # Check thresholds
        thresholds = defaults.get('thresholds', {})
        steps = thresholds.get('steps', [])
        assert len(steps) >= 2, "Gauge should have threshold steps"

        # Check min/max
        assert defaults.get('min') == 0
        assert defaults.get('max') == 100
        assert defaults.get('unit') == 'percent'

    def test_heatmap_panel_configured(self, dashboard_config):
        """Test that the Vector Search Performance heatmap is configured correctly."""
        panels = dashboard_config.get('panels', [])
        heatmap_panel = panels[4]  # Fifth panel is Vector Search Performance

        assert heatmap_panel['title'] == "Vector Search Performance (Heatmap)"
        assert heatmap_panel['type'] == 'heatmap'

        targets = heatmap_panel.get('targets', [])
        assert len(targets) > 0
        assert targets[0].get('format') == 'heatmap'
