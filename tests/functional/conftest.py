"""Functional test fixtures."""

import os
import pytest
import httpx
from agentfield import AIConfig


@pytest.fixture(scope="session")
def control_plane_url() -> str:
    return os.environ.get("AGENTFIELD_SERVER", "http://localhost:8080")


@pytest.fixture(scope="session")
def openrouter_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        pytest.skip("OPENROUTER_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def openrouter_model() -> str:
    return os.environ.get("OPENROUTER_MODEL", "openrouter/google/gemini-2.5-flash-lite")


@pytest.fixture
def openrouter_config(openrouter_api_key: str, openrouter_model: str) -> AIConfig:
    return AIConfig(
        model=openrouter_model,
        api_key=openrouter_api_key,
        temperature=0.3,
    )


@pytest.fixture
async def async_http_client(control_plane_url: str):
    async with httpx.AsyncClient(
        base_url=control_plane_url,
        timeout=60.0,
    ) as client:
        yield client


@pytest.fixture
def mock_middleman_comment() -> dict:
    return {
        "id": "test-comment-001",
        "body": "Can you add logging to this function?",
        "author": "reviewer",
        "created_at": "2026-05-27T10:00:00Z",
        "dedupe_key": "gitlab:gitlab.com:testorg/testrepo:mr:42:note:12345",
        "mr_number": 42,
        "mr_title": "Add new feature",
        "mr_url": "https://gitlab.com/testorg/testrepo/-/merge_requests/42",
        "head_branch": "feature-branch",
        "base_branch": "main",
        "platform": "gitlab",
        "platform_host": "gitlab.com",
        "repo_owner": "testorg",
        "repo_name": "testrepo",
    }
