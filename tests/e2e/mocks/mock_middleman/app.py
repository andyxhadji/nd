"""Mock Middleman API for E2E testing."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI, Query
from pydantic import BaseModel

app = FastAPI(title="Mock Middleman", version="1.0.0")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# In-memory storage
_comments: list[dict[str, Any]] = []
_issues: list[dict[str, Any]] = []


class Comment(BaseModel):
    """MR comment structure."""

    body: str
    author: str
    mr_title: str
    mr_number: int
    mr_url: str
    head_branch: str
    base_branch: str
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str
    dedupe_key: str
    created_at: str | None = None


class Issue(BaseModel):
    """Issue structure."""

    number: int
    title: str
    body: str
    url: str
    author: str
    assignees: list[str]
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str
    created_at: str | None = None


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/comments")
async def get_comments(
    since: str | None = Query(None),
    current_user: str | None = Query(None),
):
    """Get comments since a timestamp, optionally filtered by current_user."""
    logger.info(f"GET /comments since={since} current_user={current_user}")

    # Parse since timestamp
    since_dt: datetime | None = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            since_dt = None

    # Filter comments
    results = []
    for comment in _comments:
        # Filter by timestamp
        if since_dt:
            try:
                comment_dt = datetime.fromisoformat(
                    comment.get("created_at", "").replace("Z", "+00:00")
                )
                if comment_dt <= since_dt:
                    continue
            except ValueError:
                # Skip comments with invalid timestamps
                logger.warning(f"Invalid timestamp in comment: {comment.get('created_at')}")
                continue

        # Filter by current_user (skip if author matches current_user)
        if current_user and comment.get("author") == current_user:
            continue

        results.append(comment)

    logger.info(f"Returning {len(results)} comments")
    return results


@app.get("/issues/assigned/{username}")
async def get_issues_assigned_to(username: str):
    """Get issues assigned to a specific user."""
    logger.info(f"GET /issues/assigned/{username}")

    results = [issue for issue in _issues if username in issue.get("assignees", [])]

    logger.info(f"Returning {len(results)} issues for {username}")
    return results


@app.post("/seed/comments")
async def seed_comments(comments: list[Comment]):
    """Seed the mock with comments."""
    logger.info(f"POST /seed/comments - adding {len(comments)} comments")

    global _comments
    for comment in comments:
        comment_dict = comment.model_dump()
        # Add created_at if not provided
        if not comment_dict.get("created_at"):
            comment_dict["created_at"] = datetime.now(UTC).isoformat()
        _comments.append(comment_dict)

    return {"status": "ok", "total_comments": len(_comments)}


@app.post("/seed/issues")
async def seed_issues(issues: list[Issue]):
    """Seed the mock with issues."""
    logger.info(f"POST /seed/issues - adding {len(issues)} issues")

    global _issues
    for issue in issues:
        issue_dict = issue.model_dump()
        # Add created_at if not provided
        if not issue_dict.get("created_at"):
            issue_dict["created_at"] = datetime.now(UTC).isoformat()
        _issues.append(issue_dict)

    return {"status": "ok", "total_issues": len(_issues)}


@app.post("/reset")
async def reset():
    """Clear all mock data."""
    logger.info("POST /reset")

    global _comments, _issues
    _comments = []
    _issues = []

    return {"status": "ok"}


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "mock-middleman",
        "version": "1.0.0",
        "comments": len(_comments),
        "issues": len(_issues),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8091)
