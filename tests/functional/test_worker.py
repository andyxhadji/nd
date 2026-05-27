"""Functional tests for worker agent."""

import pytest
from nd.worker.analyzer import TaskAnalyzer
from nd.schemas import AnalysisInput


@pytest.mark.functional
class TestWorkerAnalysis:
    def test_analyze_trivial_task(self):
        """Test analysis of trivial task."""
        analyzer = TaskAnalyzer()
        input_data = AnalysisInput(
            comment_body="Fix the typo: 'recieve' should be 'receive'",
            comment_category="request",
            mr_title="Fix typos",
            head_branch="fix-typos",
            repo_path="/tmp/repo",
        )
        result = analyzer.analyze_deterministic(input_data)
        assert result.complexity in [1, 2]
        assert result.confidence >= 70

    def test_analyze_moderate_task(self):
        """Test analysis of moderate task."""
        analyzer = TaskAnalyzer()
        input_data = AnalysisInput(
            comment_body="Can you add a validation function for the input?",
            comment_category="request",
            mr_title="Add validation",
            head_branch="add-validation",
            repo_path="/tmp/repo",
        )
        result = analyzer.analyze_deterministic(input_data)
        assert result.complexity in [2, 3, 4]

    def test_analyze_complex_task(self):
        """Test analysis of complex task."""
        analyzer = TaskAnalyzer()
        input_data = AnalysisInput(
            comment_body="We need to refactor this to use a different database architecture",
            comment_category="request",
            mr_title="Database migration",
            head_branch="db-migration",
            repo_path="/tmp/repo",
        )
        result = analyzer.analyze_deterministic(input_data)
        assert result.complexity >= 4
        assert result.confidence < 70  # Low confidence for complex tasks

    def test_extract_file_paths(self):
        """Test file path extraction from comment."""
        analyzer = TaskAnalyzer()
        comment = "Please update src/api/handler.py and tests/test_handler.py"
        files = analyzer._extract_likely_files(comment)
        assert "src/api/handler.py" in files
        assert "tests/test_handler.py" in files
