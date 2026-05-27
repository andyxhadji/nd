"""End-to-end smoke test for WorkspaceClient against a real public repo.

Gated on GITHUB_TOKEN being set; uses ``octocat/Hello-World`` as a stable
public fixture. Asserts that ``prepare()`` produces a real worktree and
that ``cleanup()`` removes it.
"""

import os
import shutil
import tempfile

import pytest

from nd.clients.workspace import WorkspaceClient


@pytest.mark.skipif(
    not os.environ.get("GITHUB_TOKEN"),
    reason="needs GITHUB_TOKEN for clone",
)
@pytest.mark.asyncio
async def test_prepare_and_cleanup_against_hello_world():
    tmp_root = tempfile.mkdtemp(prefix="nd-workspace-e2e-")
    try:
        client = WorkspaceClient(
            root=tmp_root,
            github_token=os.environ["GITHUB_TOKEN"],
        )
        ws = await client.prepare(
            platform="github",
            platform_host="github.com",
            repo_owner="octocat",
            repo_name="Hello-World",
            head_branch="master",
            base_branch="master",
            task_slug="smoke-e2e",
        )
        assert ws is not None, "prepare returned None"
        assert os.path.isdir(ws.repo_path)
        # Worktrees use a `.git` file (gitlink), not a `.git` directory.
        assert os.path.exists(os.path.join(ws.repo_path, ".git"))

        await client.cleanup(ws)
        assert not os.path.exists(ws.repo_path)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
