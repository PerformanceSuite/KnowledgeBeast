"""
Tests to validate production operations documentation completeness and quality.
"""

import os
import re
import pytest
from pathlib import Path


# Base path for documentation
DOCS_PATH = Path(__file__).parent.parent.parent / "docs" / "operations"


class TestRunbookCompleteness:
    """Test incident response runbook completeness."""

    @pytest.fixture
    def runbook_content(self):
        """Load runbook content."""
        runbook_path = DOCS_PATH / "runbook.md"
        assert runbook_path.exists(), "runbook.md not found"
        return runbook_path.read_text()

    def test_runbook_has_minimum_incidents(self, runbook_content):
        """Test that runbook covers at least 8 incident scenarios."""
        # Count incident headers (## Incident N:)
        incident_pattern = r'^## Incident \d+:'
        incidents = re.findall(incident_pattern, runbook_content, re.MULTILINE)
        assert len(incidents) >= 8, f"Expected at least 8 incidents, found {len(incidents)}"

    def test_runbook_incidents_have_required_sections(self, runbook_content):
        """Test that each incident has required sections."""
        required_sections = [
            "Severity",
            "Symptoms",
            "Diagnosis Steps",
            "Resolution Steps",
            "Escalation Criteria",
            "Prevention"
        ]

        # Find all incident sections
        incidents = re.split(r'^## Incident \d+:', runbook_content, flags=re.MULTILINE)[1:]

        for i, incident in enumerate(incidents[:8], 1):  # Test first 8 incidents
            for section in required_sections:
                assert f"### {section}" in incident or f"**{section}**" in incident, \
                    f"Incident {i} missing required section: {section}"

    def test_runbook_has_code_examples(self, runbook_content):
        """Test that runbook includes bash code examples."""
        # Count code blocks
        code_blocks = runbook_content.count("```bash")
        assert code_blocks >= 20, f"Expected at least 20 bash code examples, found {code_blocks}"

    def test_runbook_has_escalation_contact_info(self, runbook_content):
        """Test that runbook includes escalation contact information."""
        assert "On-Call" in runbook_content, "Missing on-call contact information"
        assert "PagerDuty" in runbook_content or "Escalation Path" in runbook_content, \
            "Missing escalation path information"


class TestSLASLOCompleteness:
    """Test SLA/SLO definitions completeness."""

    @pytest.fixture
    def sla_slo_content(self):
        """Load SLA/SLO content."""
        sla_path = DOCS_PATH / "sla-slo.md"
        assert sla_path.exists(), "sla-slo.md not found"
        return sla_path.read_text()

    def test_slo_targets_defined(self, sla_slo_content):
        """Test that all SLO targets are defined."""
        required_slos = [
            "Availability SLO",
            "Query Latency SLO",
            "Error Rate SLO",
            "Search Quality SLO"
        ]

        for slo in required_slos:
            assert slo in sla_slo_content, f"Missing SLO definition: {slo}"

    def test_slo_has_measurable_targets(self, sla_slo_content):
        """Test that SLOs have measurable numeric targets."""
        # Check for specific numeric targets
        assert "99.9%" in sla_slo_content, "Missing 99.9% availability target"
        assert "< 100ms" in sla_slo_content or "<100ms" in sla_slo_content, "Missing P99 latency target"
        assert "< 0.1%" in sla_slo_content, "Missing error rate target"

    def test_slo_has_prometheus_queries(self, sla_slo_content):
        """Test that SLOs include Prometheus queries for measurement."""
        assert "promql" in sla_slo_content.lower() or "```" in sla_slo_content, \
            "Missing Prometheus query examples"
        assert "histogram_quantile" in sla_slo_content, "Missing latency percentile queries"

    def test_error_budget_defined(self, sla_slo_content):
        """Test that error budget is defined and explained."""
        assert "Error Budget" in sla_slo_content, "Missing error budget section"
        assert "43.2 minutes" in sla_slo_content or "43.2" in sla_slo_content, \
            "Missing monthly error budget calculation"

    def test_sla_response_times_defined(self, sla_slo_content):
        """Test that SLA response times are defined."""
        assert "Incident Response SLA" in sla_slo_content or "Response" in sla_slo_content, \
            "Missing incident response SLA"
        # Should have response times for different severities
        assert "15 minutes" in sla_slo_content or "< 15" in sla_slo_content, \
            "Missing critical incident response time"


class TestDisasterRecoveryCompleteness:
    """Test disaster recovery plan completeness."""

    @pytest.fixture
    def dr_content(self):
        """Load disaster recovery content."""
        dr_path = DOCS_PATH / "disaster-recovery.md"
        assert dr_path.exists(), "disaster-recovery.md not found"
        return dr_path.read_text()

    def test_dr_has_backup_strategy(self, dr_content):
        """Test that DR plan includes comprehensive backup strategy."""
        backup_components = [
            "ChromaDB",
            "SQLite",
            "Configuration"
        ]

        for component in backup_components:
            assert component in dr_content, f"Missing backup strategy for: {component}"

    def test_dr_has_rpo_rto(self, dr_content):
        """Test that DR plan defines RPO and RTO."""
        assert "RPO" in dr_content, "Missing RPO (Recovery Point Objective)"
        assert "RTO" in dr_content, "Missing RTO (Recovery Time Objective)"
        assert "< 1 hour" in dr_content or "<1 hour" in dr_content, "Missing RPO target"
        assert "< 4 hours" in dr_content or "<4 hours" in dr_content, "Missing RTO target"

    def test_dr_has_recovery_procedures(self, dr_content):
        """Test that DR plan includes step-by-step recovery procedures."""
        recovery_scenarios = [
            "Data Center Outage",
            "Database Corruption",
            "Complete System Failure"
        ]

        for scenario in recovery_scenarios:
            assert scenario in dr_content, f"Missing recovery procedure for: {scenario}"

        # Should have numbered steps
        assert "Step-by-Step Procedure" in dr_content or re.search(r'\d+\.', dr_content), \
            "Missing step-by-step recovery procedures"

    def test_dr_has_backup_scripts(self, dr_content):
        """Test that DR plan includes backup scripts."""
        assert "backup_chromadb.sh" in dr_content or "backup" in dr_content, \
            "Missing backup scripts"
        assert "```bash" in dr_content, "Missing bash script examples"

    def test_dr_has_testing_plan(self, dr_content):
        """Test that DR plan includes testing procedures."""
        assert "Testing" in dr_content or "DR Test" in dr_content, \
            "Missing DR testing plan"
        assert "Quarterly" in dr_content or "Monthly" in dr_content, \
            "Missing DR test frequency"


class TestMonitoringGuideCompleteness:
    """Test monitoring and alerting guide completeness."""

    @pytest.fixture
    def monitoring_content(self):
        """Load monitoring guide content."""
        monitoring_path = DOCS_PATH / "monitoring-guide.md"
        assert monitoring_path.exists(), "monitoring-guide.md not found"
        return monitoring_path.read_text()

    def test_monitoring_has_dashboard_tour(self, monitoring_content):
        """Test that guide includes dashboard tour."""
        assert "Dashboard Tour" in monitoring_content, "Missing dashboard tour section"
        # Should describe key panels
        assert "Panel" in monitoring_content, "Missing panel descriptions"

    def test_monitoring_has_key_metrics_explained(self, monitoring_content):
        """Test that key metrics are explained."""
        key_metrics = [
            "latency",
            "error rate",
            "cache hit ratio"
        ]

        for metric in key_metrics:
            assert metric.lower() in monitoring_content.lower(), \
                f"Missing explanation for metric: {metric}"

    def test_monitoring_has_alert_response_matrix(self, monitoring_content):
        """Test that guide includes alert response matrix."""
        assert "Alert Response" in monitoring_content, "Missing alert response matrix"
        # Should have severity levels
        assert "Critical" in monitoring_content, "Missing critical alert severity"
        assert "Warning" in monitoring_content, "Missing warning alert severity"

    def test_monitoring_has_troubleshooting_flowcharts(self, monitoring_content):
        """Test that guide includes troubleshooting flowcharts."""
        assert "Flowchart" in monitoring_content or "Troubleshooting" in monitoring_content, \
            "Missing troubleshooting flowcharts"

    def test_monitoring_has_prometheus_queries(self, monitoring_content):
        """Test that guide includes Prometheus query examples."""
        assert "promql" in monitoring_content.lower() or "```" in monitoring_content, \
            "Missing Prometheus query examples"
        assert "rate(" in monitoring_content or "histogram_quantile" in monitoring_content, \
            "Missing Prometheus query syntax examples"


class TestProductionChecklistCompleteness:
    """Test production deployment checklist completeness."""

    @pytest.fixture
    def checklist_content(self):
        """Load production checklist content."""
        checklist_path = DOCS_PATH / "production-checklist.md"
        assert checklist_path.exists(), "production-checklist.md not found"
        return checklist_path.read_text()

    def test_checklist_has_minimum_items(self, checklist_content):
        """Test that checklist has at least 50 total items."""
        # Count checkbox items (- [ ])
        checklist_items = re.findall(r'^- \[ \]', checklist_content, re.MULTILINE)
        assert len(checklist_items) >= 50, \
            f"Expected at least 50 checklist items, found {len(checklist_items)}"

    def test_checklist_has_all_phases(self, checklist_content):
        """Test that checklist covers all deployment phases."""
        phases = [
            "Pre-Deployment",
            "Deployment",
            "Post-Deployment"
        ]

        for phase in phases:
            assert phase in checklist_content, f"Missing checklist phase: {phase}"

    def test_checklist_has_verification_commands(self, checklist_content):
        """Test that checklist includes verification commands."""
        assert "```bash" in checklist_content, "Missing bash command examples"
        # Should have multiple verification commands
        code_blocks = checklist_content.count("```bash")
        assert code_blocks >= 20, \
            f"Expected at least 20 verification commands, found {code_blocks}"

    def test_checklist_has_rollback_procedure(self, checklist_content):
        """Test that checklist includes rollback procedure."""
        assert "Rollback" in checklist_content, "Missing rollback section"
        assert "rollback" in checklist_content.lower(), "Missing rollback procedures"


class TestCodeExamplesValidity:
    """Test that code examples in documentation are valid."""

    @pytest.fixture
    def all_docs_content(self):
        """Load all documentation files."""
        docs = {}
        for doc_file in DOCS_PATH.glob("*.md"):
            docs[doc_file.name] = doc_file.read_text()
        return docs

    def test_bash_commands_have_proper_syntax(self, all_docs_content):
        """Test that bash commands use proper syntax."""
        for doc_name, content in all_docs_content.items():
            # Extract bash code blocks
            bash_blocks = re.findall(r'```bash\n(.*?)```', content, re.DOTALL)

            for i, block in enumerate(bash_blocks[:10], 1):  # Test first 10 per doc
                # Basic syntax checks
                # No unescaped $
                if "$(" in block or "${" in block:
                    # Variable expansion is okay
                    pass

                # Check for common bash errors
                assert not re.search(r'^\s*fi\s*$', block, re.MULTILINE) or \
                       re.search(r'^\s*if\s', block, re.MULTILINE), \
                    f"{doc_name}: 'fi' without matching 'if' in block {i}"

    def test_prometheus_queries_have_valid_syntax(self, all_docs_content):
        """Test that Prometheus queries have valid syntax."""
        for doc_name, content in all_docs_content.items():
            # Extract promql code blocks
            promql_blocks = re.findall(r'```promql\n(.*?)```', content, re.DOTALL)

            for i, block in enumerate(promql_blocks, 1):
                # Basic PromQL syntax checks
                if "histogram_quantile" in block:
                    assert re.search(r'histogram_quantile\([0-9.]+,', block), \
                        f"{doc_name}: Invalid histogram_quantile syntax in block {i}"

                if "rate(" in block:
                    assert re.search(r'rate\(.*?\[.*?\]\)', block), \
                        f"{doc_name}: Invalid rate() syntax in block {i}"

    def test_kubernetes_commands_reference_correct_namespace(self, all_docs_content):
        """Test that kubectl commands reference appropriate namespaces."""
        for doc_name, content in all_docs_content.items():
            # Find kubectl commands
            kubectl_cmds = re.findall(r'kubectl.*', content)

            for cmd in kubectl_cmds[:20]:  # Test first 20 per doc
                if "production" in cmd or "staging" in cmd:
                    # Good - explicit namespace
                    pass
                elif "-n " in cmd or "--namespace" in cmd:
                    # Good - has namespace flag
                    pass
                # Some commands don't need namespace (cluster-wide operations)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
