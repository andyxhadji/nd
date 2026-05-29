"""Mock GitHub API for E2E testing."""

import logging
from typing import Any

from fastapi import FastAPI, Header, Path
from pydantic import BaseModel

app = FastAPI(title="Mock GitHub", version="1.0.0")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# In-memory storage for posted comments
_posted_comments: list[dict[str, Any]] = []
_pull_requests: dict[str, dict[str, Any]] = {}


class CommentBody(BaseModel):
    """GitHub comment body."""

    body: str


class PullRequest(BaseModel):
    """Pull request structure."""

    number: int
    title: str
    state: str = "open"
    head: dict[str, str]
    base: dict[str, str]


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/repos/{owner}/{repo}/issues/{number}/comments")
async def create_issue_comment(
    owner: str = Path(...),
    repo: str = Path(...),
    number: int = Path(...),
    comment: CommentBody = None,
    authorization: str | None = Header(None),
):
    """Mock endpoint for posting issue comments."""
    logger.info(f"POST /repos/{owner}/{repo}/issues/{number}/comments")
    logger.info(f"Body: {comment.body if comment else 'None'}")

    # Store the comment
    _posted_comments.append(
        {
            "type": "issue",
            "owner": owner,
            "repo": repo,
            "number": number,
            "body": comment.body if comment else "",
            "authorization": authorization,
        }
    )

    return {
        "id": len(_posted_comments),
        "body": comment.body if comment else "",
        "user": {"login": "nd-worker"},
    }


@app.post("/repos/{owner}/{repo}/pulls/{number}/comments")
async def create_pr_comment(
    owner: str = Path(...),
    repo: str = Path(...),
    number: int = Path(...),
    comment: CommentBody = None,
    authorization: str | None = Header(None),
):
    """Mock endpoint for posting PR comments."""
    logger.info(f"POST /repos/{owner}/{repo}/pulls/{number}/comments")
    logger.info(f"Body: {comment.body if comment else 'None'}")

    # Store the comment
    _posted_comments.append(
        {
            "type": "pull_request",
            "owner": owner,
            "repo": repo,
            "number": number,
            "body": comment.body if comment else "",
            "authorization": authorization,
        }
    )

    return {
        "id": len(_posted_comments),
        "body": comment.body if comment else "",
        "user": {"login": "nd-worker"},
    }


@app.get("/repos/{owner}/{repo}/pulls/{number}")
async def get_pull_request(
    owner: str = Path(...),
    repo: str = Path(...),
    number: int = Path(...),
):
    """Mock endpoint for getting PR details."""
    logger.info(f"GET /repos/{owner}/{repo}/pulls/{number}")

    key = f"{owner}/{repo}/{number}"
    if key in _pull_requests:
        return _pull_requests[key]

    # Return default PR if not found
    return {
        "number": number,
        "title": f"Mock PR #{number}",
        "state": "open",
        "head": {"ref": "feature-branch", "sha": "abc123"},
        "base": {"ref": "main", "sha": "def456"},
    }


@app.post("/repos/{owner}/{repo}/pulls")
async def create_pull_request(
    owner: str = Path(...),
    repo: str = Path(...),
    pr: PullRequest = None,
    authorization: str | None = Header(None),
):
    """Mock endpoint for creating a pull request."""
    logger.info(f"POST /repos/{owner}/{repo}/pulls")

    if pr:
        key = f"{owner}/{repo}/{pr.number}"
        _pull_requests[key] = pr.model_dump()

        return {
            "number": pr.number,
            "html_url": f"https://github.com/{owner}/{repo}/pull/{pr.number}",
            "title": pr.title,
            "state": pr.state,
        }

    return {"error": "Invalid PR data"}


@app.get("/verify")
async def verify():
    """Get all posted comments for verification."""
    return _posted_comments


@app.post("/reset")
async def reset():
    """Clear all mock data."""
    logger.info("POST /reset")

    global _posted_comments, _pull_requests
    _posted_comments = []
    _pull_requests = {}

    return {"status": "ok"}


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "mock-github",
        "version": "1.0.0",
        "posted_comments": len(_posted_comments),
        "pull_requests": len(_pull_requests),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8092)
