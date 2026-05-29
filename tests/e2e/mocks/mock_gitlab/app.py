"""Mock GitLab API for E2E testing."""

import logging
from typing import Any

from fastapi import FastAPI, Header, Path
from pydantic import BaseModel

app = FastAPI(title="Mock GitLab", version="1.0.0")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# In-memory storage for posted notes
_posted_notes: list[dict[str, Any]] = []
_merge_requests: dict[str, dict[str, Any]] = {}


class NoteBody(BaseModel):
    """GitLab note body."""

    body: str


class MergeRequest(BaseModel):
    """Merge request structure."""

    iid: int
    title: str
    state: str = "opened"
    source_branch: str
    target_branch: str


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/api/v4/projects/{project_id}/merge_requests/{mr_iid}/discussions/{discussion_id}/notes")
async def create_discussion_note(
    project_id: str = Path(...),
    mr_iid: int = Path(...),
    discussion_id: str = Path(...),
    note: NoteBody = None,
    private_token: str | None = Header(None, alias="PRIVATE-TOKEN"),
):
    """Mock endpoint for posting MR discussion notes."""
    logger.info(
        f"POST /api/v4/projects/{project_id}/merge_requests/{mr_iid}/discussions/{discussion_id}/notes"
    )
    logger.info(f"Body: {note.body if note else 'None'}")

    # Store the note
    _posted_notes.append(
        {
            "project_id": project_id,
            "mr_iid": mr_iid,
            "discussion_id": discussion_id,
            "body": note.body if note else "",
            "private_token": private_token,
        }
    )

    return {
        "id": len(_posted_notes),
        "body": note.body if note else "",
        "author": {"username": "nd-worker"},
    }


@app.get("/api/v4/projects/{project_id}/merge_requests/{mr_iid}")
async def get_merge_request(
    project_id: str = Path(...),
    mr_iid: int = Path(...),
):
    """Mock endpoint for getting MR details."""
    logger.info(f"GET /api/v4/projects/{project_id}/merge_requests/{mr_iid}")

    key = f"{project_id}/{mr_iid}"
    if key in _merge_requests:
        return _merge_requests[key]

    # Return default MR if not found
    return {
        "iid": mr_iid,
        "title": f"Mock MR !{mr_iid}",
        "state": "opened",
        "source_branch": "feature-branch",
        "target_branch": "main",
        "web_url": f"https://gitlab.com/project/{project_id}/-/merge_requests/{mr_iid}",
    }


@app.post("/api/v4/projects/{project_id}/merge_requests")
async def create_merge_request(
    project_id: str = Path(...),
    mr: MergeRequest = None,
    private_token: str | None = Header(None, alias="PRIVATE-TOKEN"),
):
    """Mock endpoint for creating a merge request."""
    logger.info(f"POST /api/v4/projects/{project_id}/merge_requests")

    if mr:
        key = f"{project_id}/{mr.iid}"
        _merge_requests[key] = mr.model_dump()

        return {
            "iid": mr.iid,
            "web_url": f"https://gitlab.com/project/{project_id}/-/merge_requests/{mr.iid}",
            "title": mr.title,
            "state": mr.state,
        }

    return {"error": "Invalid MR data"}


@app.get("/verify")
async def verify():
    """Get all posted notes for verification."""
    return _posted_notes


@app.post("/reset")
async def reset():
    """Clear all mock data."""
    logger.info("POST /reset")

    global _posted_notes, _merge_requests
    _posted_notes = []
    _merge_requests = {}

    return {"status": "ok"}


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "mock-gitlab",
        "version": "1.0.0",
        "posted_notes": len(_posted_notes),
        "merge_requests": len(_merge_requests),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8093)
