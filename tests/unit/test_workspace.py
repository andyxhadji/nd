"""Unit tests for WorkspaceClient."""

import pytest

from nd.clients.workspace import Workspace, WorkspaceClient, _auth_clone_url


class _FakeProc:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


def _patch_subprocess_sequence(monkeypatch, responses):
    """Patch asyncio.create_subprocess_exec with queued (rc, stdout) tuples.

    Returns ``captured`` with ``cmds`` (list of argv tuples in call order).
    Once the queue is down to its last entry, subsequent calls reuse it.
    """
    queue = list(responses)
    captured: dict = {"cmds": []}

    async def fake_exec(*cmd, stdout=None, stderr=None, cwd=None):
        captured["cmds"].append(cmd)
        rc, out = queue[0] if len(queue) == 1 else queue.pop(0)
        return _FakeProc(rc, stdout=out, stderr=b"")

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    return captured


class TestAuthCloneUrl:
    def test_github_with_token(self):
        url = _auth_clone_url("github", "github.com", "octocat", "Hello-World", "ghp_abc", "")
        assert url == "https://x-access-token:ghp_abc@github.com/octocat/Hello-World.git"

    def test_gitlab_with_token(self):
        url = _auth_clone_url("gitlab", "gitlab.com", "org", "repo", "", "glpat_xyz")
        assert url == "https://oauth2:glpat_xyz@gitlab.com/org/repo.git"

    def test_github_without_token_falls_back_to_anonymous(self):
        url = _auth_clone_url("github", "github.com", "octocat", "Hello-World", "", "")
        assert url == "https://github.com/octocat/Hello-World.git"

    def test_gitlab_without_token_falls_back_to_anonymous(self):
        url = _auth_clone_url("gitlab", "gitlab.com", "org", "repo", "", "")
        assert url == "https://gitlab.com/org/repo.git"


class TestWorkspaceClientPaths:
    def test_bare_path_includes_host_owner_repo(self):
        c = WorkspaceClient(root="/var/nd")
        assert (
            c._bare_path("github.com", "octocat", "Hello-World")
            == "/var/nd/repos/github.com/octocat/Hello-World.git"
        )

    def test_worktree_path_sanitizes_unsafe_chars(self):
        c = WorkspaceClient(root="/var/nd")
        # Slash and "#" should be replaced; trailing/leading dashes stripped.
        path = c._worktree_path("group/sub#abcd")
        assert path == "/var/nd/work/group-sub-abcd"


@pytest.mark.asyncio
class TestPrepareNoExistingCache:
    async def test_clones_bare_then_adds_worktree(self, monkeypatch):
        captured = _patch_subprocess_sequence(
            monkeypatch,
            [
                (0, b""),  # git clone --bare
                (0, b""),  # git worktree add
            ],
        )
        # Bare path missing, worktree path missing.
        monkeypatch.setattr("os.path.exists", lambda _p: False)
        monkeypatch.setattr("os.makedirs", lambda *_a, **_k: None)

        c = WorkspaceClient(root="/var/nd", github_token="ghp_test", gitlab_token="")
        ws = await c.prepare(
            platform="github",
            platform_host="github.com",
            repo_owner="octocat",
            repo_name="Hello-World",
            head_branch="master",
            base_branch="master",
            task_slug="myproj-7by6",
        )

        assert ws is not None
        assert ws.repo_path == "/var/nd/work/myproj-7by6"
        assert ws.branch == "master"
        assert ws.base_branch == "master"
        assert ws.bare_path == "/var/nd/repos/github.com/octocat/Hello-World.git"

        # First call: git clone --bare <auth_url> <bare_path>
        first = captured["cmds"][0]
        assert first[0:3] == ("git", "clone", "--bare")
        assert first[3] == "https://x-access-token:ghp_test@github.com/octocat/Hello-World.git"
        assert first[4] == "/var/nd/repos/github.com/octocat/Hello-World.git"

        # Second call: git -C <bare> worktree add <wt> <branch>
        second = captured["cmds"][1]
        assert second[:3] == ("git", "-C", "/var/nd/repos/github.com/octocat/Hello-World.git")
        assert "worktree" in second and "add" in second
        assert second[-2:] == ("/var/nd/work/myproj-7by6", "master")


@pytest.mark.asyncio
class TestPrepareExistingCache:
    async def test_fetches_then_adds_worktree(self, monkeypatch):
        captured = _patch_subprocess_sequence(
            monkeypatch,
            [
                (0, b""),  # git fetch --prune ...
                (0, b""),  # git worktree add
            ],
        )

        # Bare exists, worktree does not.
        bare = "/var/nd/repos/github.com/octocat/Hello-World.git"
        worktree = "/var/nd/work/myproj-7by6"

        def fake_exists(p):
            if p == bare:
                return True
            if p == worktree:
                return False
            return False

        monkeypatch.setattr("os.path.exists", fake_exists)
        monkeypatch.setattr("os.makedirs", lambda *_a, **_k: None)

        c = WorkspaceClient(root="/var/nd", github_token="ghp_test")
        ws = await c.prepare(
            platform="github",
            platform_host="github.com",
            repo_owner="octocat",
            repo_name="Hello-World",
            head_branch="master",
            base_branch="master",
            task_slug="myproj-7by6",
        )

        assert ws is not None
        # First call should be `git -C <bare> fetch --prune ...`
        first = captured["cmds"][0]
        assert first[0:5] == ("git", "-C", bare, "fetch", "--prune")
        # No `git clone --bare` was issued.
        assert all(c[0:3] != ("git", "clone", "--bare") for c in captured["cmds"])


@pytest.mark.asyncio
class TestPrepareIssueBranch:
    async def test_issue_creates_nd_issue_branch(self, monkeypatch):
        captured = _patch_subprocess_sequence(
            monkeypatch,
            [
                (0, b""),  # git clone --bare
                (0, b"main\n"),  # git symbolic-ref --short HEAD -> main
                (0, b""),  # git worktree add -b nd/issue-7by6 ... main
            ],
        )
        monkeypatch.setattr("os.path.exists", lambda _p: False)
        monkeypatch.setattr("os.makedirs", lambda *_a, **_k: None)

        c = WorkspaceClient(root="/var/nd")
        ws = await c.prepare(
            platform="github",
            platform_host="github.com",
            repo_owner="octocat",
            repo_name="Hello-World",
            head_branch=None,
            base_branch=None,
            task_slug="myproj-7by6",
            issue_short_id="7by6",
        )

        assert ws is not None
        assert ws.branch == "nd/issue-7by6"
        assert ws.base_branch == "main"

        # The third subprocess call is the worktree add with -b nd/issue-7by6 main.
        third = captured["cmds"][2]
        assert "-b" in third
        idx = third.index("-b")
        assert third[idx + 1] == "nd/issue-7by6"
        assert third[-1] == "main"


@pytest.mark.asyncio
class TestPrepareWorktreeAlreadyExists:
    async def test_returns_none_without_running_git(self, monkeypatch):
        calls: list = []

        async def fake_exec(*cmd, **_k):
            calls.append(cmd)
            return _FakeProc(0)

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)

        worktree = "/var/nd/work/myproj-7by6"

        def fake_exists(p):
            return p == worktree

        monkeypatch.setattr("os.path.exists", fake_exists)

        c = WorkspaceClient(root="/var/nd")
        ws = await c.prepare(
            platform="github",
            platform_host="github.com",
            repo_owner="octocat",
            repo_name="Hello-World",
            head_branch="master",
            base_branch="master",
            task_slug="myproj-7by6",
        )

        assert ws is None
        assert calls == []


@pytest.mark.asyncio
class TestPrepareCloneFailure:
    async def test_returns_none_when_clone_fails(self, monkeypatch):
        _patch_subprocess_sequence(
            monkeypatch,
            [(128, b"")],  # git clone --bare fails
        )
        monkeypatch.setattr("os.path.exists", lambda _p: False)
        monkeypatch.setattr("os.makedirs", lambda *_a, **_k: None)

        c = WorkspaceClient(root="/var/nd")
        ws = await c.prepare(
            platform="github",
            platform_host="github.com",
            repo_owner="octocat",
            repo_name="Hello-World",
            head_branch="master",
            base_branch="master",
            task_slug="myproj-7by6",
        )
        assert ws is None


@pytest.mark.asyncio
class TestCleanup:
    async def test_runs_worktree_remove_force(self, monkeypatch):
        captured = _patch_subprocess_sequence(monkeypatch, [(0, b"")])
        c = WorkspaceClient(root="/var/nd")
        ws = Workspace(
            repo_path="/var/nd/work/myproj-7by6",
            branch="master",
            base_branch="master",
            bare_path="/var/nd/repos/github.com/octocat/Hello-World.git",
        )
        await c.cleanup(ws)
        cmd = captured["cmds"][0]
        assert cmd[:3] == ("git", "-C", ws.bare_path)
        assert "worktree" in cmd and "remove" in cmd and "--force" in cmd
        assert cmd[-1] == ws.repo_path

    async def test_falls_back_to_rmtree_on_failure(self, monkeypatch):
        _patch_subprocess_sequence(monkeypatch, [(1, b"")])
        called = {}

        def fake_rmtree(path, ignore_errors=False):
            called["path"] = path
            called["ignore_errors"] = ignore_errors

        monkeypatch.setattr("nd.clients.workspace.shutil.rmtree", fake_rmtree)

        c = WorkspaceClient(root="/var/nd")
        ws = Workspace(
            repo_path="/var/nd/work/myproj-7by6",
            branch="",
            base_branch="",
            bare_path="/var/nd/repos/github.com/octocat/Hello-World.git",
        )
        await c.cleanup(ws)
        assert called == {"path": ws.repo_path, "ignore_errors": True}
