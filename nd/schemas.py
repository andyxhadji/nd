"""Pydantic schemas for nd agents."""

from typing import Literal

from pydantic import BaseModel, Field

# ============================================================================
# Triage Agent Schemas
# ============================================================================


class CommentInput(BaseModel):
    """Input for comment classification."""

    body: str
    author: str
    mr_title: str
    mr_number: int


class ClassificationResult(BaseModel):
    """Result of comment classification."""

    actionable: bool
    reason: str
    category: Literal["question", "request", "feedback", "acknowledgment", "bot", "other"]
    confident: bool


class TaskInput(BaseModel):
    """Input for creating a kata task."""

    comment_body: str
    comment_author: str
    comment_dedupe_key: str
    mr_number: int
    mr_title: str
    mr_url: str
    head_branch: str
    base_branch: str
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str
    classification: ClassificationResult


class TaskCreationResult(BaseModel):
    """Result of task creation."""

    created: bool
    task_id: str | None = None
    skipped_reason: str | None = None


class PollResult(BaseModel):
    """Result of polling for comments."""

    comments_found: int
    tasks_created: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


class IssueTaskInput(BaseModel):
    """Input for creating a kata task from an issue."""

    issue_number: int
    issue_title: str
    issue_body: str
    issue_url: str
    issue_author: str
    assignees: list[str]
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str


class IssuePollResult(BaseModel):
    """Result of polling for issues."""

    issues_found: int
    tasks_created: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


# ============================================================================
# Worker Agent Schemas
# ============================================================================


class ClaimResult(BaseModel):
    """Result of claiming a task."""

    claimed: bool
    task_id: str | None = None
    project: str | None = None


class WorkspaceInput(BaseModel):
    """Input for workspace preparation."""

    task_id: str
    project: str
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str
    head_branch: str | None = None
    base_branch: str | None = None
    is_issue: bool = False
    issue_short_id: str | None = None


class WorkspaceResult(BaseModel):
    """Result of workspace preparation."""

    prepared: bool
    repo_path: str | None = None
    branch: str | None = None
    base_branch: str | None = None
    bare_path: str | None = None
    branch_hash: str | None = None  # 6-char random hash for uniqueness
    error: str | None = None


class TaskDetails(BaseModel):
    """Details of a claimed task."""

    task_id: str
    project: str
    title: str
    body: str
    labels: list[str] = Field(default_factory=list)


class AnalysisInput(BaseModel):
    """Input for task analysis."""

    comment_body: str
    comment_category: str
    mr_title: str
    head_branch: str
    repo_path: str


class AnalysisResult(BaseModel):
    """Result of task complexity analysis."""

    complexity: Literal[1, 2, 3, 4, 5]
    confidence: int = Field(ge=0, le=100)
    reasoning: str
    suggested_approach: str
    files_likely_affected: list[str] = Field(default_factory=list)
    confident: bool


class SpecDocument(BaseModel):
    """Spec document for complex tasks."""

    summary: str
    problem_statement: str
    proposed_solution: str
    files_to_modify: list[str] = Field(default_factory=list)
    files_to_create: list[str] = Field(default_factory=list)
    testing_approach: str
    risks: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    confident: bool


class ExecutionInput(BaseModel):
    """Input for code execution."""

    task_id: str
    spec: SpecDocument | None = None
    comment_body: str
    repo_path: str
    head_branch: str


class ExecutionResult(BaseModel):
    """Result of code execution."""

    success: bool
    files_changed: list[str] = Field(default_factory=list)
    commit_sha: str | None = None
    diff: str | None = None
    error: str | None = None


class RoborevInput(BaseModel):
    """Input for roborev validation."""

    repo_path: str
    commit_sha: str
    max_iterations: int = 3


class RoborevResult(BaseModel):
    """Result of roborev validation."""

    passed: bool
    iterations: int
    final_findings: list[str] = Field(default_factory=list)
    error: str | None = None


class DraftInput(BaseModel):
    """Input for response drafting."""

    comment_body: str
    changes_made: list[str]
    commit_sha: str


class DraftResult(BaseModel):
    """Result of response drafting."""

    response_text: str
    confident: bool


class PublishResult(BaseModel):
    """Result of publishing committed changes back to the code host."""

    pushed: bool
    merge_request_url: str | None = None
    error: str | None = None


class ApprovalRequest(BaseModel):
    """Request for human approval of response."""

    task_id: str
    mr_url: str
    original_comment: str
    response_draft: str
    commit_sha: str
    commit_diff: str
    changes_summary: list[str] = Field(default_factory=list)


class PostInput(BaseModel):
    """Input for posting response to MR."""

    response_text: str
    dedupe_key: str
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str
    mr_number: int


class FinalizeInput(BaseModel):
    """Input for finalizing a task."""

    task_id: str
    status: Literal["completed", "failed", "needs-human"]
    response_posted: bool
    commit_sha: str | None = None


class ProcessResult(BaseModel):
    """Result of processing a task."""

    status: Literal["completed", "paused_for_spec", "paused_for_review", "failed"]
    changes_made: list[str] = Field(default_factory=list)
    response_draft: str | None = None
    commit_sha: str | None = None
    diff: str | None = None
    roborev_passed: bool | None = None
    roborev_findings: list[str] = Field(default_factory=list)
    error: str | None = None
