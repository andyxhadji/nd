"""
Validation tests for the E2E framework itself.

These tests verify the framework structure without requiring docker-compose.
They test fixtures, helpers, and mock service logic.
"""

import json
from pathlib import Path

import pytest


def test_fixture_files_exist():
    """Verify all fixture files exist and are valid JSON."""
    fixtures_dir = Path(__file__).parent / "fixtures"

    # Check comments.json
    comments_file = fixtures_dir / "comments.json"
    assert comments_file.exists(), "comments.json missing"

    with open(comments_file) as f:
        comments = json.load(f)
        assert isinstance(comments, list), "comments.json should be a list"
        assert len(comments) > 0, "comments.json should not be empty"
        assert "body" in comments[0], "Comment missing 'body' field"

    # Check issues.json
    issues_file = fixtures_dir / "issues.json"
    assert issues_file.exists(), "issues.json missing"

    with open(issues_file) as f:
        issues = json.load(f)
        assert isinstance(issues, list), "issues.json should be a list"
        assert len(issues) > 0, "issues.json should not be empty"
        assert "title" in issues[0], "Issue missing 'title' field"


def test_scenario_files_exist():
    """Verify all scenario files exist and have required structure."""
    scenarios_dir = Path(__file__).parent / "fixtures" / "scenarios"

    scenario_files = list(scenarios_dir.glob("*.json"))
    assert len(scenario_files) >= 3, "Should have at least 3 scenario files"

    for scenario_file in scenario_files:
        with open(scenario_file) as f:
            scenario = json.load(f)

            # Check required fields
            assert "name" in scenario, f"{scenario_file.name} missing 'name'"
            assert "initial_state" in scenario, f"{scenario_file.name} missing 'initial_state'"
            assert "expected_flow" in scenario, f"{scenario_file.name} missing 'expected_flow'"


def test_mock_middleman_structure():
    """Verify mock middleman has correct structure."""
    mock_dir = Path(__file__).parent / "mocks" / "mock_middleman"

    assert mock_dir.exists(), "mock_middleman directory missing"
    assert (mock_dir / "app.py").exists(), "mock_middleman/app.py missing"
    assert (mock_dir / "Dockerfile").exists(), "mock_middleman/Dockerfile missing"


def test_mock_github_structure():
    """Verify mock github has correct structure."""
    mock_dir = Path(__file__).parent / "mocks" / "mock_github"

    assert mock_dir.exists(), "mock_github directory missing"
    assert (mock_dir / "app.py").exists(), "mock_github/app.py missing"
    assert (mock_dir / "Dockerfile").exists(), "mock_github/Dockerfile missing"


def test_mock_gitlab_structure():
    """Verify mock gitlab has correct structure."""
    mock_dir = Path(__file__).parent / "mocks" / "mock_gitlab"

    assert mock_dir.exists(), "mock_gitlab directory missing"
    assert (mock_dir / "app.py").exists(), "mock_gitlab/app.py missing"
    assert (mock_dir / "Dockerfile").exists(), "mock_gitlab/Dockerfile missing"


def test_docker_compose_exists():
    """Verify docker-compose.e2e.yml exists."""
    compose_file = Path(__file__).parent / "docker-compose.e2e.yml"
    assert compose_file.exists(), "docker-compose.e2e.yml missing"

    # Basic validation - file is not empty
    assert compose_file.stat().st_size > 0, "docker-compose.e2e.yml is empty"


def test_helper_scripts_exist():
    """Verify helper scripts exist and are executable."""
    scripts_dir = Path(__file__).parent / "scripts"

    assert scripts_dir.exists(), "scripts directory missing"

    scripts = [
        "run-e2e-tests.sh",
        "test-running-agent.sh",
        "wait-for-services.sh",
    ]

    for script in scripts:
        script_path = scripts_dir / script
        assert script_path.exists(), f"{script} missing"
        # Check file is not empty
        assert script_path.stat().st_size > 0, f"{script} is empty"


def test_documentation_exists():
    """Verify documentation files exist."""
    e2e_dir = Path(__file__).parent

    docs = [
        "README.md",
        "QUICKSTART.md",
        "ARCHITECTURE.md",
    ]

    for doc in docs:
        doc_path = e2e_dir / doc
        assert doc_path.exists(), f"{doc} missing"
        assert doc_path.stat().st_size > 100, f"{doc} is too small"


def test_conftest_structure():
    """Verify conftest.py has required fixtures."""
    import importlib.util

    conftest_path = Path(__file__).parent / "conftest.py"
    assert conftest_path.exists(), "conftest.py missing"

    # Load conftest module
    spec = importlib.util.spec_from_file_location("conftest", conftest_path)
    conftest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conftest)

    # Check key fixtures exist
    required_fixtures = [
        "e2e_env",
        "mock_middleman",
        "mock_github",
        "mock_gitlab",
        "kata_client",
        "scenario_loader",
        "fixture_loader",
    ]

    for fixture_name in required_fixtures:
        assert hasattr(conftest, fixture_name), f"Fixture '{fixture_name}' not found in conftest.py"


def test_pytest_ini_exists():
    """Verify pytest.ini configuration exists."""
    pytest_ini = Path(__file__).parent / "pytest.ini"
    assert pytest_ini.exists(), "pytest.ini missing"

    content = pytest_ini.read_text()
    assert "[pytest]" in content, "pytest.ini should have [pytest] section"
    assert "markers" in content, "pytest.ini should define markers"


def test_all_test_files_importable():
    """Verify all test files can be imported (syntax check)."""
    import importlib.util
    import sys

    test_files = [
        "test_full_e2e.py",
        "test_triage_e2e.py",
        "test_worker_e2e.py",
        "test_reasoners_e2e.py",
        "example_test.py",
    ]

    for test_file in test_files:
        test_path = Path(__file__).parent / test_file
        assert test_path.exists(), f"{test_file} missing"

        # Try to import (syntax check)
        spec = importlib.util.spec_from_file_location(test_file[:-3], test_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[test_file[:-3]] = module

        try:
            spec.loader.exec_module(module)
            print(f"✓ {test_file} imports successfully")
        except Exception as e:
            pytest.fail(f"Failed to import {test_file}: {e}")


def test_fixture_loader_function(fixture_loader):
    """Test that fixture_loader fixture works."""
    # This test requires conftest fixtures but doesn't need docker-compose
    comments = fixture_loader("comments.json")

    assert isinstance(comments, list)
    assert len(comments) > 0
    assert "body" in comments[0]


def test_scenario_loader_function(scenario_loader):
    """Test that scenario_loader fixture works."""
    scenario = scenario_loader("simple_request.json")

    assert isinstance(scenario, dict)
    assert "name" in scenario
    assert scenario["name"] == "Simple request flow"
    assert "initial_state" in scenario
    assert "expected_flow" in scenario
