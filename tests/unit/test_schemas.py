# tests/unit/test_schemas.py
"""Unit tests for Pydantic schemas."""

import pytest

from nd.schemas import (
    AnalysisResult,
    ClassificationResult,
    CommentInput,
    IssuePollResult,
    IssueTaskInput,
    SourceMetadata,
)


class TestCommentInput:
    def test_valid_comment(self):
        comment = CommentInput(
            body="Can you fix this?",
            author="reviewer",
            mr_title="Add feature",
            mr_number=42,
        )
        assert comment.body == "Can you fix this?"
        assert comment.mr_number == 42


class TestClassificationResult:
    def test_actionable_request(self):
        result = ClassificationResult(
            actionable=True,
            reason="Explicit request with 'fix'",
            category="request",
            confident=True,
        )
        assert result.actionable is True
        assert result.category == "request"

    def test_category_validation(self):
        with pytest.raises(ValueError):
            ClassificationResult(
                actionable=True,
                reason="test",
                category="invalid_category",
                confident=True,
            )


class TestAnalysisResult:
    def test_complexity_range(self):
        result = AnalysisResult(
            complexity=3,
            confidence=85,
            reasoning="Moderate change",
            suggested_approach="Refactor function",
            files_likely_affected=["src/handler.py"],
            confident=True,
        )
        assert result.complexity == 3
        assert result.confidence == 85

    def test_confidence_bounds(self):
        # confidence should be 0-100
        result = AnalysisResult(
            complexity=1,
            confidence=100,
            reasoning="test",
            suggested_approach="test",
            files_likely_affected=[],
            confident=True,
        )
        assert result.confidence == 100


class TestIssueTaskInput:
    def test_valid_issue_input(self):
        issue_input = IssueTaskInput(
            issue_number=123,
            issue_title="Bug report",
            issue_body="Something is broken",
            issue_url="https://github.com/org/repo/issues/123",
            issue_author="reporter",
            assignees=["user1", "user2"],
            platform="github",
            platform_host="github.com",
            repo_owner="org",
            repo_name="repo",
        )
        assert issue_input.issue_number == 123
        assert issue_input.assignees == ["user1", "user2"]


class TestIssuePollResult:
    def test_poll_result(self):
        result = IssuePollResult(
            issues_found=5,
            tasks_created=3,
            skipped=2,
            errors=["Error 1"],
        )
        assert result.issues_found == 5
        assert result.tasks_created == 3
        assert result.skipped == 2
        assert len(result.errors) == 1


class TestSourceMetadata:
    def test_valid_mr_source(self):
        source = SourceMetadata(
            source_url="https://gitlab.com/flatiron/myproject/-/merge_requests/123",
            source_type="mr",
            source_identifier="gitlab:flatiron/myproject#123",
        )
        assert source.source_url == "https://gitlab.com/flatiron/myproject/-/merge_requests/123"
        assert source.source_type == "mr"
        assert source.source_identifier == "gitlab:flatiron/myproject#123"

    def test_valid_issue_source(self):
        source = SourceMetadata(
            source_url="https://github.com/owner/repo/issues/456",
            source_type="issue",
            source_identifier="github:owner/repo#456",
        )
        assert source.source_url == "https://github.com/owner/repo/issues/456"
        assert source.source_type == "issue"
        assert source.source_identifier == "github:owner/repo#456"

    def test_source_type_validation(self):
        with pytest.raises(ValueError):
            SourceMetadata(
                source_url="https://example.com",
                source_type="invalid_type",
                source_identifier="test",
            )
