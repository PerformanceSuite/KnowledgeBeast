"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner
from knowledgebeast.cli.commands import cli


def test_version_command():
    """Test version command."""
    runner = CliRunner()
    result = runner.invoke(cli, ['version'])
    assert result.exit_code == 0
    assert 'KnowledgeBeast' in result.output
    assert '0.1.0' in result.output


def test_help_command():
    """Test help command."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'knowledgebeast' in result.output.lower()


def test_init_command():
    """Test init command."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['init', './test-kb'])
        assert result.exit_code == 0
        assert 'initialized successfully' in result.output.lower()


def test_health_command_no_kb():
    """Test health command without knowledge base."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['health'])
        # Should fail gracefully with no KB
        assert 'Config' in result.output or 'health' in result.output.lower()
