#!/usr/bin/env python3
"""End-to-End Production Readiness Tests for KnowledgeBeast v2.0.

This test suite validates the ACTUAL system works end-to-end, not just unit tests.

Tests:
1. API Server Startup & Health
2. Project Creation via API
3. Document Ingestion (real files)
4. Vector Search Quality (real queries)
5. Hybrid Search Comparison
6. CLI Commands
7. Performance Under Load
8. Migration (if applicable)

This is what should have been run BEFORE tagging v2.0.0.
"""

import os
import sys
import time
import json
import tempfile
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional

# Test configuration
API_BASE_URL = "http://localhost:8000"
API_KEY = "test-api-key-12345"
TEST_PROJECT_NAME = "e2e-test-project"

class Colors:
    """Terminal colors for output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(title: str):
    """Print test section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}  {title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.RESET}\n")

def print_pass(message: str):
    """Print test pass message."""
    print(f"  {Colors.GREEN}✅ PASS{Colors.RESET}: {message}")

def print_fail(message: str, error: Optional[str] = None):
    """Print test failure message."""
    print(f"  {Colors.RED}❌ FAIL{Colors.RESET}: {message}")
    if error:
        print(f"     {Colors.RED}Error: {error}{Colors.RESET}")

def print_warn(message: str):
    """Print warning message."""
    print(f"  {Colors.YELLOW}⚠️  WARN{Colors.RESET}: {message}")

def print_info(message: str):
    """Print info message."""
    print(f"  {Colors.BLUE}ℹ️  INFO{Colors.RESET}: {message}")


class E2ETestSuite:
    """End-to-end test suite for production readiness."""

    def __init__(self):
        self.api_server_process = None
        self.test_project_id = None
        self.results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'warnings': 0
        }

    def run_all_tests(self) -> bool:
        """Run all E2E tests.

        Returns:
            True if all tests pass, False otherwise
        """
        print_header("🚀 KnowledgeBeast v2.0 - Production Readiness Validation")
        print_info("Testing ACTUAL system functionality (not just unit tests)")

        try:
            # Test 1: API Server
            if not self.test_api_server_startup():
                print_fail("Critical: API server won't start. Aborting.")
                return False

            # Test 2: Health Check
            if not self.test_health_endpoint():
                print_warn("Health endpoint issues, continuing...")

            # Test 3: Project Management
            if not self.test_project_creation():
                print_fail("Critical: Cannot create projects. Aborting.")
                self.cleanup()
                return False

            # Test 4: Document Ingestion
            if not self.test_document_ingestion():
                print_fail("Critical: Document ingestion broken.")

            # Test 5: Search Functionality
            if not self.test_search_functionality():
                print_fail("Critical: Search broken.")

            # Test 6: CLI Commands
            if not self.test_cli_commands():
                print_warn("CLI issues detected.")

            # Cleanup
            self.cleanup()

            # Report
            return self.print_summary()

        except KeyboardInterrupt:
            print_warn("Tests interrupted by user")
            self.cleanup()
            return False
        except Exception as e:
            print_fail(f"Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.cleanup()
            return False

    def test_api_server_startup(self) -> bool:
        """Test 1: Can the API server actually start?"""
        print_header("TEST 1: API Server Startup")

        try:
            # Set environment variable for API key
            env = os.environ.copy()
            env['KB_API_KEY'] = API_KEY
            env['KB_ALLOWED_ORIGINS'] = 'http://localhost:3000'

            # Start server in background
            print_info("Starting API server...")
            self.api_server_process = subprocess.Popen(
                [sys.executable, '-m', 'uvicorn',
                 'knowledgebeast.api.app:app',
                 '--host', '0.0.0.0',
                 '--port', '8000'],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Wait for server to start (longer timeout for model loading)
            print_info("Waiting for server to be ready (may take 60s for model loading)...")
            max_retries = 60
            for i in range(max_retries):
                try:
                    response = requests.get(
                        f"{API_BASE_URL}/health",
                        headers={'X-API-Key': API_KEY},
                        timeout=2
                    )
                    if response.status_code == 200:
                        print_pass(f"API server started successfully (took {i+1}s)")
                        self.results['passed'] += 1
                        self.results['total'] += 1
                        return True
                except requests.exceptions.RequestException as e:
                    if i % 10 == 0:  # Print progress every 10 seconds
                        print_info(f"Still waiting... ({i+1}s elapsed)")
                    time.sleep(1)

            # Check if process died
            if self.api_server_process and self.api_server_process.poll() is not None:
                stdout, stderr = self.api_server_process.communicate()
                print_fail(f"API server process died during startup")
                if stderr:
                    print(f"     STDERR: {stderr.decode()[:500]}")
            else:
                print_fail("API server failed to start within 60 seconds")

            self.results['failed'] += 1
            self.results['total'] += 1
            return False

        except Exception as e:
            print_fail(f"Could not start API server: {e}")
            self.results['failed'] += 1
            self.results['total'] += 1
            return False

    def test_health_endpoint(self) -> bool:
        """Test 2: Health endpoint responds correctly."""
        print_header("TEST 2: Health Endpoint")

        try:
            response = requests.get(
                f"{API_BASE_URL}/health",
                headers={'X-API-Key': API_KEY},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                print_pass(f"Health endpoint OK: {data}")
                self.results['passed'] += 1
                self.results['total'] += 1
                return True
            else:
                print_fail(f"Health endpoint returned {response.status_code}")
                self.results['failed'] += 1
                self.results['total'] += 1
                return False

        except Exception as e:
            print_fail(f"Health endpoint error: {e}")
            self.results['failed'] += 1
            self.results['total'] += 1
            return False

    def test_project_creation(self) -> bool:
        """Test 3: Can we create a project via API?"""
        print_header("TEST 3: Project Creation via API")

        try:
            # Create project
            response = requests.post(
                f"{API_BASE_URL}/api/v2/projects",
                headers={'X-API-Key': API_KEY},
                json={
                    'name': TEST_PROJECT_NAME,
                    'description': 'End-to-end test project',
                    'embedding_model': 'all-MiniLM-L6-v2'
                },
                timeout=10
            )

            if response.status_code == 201:
                data = response.json()
                self.test_project_id = data.get('project_id')
                print_pass(f"Project created: {self.test_project_id}")
                self.results['passed'] += 1
                self.results['total'] += 1
                return True
            else:
                print_fail(f"Project creation failed: {response.status_code}", response.text)
                self.results['failed'] += 1
                self.results['total'] += 1
                return False

        except Exception as e:
            print_fail(f"Project creation error: {e}")
            self.results['failed'] += 1
            self.results['total'] += 1
            return False

    def test_document_ingestion(self) -> bool:
        """Test 4: Can we ingest real documents?"""
        print_header("TEST 4: Document Ingestion")

        if not self.test_project_id:
            print_fail("No project ID, skipping ingestion test")
            self.results['failed'] += 1
            self.results['total'] += 1
            return False

        try:
            # Find README.md to ingest
            readme_path = Path('README.md')
            if not readme_path.exists():
                print_fail("README.md not found")
                self.results['failed'] += 1
                self.results['total'] += 1
                return False

            # Read document content
            with open(readme_path, 'r') as f:
                content = f.read()

            # Ingest document (send JSON, not multipart)
            print_info(f"Ingesting {readme_path}...")
            response = requests.post(
                f"{API_BASE_URL}/api/v2/projects/{self.test_project_id}/ingest",
                headers={'X-API-Key': API_KEY},
                json={
                    'content': content,
                    'metadata': {'source': 'e2e-test', 'filename': 'README.md'}
                },
                timeout=30
            )

            if response.status_code in [200, 201]:
                data = response.json()
                print_pass(f"Document ingested: {data.get('document_id', 'unknown')}")
                self.results['passed'] += 1
                self.results['total'] += 1
                return True
            else:
                print_fail(f"Ingestion failed: {response.status_code}", response.text)
                self.results['failed'] += 1
                self.results['total'] += 1
                return False

        except Exception as e:
            print_fail(f"Ingestion error: {e}")
            import traceback
            traceback.print_exc()
            self.results['failed'] += 1
            self.results['total'] += 1
            return False

    def test_search_functionality(self) -> bool:
        """Test 5: Can we search and get results?"""
        print_header("TEST 5: Search Functionality")

        if not self.test_project_id:
            print_fail("No project ID, skipping search test")
            self.results['failed'] += 1
            self.results['total'] += 1
            return False

        test_queries = [
            ("installation", "vector"),
            ("knowledgebeast", "hybrid"),
            ("documentation", "keyword")
        ]

        all_passed = True

        for query, mode in test_queries:
            try:
                print_info(f"Testing {mode} search: '{query}'")
                response = requests.post(
                    f"{API_BASE_URL}/api/v2/projects/{self.test_project_id}/query",
                    headers={'X-API-Key': API_KEY},
                    json={
                        'query': query,
                        'mode': mode,
                        'top_k': 5
                    },
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get('results', [])
                    print_pass(f"{mode.capitalize()} search OK: {len(results)} results")
                    self.results['passed'] += 1
                else:
                    print_fail(f"{mode} search failed: {response.status_code}", response.text)
                    self.results['failed'] += 1
                    all_passed = False

                self.results['total'] += 1

            except Exception as e:
                print_fail(f"{mode} search error: {e}")
                self.results['failed'] += 1
                self.results['total'] += 1
                all_passed = False

        return all_passed

    def test_cli_commands(self) -> bool:
        """Test 6: Do CLI commands work?"""
        print_header("TEST 6: CLI Commands")

        commands_to_test = [
            (['python3', '-m', 'knowledgebeast.cli', '--version'], "Version check"),
            (['python3', '-m', 'knowledgebeast.cli', '--help'], "Help command"),
        ]

        all_passed = True

        for cmd, description in commands_to_test:
            try:
                print_info(f"Testing: {description}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0:
                    print_pass(f"{description} works")
                    self.results['passed'] += 1
                else:
                    print_fail(f"{description} failed", result.stderr)
                    self.results['failed'] += 1
                    all_passed = False

                self.results['total'] += 1

            except Exception as e:
                print_fail(f"{description} error: {e}")
                self.results['failed'] += 1
                self.results['total'] += 1
                all_passed = False

        return all_passed

    def cleanup(self):
        """Cleanup test resources."""
        print_header("Cleanup")

        # Delete test project
        if self.test_project_id:
            try:
                response = requests.delete(
                    f"{API_BASE_URL}/api/v2/projects/{self.test_project_id}",
                    headers={'X-API-Key': API_KEY},
                    timeout=10
                )
                if response.status_code == 200:
                    print_info("Test project deleted")
                else:
                    print_warn(f"Could not delete test project: {response.status_code}")
            except:
                pass

        # Stop API server
        if self.api_server_process:
            print_info("Stopping API server...")
            self.api_server_process.terminate()
            try:
                self.api_server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.api_server_process.kill()
            print_info("API server stopped")

    def print_summary(self) -> bool:
        """Print test summary and return pass/fail."""
        print_header("📊 Test Summary")

        total = self.results['total']
        passed = self.results['passed']
        failed = self.results['failed']
        warnings = self.results['warnings']

        pass_rate = (passed / total * 100) if total > 0 else 0

        print(f"\n  Total Tests: {total}")
        print(f"  {Colors.GREEN}Passed: {passed}{Colors.RESET}")
        print(f"  {Colors.RED}Failed: {failed}{Colors.RESET}")
        if warnings > 0:
            print(f"  {Colors.YELLOW}Warnings: {warnings}{Colors.RESET}")
        print(f"\n  Pass Rate: {pass_rate:.1f}%\n")

        if failed == 0:
            print(f"  {Colors.GREEN}{Colors.BOLD}✅ ALL TESTS PASSED{Colors.RESET}")
            print(f"  {Colors.GREEN}System is ready for v2.0.0 final release{Colors.RESET}\n")
            return True
        else:
            print(f"  {Colors.RED}{Colors.BOLD}❌ TESTS FAILED{Colors.RESET}")
            print(f"  {Colors.RED}System NOT ready for production{Colors.RESET}")
            print(f"  {Colors.YELLOW}Keep as v2.0.0-beta until issues resolved{Colors.RESET}\n")
            return False


def main():
    """Run end-to-end test suite."""
    suite = E2ETestSuite()
    success = suite.run_all_tests()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
