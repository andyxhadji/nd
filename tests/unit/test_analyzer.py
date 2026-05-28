# tests/unit/test_analyzer.py
"""Unit tests for task analyzer."""

import pytest

from nd.schemas import AnalysisInput
from nd.worker.analyzer import TaskAnalyzer


class TestTaskAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return TaskAnalyzer()

    def test_estimate_complexity_trivial(self, analyzer):
        # Typo fix should be trivial
        comment = "There's a typo: 'recieve' should be 'receive'"
        complexity = analyzer._estimate_complexity(comment)
        assert complexity in [1, 2]

    def test_estimate_complexity_moderate(self, analyzer):
        # New function request should be moderate
        comment = "Can you add a function to validate the input?"
        complexity = analyzer._estimate_complexity(comment)
        assert complexity in [2, 3, 4]

    def test_estimate_complexity_major(self, analyzer):
        # Architectural change should be major
        comment = "We need to refactor this to use a different database"
        complexity = analyzer._estimate_complexity(comment)
        assert complexity in [4, 5]

    def test_extract_likely_files(self, analyzer):
        comment = "Please update the handler in src/api/handler.py"
        files = analyzer._extract_likely_files(comment)
        assert "src/api/handler.py" in files

    def test_build_analysis_input(self, analyzer):
        input_data = AnalysisInput(
            comment_body="Fix the bug",
            comment_category="request",
            mr_title="Bug fix",
            head_branch="fix-branch",
            repo_path="/tmp/repo",
        )
        assert input_data.comment_body == "Fix the bug"
