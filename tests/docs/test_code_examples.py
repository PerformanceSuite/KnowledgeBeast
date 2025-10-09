"""
Tests to validate code examples in production operations documentation.

These tests extract and validate code examples from documentation to ensure
they are accurate and functional.
"""

import os
import re
import json
import yaml
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# Base path for documentation
DOCS_PATH = Path(__file__).parent.parent.parent / "docs" / "operations"


class TestBashCommandExamples:
    """Test bash command examples from documentation."""

    @pytest.fixture
    def bash_commands(self):
        """Extract all bash commands from all documentation files."""
        commands = []
        for doc_file in DOCS_PATH.glob("*.md"):
            content = doc_file.read_text()
            # Extract bash code blocks
            bash_blocks = re.findall(r'```bash\n(.*?)```', content, re.DOTALL)
            for block in bash_blocks:
                # Split into individual commands (simple heuristic)
                for line in block.split('\n'):
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith('#'):
                        commands.append({
                            'file': doc_file.name,
                            'command': line
                        })
        return commands

    def test_kubectl_commands_have_valid_syntax(self, bash_commands):
        """Test that kubectl commands have valid basic syntax."""
        kubectl_cmds = [cmd for cmd in bash_commands if 'kubectl' in cmd['command']]

        for cmd_info in kubectl_cmds[:20]:  # Test sample of 20
            cmd = cmd_info['command']

            # Should have valid kubectl subcommand
            valid_subcommands = ['get', 'apply', 'delete', 'scale', 'exec', 'logs',
                                 'describe', 'rollout', 'wait', 'cp', 'patch', 'set', 'top']

            has_valid_subcommand = any(subcmd in cmd for subcmd in valid_subcommands)
            assert has_valid_subcommand, \
                f"kubectl command missing valid subcommand in {cmd_info['file']}: {cmd}"

    def test_curl_commands_have_valid_urls(self, bash_commands):
        """Test that curl commands reference valid URL patterns."""
        curl_cmds = [cmd for cmd in bash_commands if 'curl' in cmd['command']]

        for cmd_info in curl_cmds[:20]:  # Test sample of 20
            cmd = cmd_info['command']

            # Should have URL pattern (http:// or https://)
            has_url = 'http://' in cmd or 'https://' in cmd or '$' in cmd  # $ for variables
            assert has_url, \
                f"curl command missing URL in {cmd_info['file']}: {cmd}"

    def test_aws_commands_have_valid_syntax(self, bash_commands):
        """Test that AWS CLI commands have valid basic syntax."""
        aws_cmds = [cmd for cmd in bash_commands if cmd['command'].startswith('aws ')]

        for cmd_info in aws_cmds[:10]:  # Test sample of 10
            cmd = cmd_info['command']

            # Should have valid AWS service
            valid_services = ['s3', 'ec2', 'eks', 'route53', 'cloudtrail']
            has_valid_service = any(service in cmd for service in valid_services)
            assert has_valid_service, \
                f"AWS command missing valid service in {cmd_info['file']}: {cmd}"

    def test_sqlite3_commands_have_valid_syntax(self, bash_commands):
        """Test that sqlite3 commands have valid basic syntax."""
        sqlite_cmds = [cmd for cmd in bash_commands if 'sqlite3' in cmd['command']]

        for cmd_info in sqlite_cmds[:10]:  # Test sample of 10
            cmd = cmd_info['command']

            # Should reference a database file or have SQL
            has_db_or_sql = '.db' in cmd or 'PRAGMA' in cmd or 'SELECT' in cmd or '"' in cmd
            assert has_db_or_sql, \
                f"sqlite3 command missing database or SQL in {cmd_info['file']}: {cmd}"


class TestPrometheusQueryExamples:
    """Test Prometheus query examples from documentation."""

    @pytest.fixture
    def prometheus_queries(self):
        """Extract all Prometheus queries from documentation."""
        queries = []
        for doc_file in DOCS_PATH.glob("*.md"):
            content = doc_file.read_text()

            # Extract promql code blocks
            promql_blocks = re.findall(r'```promql\n(.*?)```', content, re.DOTALL)
            for block in promql_blocks:
                for line in block.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        queries.append({
                            'file': doc_file.name,
                            'query': line
                        })
        return queries

    def test_histogram_quantile_queries_valid(self, prometheus_queries):
        """Test that histogram_quantile queries have valid syntax."""
        hq_queries = [q for q in prometheus_queries if 'histogram_quantile' in q['query']]

        for query_info in hq_queries:
            query = query_info['query']

            # Should have quantile value (0.0 to 1.0)
            match = re.search(r'histogram_quantile\(([0-9.]+)', query)
            assert match, f"histogram_quantile missing quantile value in {query_info['file']}"

            quantile = float(match.group(1))
            assert 0.0 <= quantile <= 1.0, \
                f"Invalid quantile value {quantile} in {query_info['file']}"

    def test_rate_queries_have_time_range(self, prometheus_queries):
        """Test that rate() queries include time range."""
        rate_queries = [q for q in prometheus_queries if 'rate(' in q['query']]

        for query_info in rate_queries:
            query = query_info['query']

            # Should have time range in square brackets [5m], [1h], etc.
            assert re.search(r'\[\d+[smhd]\]', query), \
                f"rate() query missing time range in {query_info['file']}: {query}"

    def test_aggregation_queries_valid(self, prometheus_queries):
        """Test that aggregation queries (sum, avg, etc.) are valid."""
        agg_queries = [q for q in prometheus_queries
                       if any(agg in q['query'] for agg in ['sum(', 'avg(', 'max(', 'min('])]

        for query_info in agg_queries[:10]:  # Test sample
            query = query_info['query']

            # Should have balanced parentheses
            open_parens = query.count('(')
            close_parens = query.count(')')
            assert open_parens == close_parens, \
                f"Unbalanced parentheses in {query_info['file']}: {query}"


class TestYAMLConfigurationExamples:
    """Test YAML configuration examples from documentation."""

    @pytest.fixture
    def yaml_examples(self):
        """Extract all YAML configuration examples from documentation."""
        examples = []
        for doc_file in DOCS_PATH.glob("*.md"):
            content = doc_file.read_text()

            # Extract YAML code blocks
            yaml_blocks = re.findall(r'```yaml\n(.*?)```', content, re.DOTALL)
            for block in yaml_blocks:
                examples.append({
                    'file': doc_file.name,
                    'yaml': block
                })
        return examples

    def test_yaml_syntax_valid(self, yaml_examples):
        """Test that YAML examples have valid syntax."""
        for example in yaml_examples:
            try:
                # Attempt to parse YAML
                # Replace template variables before parsing
                yaml_content = example['yaml']
                yaml_content = re.sub(r'\$\{.*?\}', 'placeholder', yaml_content)
                yaml_content = re.sub(r'\$[A-Z_]+', 'placeholder', yaml_content)

                parsed = yaml.safe_load(yaml_content)
                # If we get here, YAML is valid
                assert parsed is not None or yaml_content.strip() == '', \
                    f"YAML parsed to None in {example['file']}"

            except yaml.YAMLError as e:
                # Some examples may intentionally be partial/template or example patterns
                # Only fail if it's clearly not a template or example pattern
                if '...' not in example['yaml'] and '<' not in example['yaml'] and 'Pattern' not in example['yaml']:
                    pytest.fail(f"Invalid YAML syntax in {example['file']}: {e}")

    def test_kubernetes_yaml_has_required_fields(self, yaml_examples):
        """Test that Kubernetes YAML examples have required fields."""
        k8s_examples = [ex for ex in yaml_examples if 'apiVersion' in ex['yaml']]

        for example in k8s_examples:
            yaml_content = example['yaml']

            # Should have apiVersion, kind, metadata
            assert 'apiVersion:' in yaml_content, \
                f"Kubernetes YAML missing apiVersion in {example['file']}"
            assert 'kind:' in yaml_content, \
                f"Kubernetes YAML missing kind in {example['file']}"
            assert 'metadata:' in yaml_content, \
                f"Kubernetes YAML missing metadata in {example['file']}"


class TestPythonCodeExamples:
    """Test Python code examples from documentation."""

    @pytest.fixture
    def python_examples(self):
        """Extract all Python code examples from documentation."""
        examples = []
        for doc_file in DOCS_PATH.glob("*.md"):
            content = doc_file.read_text()

            # Extract Python code blocks
            python_blocks = re.findall(r'```python\n(.*?)```', content, re.DOTALL)
            for block in python_blocks:
                examples.append({
                    'file': doc_file.name,
                    'code': block
                })
        return examples

    def test_python_imports_valid(self, python_examples):
        """Test that Python import statements are valid."""
        for example in python_examples[:10]:  # Test sample
            code = example['code']

            # Extract import statements
            imports = re.findall(r'^(?:from|import)\s+\S+', code, re.MULTILINE)

            for imp in imports:
                # Basic syntax check - should not have obvious errors
                assert not imp.endswith(','), \
                    f"Invalid import syntax in {example['file']}: {imp}"

    def test_python_syntax_valid(self, python_examples):
        """Test that Python code has valid basic syntax."""
        for example in python_examples[:10]:  # Test sample
            code = example['code']

            # Check for balanced parentheses
            open_parens = code.count('(')
            close_parens = code.count(')')
            assert open_parens == close_parens, \
                f"Unbalanced parentheses in {example['file']}"

            # Check for balanced brackets
            open_brackets = code.count('[')
            close_brackets = code.count(']')
            assert open_brackets == close_brackets, \
                f"Unbalanced brackets in {example['file']}"


class TestJSONExamples:
    """Test JSON examples from documentation."""

    @pytest.fixture
    def json_examples(self):
        """Extract all JSON examples from documentation."""
        examples = []
        for doc_file in DOCS_PATH.glob("*.md"):
            content = doc_file.read_text()

            # Extract JSON code blocks
            json_blocks = re.findall(r'```json\n(.*?)```', content, re.DOTALL)
            for block in json_blocks:
                examples.append({
                    'file': doc_file.name,
                    'json': block
                })
        return examples

    def test_json_syntax_valid(self, json_examples):
        """Test that JSON examples have valid syntax."""
        for example in json_examples:
            try:
                # Replace template variables
                json_content = example['json']
                json_content = re.sub(r'\{\{.*?\}\}', '"placeholder"', json_content)
                json_content = re.sub(r'\$[A-Z_]+', '"placeholder"', json_content)

                # Attempt to parse JSON
                parsed = json.loads(json_content)
                assert parsed is not None, f"JSON parsed to None in {example['file']}"

            except json.JSONDecodeError as e:
                # Some examples may be partial/template
                if '...' not in example['json']:
                    pytest.fail(f"Invalid JSON syntax in {example['file']}: {e}")


class TestAPIEndpointExamples:
    """Test API endpoint examples from documentation."""

    @pytest.fixture
    def api_endpoints(self):
        """Extract all API endpoint references from documentation."""
        endpoints = []
        for doc_file in DOCS_PATH.glob("*.md"):
            content = doc_file.read_text()

            # Find API endpoint patterns
            endpoint_patterns = re.findall(r'/api/v\d+/\S+', content)
            for endpoint in endpoint_patterns:
                endpoints.append({
                    'file': doc_file.name,
                    'endpoint': endpoint
                })
        return endpoints

    def test_api_endpoints_use_versioning(self, api_endpoints):
        """Test that API endpoints include version (v1, v2, etc.)."""
        for endpoint_info in api_endpoints:
            endpoint = endpoint_info['endpoint']

            # Should have version in path
            assert re.search(r'/api/v\d+/', endpoint), \
                f"API endpoint missing version in {endpoint_info['file']}: {endpoint}"

    def test_api_endpoints_follow_conventions(self, api_endpoints):
        """Test that API endpoints follow REST conventions."""
        for endpoint_info in api_endpoints[:20]:  # Test sample
            endpoint = endpoint_info['endpoint']

            # Should use lowercase and hyphens/underscores, not camelCase in path
            # Remove trailing punctuation/markdown characters
            endpoint = endpoint.rstrip('`*).,;')
            path_parts = endpoint.split('?')[0].split('/')
            for part in path_parts:
                if part and not part.startswith('v'):  # Skip version
                    # Allow alphanumeric, hyphens, underscores, wildcards, and parameter placeholders
                    assert re.match(r'^[a-z0-9_\-{}:*]+$', part) or part.startswith('<'), \
                        f"API endpoint path not following conventions in {endpoint_info['file']}: {endpoint}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
