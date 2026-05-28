"""Unit tests for WorkspaceClient."""

import pytest

from nd.clients.workspace import (
    WorkspaceClient,
    _anon_clone_url,
    _askpass_env,
    _check_safe_component,
)


class _FakeProc:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


def _patch_subprocess_sequence(monkeypatch, responses):
    """Patch asyncio.create_subprocess_exec with queued (rc, stdout) tuples.

    Returns ``captured`` with ``cmds`` (list of argv tuples in call order)
    and ``envs`` (list of env dicts that were forwarded). Once the queue is
    down to its last entry, subsequent calls reuse it.
    """
    queue = list(responses)
    captured: dict = {"cmds": [], "envs": []}

    async def fake_exec(*cmd, stdout=None, stderr=None, cwd=None, env=None):
        captured["cmds"].append(cmd)
        captured["envs"].append(env)
        rc, out = queue[0] if len(queue) == 1 else queue.pop(0)
        return _FakeProc(rc, stdout=out, stderr=b"")

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    return captured


def _patch_filesystem_for_prepare(monkeypatch, *, askpass_env=None):
    """Stub the filesystem side effects of ``prepare()``.

    - The atomic worktree-claim ``mkdir``/``rmdir``/``makedirs`` are
      no-ops (we don't want real directories created during unit tests).
    - ``_askpass_env`` is replaced with a deterministic stub by default
      so tests don't have to manage the real tempdir / chmod / file I/O.
      Pass ``askpass_env=({...}, "/tmp/fake")`` to override what the stub
      returns.
    """
    import nd.clients.workspace as ws_mod

    monkeypatch.setattr(ws_mod.os, "mkdir", lambda *_a, **_k: None)
    monkeypatch.setattr(ws_mod.os, "rmdir", lambda *_a, **_k: None)
    monkeypatch.setattr(ws_mod.os, "makedirs", lambda *_a, **_k: None)

    def _fake_askpass(platform, gh, gl):
        if askpass_env is not None:
            return askpass_env
        if platform == "github" and gh:
            return (
                {
                    "GIT_ASKPASS": "/tmp/fake-askpass.sh",
                    "GIT_ASKPASS_USERNAME": "x-access-token",
                    "GIT_ASKPASS_TOKEN": gh,
                    "GIT_TERMINAL_PROMPT": "0",
                },
                None,  # No real tempdir to clean up.
            )
        if platform == "gitlab" and gl:
            return (
                {
                    "GIT_ASKPASS": "/tmp/fake-askpass.sh",
                    "GIT_ASKPASS_USERNAME": "oauth2",
                    "GIT_ASKPASS_TOKEN": gl,
                    "GIT_TERMINAL_PROMPT": "0",
                },
                None,
            )
        return ({}, None)

    monkeypatch.setattr(ws_mod, "_askpass_env", _fake_askpass)


# Backwards-compat alias for tests that don't care about askpass.
_patch_atomic_mkdir_happy = _patch_filesystem_for_prepare


class TestAnonCloneUrl:
    def test_no_token_in_url(self):
        url = _anon_clone_url("github.com", "octocat", "Hello-World")
        assert url == "https://github.com/octocat/Hello-World.git"
        # The token must NEVER appear in the clone URL.
        assert "x-access-token" not in url
        assert "@" not in url

    def test_gitlab(self):
        url = _anon_clone_url("gitlab.com", "org", "repo")
        assert url == "https://gitlab.com/org/repo.git"


class TestCheckSafeComponent:
    def test_rejects_dotdot(self):
        with pytest.raises(ValueError):
            _check_safe_component("..", allow_colon=False, label="owner")

    def test_rejects_slash(self):
        with pytest.raises(ValueError):
            _check_safe_component("a/b", allow_colon=False, label="owner")

    def test_rejects_backslash(self):
        with pytest.raises(ValueError):
            _check_safe_component("a\\b", allow_colon=False, label="owner")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            _check_safe_component("", allow_colon=False, label="owner")

    def test_rejects_traversal_segment(self):
        # Embedded ".." within a slash-bearing string is rejected by the
        # slash check, but a bare ".." also gets rejected explicitly.
        with pytest.raises(ValueError):
            _check_safe_component(".", allow_colon=False, label="owner")

    def test_accepts_normal_owner(self):
        _check_safe_component("octocat", allow_colon=False, label="owner")

    def test_accepts_normal_repo(self):
        _check_safe_component("Hello-World.test_1", allow_colon=False, label="repo")

    def test_host_allows_colon(self):
        _check_safe_component("git.example.com:8443", allow_colon=True, label="host")

    def test_host_rejects_colon_when_disallowed(self):
        with pytest.raises(ValueError):
            _check_safe_component("git.example.com:8443", allow_colon=False, label="repo")


class TestAskpassEnv:
    def test_no_token_returns_empty(self, tmp_path):
        env, tmpdir = _askpass_env("github", "", "")
        assert env == {}
        assert tmpdir is None

    def test_github_token_creates_helper_with_token_in_env_only(self, monkeypatch):
        env, tmpdir = _askpass_env("github", "ghp_secret", "")
        try:
            assert tmpdir is not None
            # Token only travels via env vars, NEVER in argv.
            assert env["GIT_ASKPASS_TOKEN"] == "ghp_secret"
            assert env["GIT_ASKPASS_USERNAME"] == "x-access-token"
            assert env["GIT_TERMINAL_PROMPT"] == "0"
            # The helper script exists and is executable.
            import os
            import stat as _stat

            helper = env["GIT_ASKPASS"]
            mode = os.stat(helper).st_mode
            assert mode & _stat.S_IXUSR, "helper must be executable"
            # Token must NOT appear in the helper script body itself —
            # it must be read from the env at runtime.
            with open(helper) as f:
                body = f.read()
            assert "ghp_secret" not in body
        finally:
            if tmpdir:
                import shutil as _shutil

                _shutil.rmtree(tmpdir, ignore_errors=True)

    def test_gitlab_token_uses_oauth2_username(self):
        env, tmpdir = _askpass_env("gitlab", "", "glpat_xyz")
        try:
            assert env["GIT_ASKPASS_USERNAME"] == "oauth2"
            assert env["GIT_ASKPASS_TOKEN"] == "glpat_xyz"
        finally:
            if tmpdir:
                import shutil as _shutil

                _shutil.rmtree(tmpdir, ignore_errors=True)


class TestWorkspaceClientPaths:
    def test_bare_path_includes_host_owner_repo(self):
        c = WorkspaceClient(root="/var/nd")
        assert (
            c._bare_path("github.com", "octocat", "Hello-World")
            == "/var/nd/repos/github.com/octocat/Hello-World.git"
        )

    def test_bare_path_rejects_traversal_owner(self):
        c = WorkspaceClient(root="/var/nd")
        with pytest.raises(ValueError):
            c._bare_path("github.com", "..", "repo")

    def test_bare_path_rejects_slash_in_repo(self):
        c = WorkspaceClient(root="/var/nd")
        with pytest.raises(ValueError):
            c._bare_path("github.com", "owner", "../etc/passwd")

    def test_bare_path_rejects_slash_in_host(self):
        c = WorkspaceClient(root="/var/nd")
        with pytest.raises(ValueError):
            c._bare_path("github.com/evil", "owner", "repo")

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
        # Bare path missing.
        monkeypatch.setattr("os.path.exists", lambda _p: False)
        _patch_atomic_mkdir_happy(monkeypatch)

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

        # First call: git clone --bare uses anonymous URL — token must NOT
        # appear anywhere in argv.
        first = captured["cmds"][0]
        assert first[0:3] == ("git", "clone", "--bare")
        assert first[3] == "https://github.com/octocat/Hello-World.git"
        assert first[4] == "/var/nd/repos/github.com/octocat/Hello-World.git"
        for arg in first:
            assert "ghp_test" not in arg, f"token leaked into argv: {arg!r}"

        # Token is conveyed via env (GIT_ASKPASS_TOKEN), not argv.
        first_env = captured["envs"][0]
        assert first_env is not None
        assert first_env["GIT_ASKPASS_TOKEN"] == "ghp_test"
        assert first_env["GIT_ASKPASS_USERNAME"] == "x-access-token"

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

        # Bare exists.
        bare = "/var/nd/repos/github.com/octocat/Hello-World.git"

        def fake_exists(p):
            return p == bare

        monkeypatch.setattr("os.path.exists", fake_exists)
        _patch_atomic_mkdir_happy(monkeypatch)

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
        # And no token leaked into the fetch argv.
        for arg in first:
            assert "ghp_test" not in arg


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
        _patch_atomic_mkdir_happy(monkeypatch)

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

        import nd.clients.workspace as ws_mod

        monkeypatch.setattr(ws_mod.os, "makedirs", lambda *_a, **_k: None)
        monkeypatch.setattr(ws_mod.os, "rmdir", lambda *_a, **_k: None)

        # Atomic claim collides — os.mkdir raises FileExistsError.
        def fake_mkdir(_path):
            raise FileExistsError(_path)

        monkeypatch.setattr(ws_mod.os, "mkdir", fake_mkdir)

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
        _patch_atomic_mkdir_happy(monkeypatch)

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
        repo_path = "/var/nd/work/myproj-7by6"
        bare_path = "/var/nd/repos/github.com/octocat/Hello-World.git"
        ok = await c.cleanup(repo_path=repo_path, bare_path=bare_path)
        assert ok is True
        cmd = captured["cmds"][0]
        assert cmd[:3] == ("git", "-C", bare_path)
        assert "worktree" in cmd and "remove" in cmd and "--force" in cmd
        assert cmd[-1] == repo_path

    async def test_falls_back_to_rmtree_on_failure(self, monkeypatch):
        _patch_subprocess_sequence(monkeypatch, [(1, b"")])
        called = {}

        def fake_rmtree(path, ignore_errors=False):
            called["path"] = path
            called["ignore_errors"] = ignore_errors

        monkeypatch.setattr("nd.clients.workspace.shutil.rmtree", fake_rmtree)

        c = WorkspaceClient(root="/var/nd")
        repo_path = "/var/nd/work/myproj-7by6"
        bare_path = "/var/nd/repos/github.com/octocat/Hello-World.git"
        ok = await c.cleanup(repo_path=repo_path, bare_path=bare_path)
        assert ok is False
        assert called == {"path": repo_path, "ignore_errors": True}
