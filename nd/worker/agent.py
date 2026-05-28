"""Worker agent definition with AgentField reasoners."""

import asyncio
import re

import httpx
from agentfield import Agent, AIConfig
from pydantic import BaseModel

from nd.clients.kata import KataClient
from nd.clients.platform import PlatformClient
from nd.clients.workspace import WorkspaceClient
from nd.config import config
from nd.schemas import (
    AnalysisInput,
    AnalysisResult,
    ClaimResult,
    DraftResult,
    ExecutionResult,
    ProcessResult,
    PublishResult,
    RoborevResult,
    SpecDocument,
    WorkspaceResult,
)
from nd.worker.analyzer import TaskAnalyzer


def create_worker_agent(
    node_id: str = "nd-worker",
    ai_config: AIConfig | None = None,
) -> Agent:
    """Create and configure the worker agent."""

    if ai_config is None:
        ai_config = AIConfig(
            model=config.worker_model,
        )

    app = Agent(
        node_id=node_id,
        version="1.0.0",
        agentfield_server=config.agentfield_url,
        ai_config=ai_config,
    )

    # Initialize clients
    kata = KataClient(kata_server=config.kata_server)
    _platform = PlatformClient(  # noqa: F841 - used in future reasoners
        github_token=config.github_token,
        gitlab_token=config.gitlab_token,
    )
    workspace = WorkspaceClient(
        root=config.workspace_root,
        github_token=config.github_token,
        gitlab_token=config.gitlab_token,
    )
    analyzer = TaskAnalyzer()

    @app.on_event("shutdown")
    async def _close_clients() -> None:
        """Close httpx connection pools on agent shutdown."""
        await _platform.close()

    # ========================================================================
    # Reasoners
    # ========================================================================

    @app.reasoner(tags=["entry"])
    # @on_schedule("* * * * *")  # Disabled - trigger manually
    async def claim_task(payload: dict | None = None) -> dict:
        """
        Poll kata for unclaimed tasks and claim one for processing.

        Triggered manually (cron decorator disabled). The `payload` parameter
        accepts the cron event ({expression, fired_at, timezone}) that
        AgentField passes as a single positional argument when triggered via
        cron; it is unused.

        Note: parameter is intentionally NOT named `trigger` or `webhook` —
        AgentField auto-injects those names as kwargs, which would collide
        with the positional payload from cron triggers.
        """
        # Get available tasks
        tasks = await kata.ready(label="nd", unowned=True)
        if not tasks:
            return ClaimResult(claimed=False).model_dump()

        # Claim first available
        task = tasks[0]
        success = await kata.assign(task.id, config.agent_instance_id)
        if not success:
            return ClaimResult(claimed=False).model_dump()

        # Add in-progress label
        await kata.label(task.id, "in-progress")

        # Process the task
        await app.call(
            f"{app.node_id}.process_task",
            task_id=task.id,
            project=task.project,
            title=task.title,
            body=task.body,
            labels=task.labels,
        )

        return ClaimResult(
            claimed=True,
            task_id=task.id,
            project=task.project,
        ).model_dump()

    @app.reasoner()
    async def prepare_workspace(
        task_id: str,
        project: str,
        platform: str,
        platform_host: str,
        repo_owner: str,
        repo_name: str,
        head_branch: str | None = None,
        base_branch: str | None = None,
        is_issue: bool = False,
        issue_short_id: str | None = None,
    ) -> dict:
        """Clone-or-fetch the bare cache and create a per-task git worktree.

        For MR tasks, ``head_branch`` must be set; the worker checks it out
        directly. For issue tasks pass ``is_issue=True`` (and optionally
        ``issue_short_id``); the worker creates ``nd/issue-<short_id>`` off
        the resolved base branch.
        """
        task_slug = f"{project}-{issue_short_id or task_id}".replace("#", "-")
        ws = await workspace.prepare(
            platform=platform,
            platform_host=platform_host,
            repo_owner=repo_owner,
            repo_name=repo_name,
            head_branch=None if is_issue else head_branch,
            base_branch=base_branch,
            task_slug=task_slug,
            issue_short_id=issue_short_id if is_issue else None,
        )
        if ws is None:
            return WorkspaceResult(
                prepared=False,
                error="workspace prep failed",
            ).model_dump()
        return WorkspaceResult(
            prepared=True,
            repo_path=ws.repo_path,
            branch=ws.branch,
            base_branch=ws.base_branch,
            bare_path=ws.bare_path,
        ).model_dump()

    @app.reasoner()
    async def cleanup_workspace(repo_path: str, bare_path: str) -> dict:
        """Best-effort worktree teardown after task completion.

        Returns ``{"cleaned": bool}`` reflecting whether the underlying
        ``git worktree remove`` succeeded. ``False`` indicates we had to
        fall back to ``rm -rf``.
        """
        cleaned = await workspace.cleanup(repo_path=repo_path, bare_path=bare_path)
        return {"cleaned": cleaned}

    @app.reasoner()
    async def process_task(
        task_id: str,
        project: str,
        title: str,
        body: str,
        labels: list[str],
    ) -> dict:
        """Orchestrate the full task processing flow."""
        # Parse task body to extract context
        context = _parse_task_body(body)
        if not context:
            return ProcessResult(
                status="failed",
                error="Could not parse task body",
            ).model_dump()

        # Prepare workspace: clone-or-fetch the bare cache and create a
        # per-task git worktree. Failure here aborts before we touch the LLM.
        is_issue = context.get("category") == "issue"
        ws_result = await app.call(
            f"{app.node_id}.prepare_workspace",
            task_id=task_id,
            project=project,
            platform=context.get("platform", ""),
            platform_host=context.get("platform_host", ""),
            repo_owner=context.get("repo_owner", ""),
            repo_name=context.get("repo_name", project),
            head_branch=context.get("head_branch"),
            base_branch=context.get("base_branch"),
            is_issue=is_issue,
            issue_short_id=task_id.split("#")[-1] if "#" in task_id else None,
        )
        ws = WorkspaceResult(**ws_result)
        if not ws.prepared or ws.repo_path is None:
            await kata.label(task_id, "needs-human")
            return ProcessResult(
                status="failed",
                error=f"workspace prep failed: {ws.error}",
            ).model_dump()
        repo_path = ws.repo_path

        async def _maybe_cleanup_on_failure() -> None:
            """Tear down the worktree on failure/pause when configured.

            The default (``WORKSPACE_KEEP_ON_FAILURE=1``) leaves the worktree
            in place for human inspection. Operators that don't want stale
            worktrees can set ``WORKSPACE_KEEP_ON_FAILURE=0`` to have us
            clean up here too.
            """
            if config.workspace_keep_on_failure:
                return
            if ws.bare_path is None:
                return
            await app.call(
                f"{app.node_id}.cleanup_workspace",
                repo_path=repo_path,
                bare_path=ws.bare_path,
            )

        # Analyze task
        analysis_result = await app.call(
            f"{app.node_id}.analyze_task",
            comment_body=context["comment_body"],
            comment_category=context.get("category", "request"),
            mr_title=context.get("mr_title", ""),
            head_branch=context.get("head_branch", ""),
            repo_path=repo_path,
        )
        analysis = AnalysisResult(**analysis_result)

        # Check confidence threshold - create spec for low confidence tasks
        spec: SpecDocument | None = None
        if analysis.confidence < config.confidence_threshold:
            # Create spec and pause for review
            spec_result = await app.call(
                f"{app.node_id}.plan_changes",
                task_id=task_id,
                comment_body=context["comment_body"],
                analysis=analysis.model_dump(),
                repo_path=repo_path,
            )
            spec = SpecDocument(**spec_result)

            # Pause for human spec review
            approval = await app.pause(
                approval_request_id=f"spec-{task_id}",
                approval_request_url=context.get("mr_url", ""),
                expires_in_hours=72,
                timeout=259200,
            )

            if not approval.approved:
                await kata.label(task_id, "needs-human")
                await _maybe_cleanup_on_failure()
                return ProcessResult(
                    status="paused_for_spec",
                    error="Spec rejected by human reviewer",
                ).model_dump()

        # Execute changes via harness
        exec_result = await app.call(
            f"{app.node_id}.execute_changes",
            task_id=task_id,
            comment_body=context["comment_body"],
            repo_path=repo_path,
            head_branch=context.get("head_branch", "main"),
            spec=spec.model_dump() if spec else None,
        )
        execution = ExecutionResult(**exec_result)

        if not execution.success:
            await kata.label(task_id, "failed")
            await _maybe_cleanup_on_failure()
            return ProcessResult(
                status="failed",
                error=execution.error,
            ).model_dump()

        # Run roborev
        roborev_result = await app.call(
            f"{app.node_id}.run_roborev",
            repo_path=repo_path,
            commit_sha=execution.commit_sha or "",
            max_iterations=config.roborev_max_iterations,
        )
        roborev = RoborevResult(**roborev_result)

        if not roborev.passed:
            # Pause for human review of roborev failure
            approval = await app.pause(
                approval_request_id=f"roborev-{task_id}",
                approval_request_url=context.get("mr_url", ""),
                expires_in_hours=72,
                timeout=259200,
            )

            if not approval.approved:
                await kata.label(task_id, "needs-human")
                await _maybe_cleanup_on_failure()
                return ProcessResult(
                    status="paused_for_review",
                    error="Roborev failed and human rejected",
                ).model_dump()

        publish_result = await app.call(
            f"{app.node_id}.publish_changes",
            repo_path=repo_path,
            branch=ws.branch or context.get("head_branch", ""),
            platform=context.get("platform", ""),
            platform_host=context.get("platform_host", ""),
            repo_owner=context.get("repo_owner", ""),
            repo_name=context.get("repo_name", project),
            base_branch=ws.base_branch or context.get("base_branch", "main"),
            title=context.get("mr_title", title),
            source_url=context.get("mr_url", ""),
            is_issue=is_issue,
        )
        publish = PublishResult(**publish_result)
        if not publish.pushed or publish.error:
            await kata.label(task_id, "failed")
            await _maybe_cleanup_on_failure()
            return ProcessResult(
                status="failed",
                error=publish.error or "publish failed",
            ).model_dump()

        # Draft response
        draft_result = await app.call(
            f"{app.node_id}.draft_response",
            comment_body=context["comment_body"],
            changes_made=execution.files_changed,
            commit_sha=execution.commit_sha or "",
            commit_diff="",
        )
        draft = DraftResult(**draft_result)

        # Always pause for response approval
        approval = await app.pause(
            approval_request_id=f"post-{task_id}",
            approval_request_url=publish.merge_request_url or context.get("mr_url", ""),
            expires_in_hours=72,
            timeout=259200,
        )

        if not approval.approved:
            await kata.label(task_id, "addressed")
            await _maybe_cleanup_on_failure()
            return ProcessResult(
                status="paused_for_review",
                changes_made=execution.files_changed,
                response_draft=draft.response_text,
            ).model_dump()

        # Get potentially edited response from approval
        final_response = approval.feedback or draft.response_text

        # Issue tasks create a new MR instead of replying to an existing MR
        # discussion thread.
        if not is_issue:
            await app.call(
                f"{app.node_id}.post_response",
                response_text=final_response,
                dedupe_key=context.get("dedupe_key", ""),
                platform=context.get("platform", ""),
                platform_host=context.get("platform_host", ""),
                repo_owner=context.get("repo_owner", ""),
                repo_name=project,
                mr_number=context.get("mr_number", 0),
            )

        # Finalize task
        await app.call(
            f"{app.node_id}.finalize_task",
            task_id=task_id,
            status="completed",
            response_posted=True,
            commit_sha=execution.commit_sha,
            merge_request_url=publish.merge_request_url,
        )

        # Clean up the worktree only on successful completion. Failed and
        # paused tasks leave the worktree in place for human inspection.
        if ws.bare_path is not None:
            await app.call(
                f"{app.node_id}.cleanup_workspace",
                repo_path=repo_path,
                bare_path=ws.bare_path,
            )

        return ProcessResult(
            status="completed",
            changes_made=execution.files_changed,
            response_draft=final_response,
        ).model_dump()

    @app.reasoner()
    async def analyze_task(
        comment_body: str,
        comment_category: str,
        mr_title: str,
        head_branch: str,
        repo_path: str,
    ) -> dict:
        """Analyze task complexity and confidence."""
        input_data = AnalysisInput(
            comment_body=comment_body,
            comment_category=comment_category,
            mr_title=mr_title,
            head_branch=head_branch,
            repo_path=repo_path,
        )

        # Get deterministic estimate
        result = analyzer.analyze_deterministic(input_data)

        # Enhance with LLM for suggested approach
        class ApproachSuggestion(BaseModel):
            suggested_approach: str
            additional_files: list[str]
            confident: bool

        llm_result = await app.ai(
            system="""You are analyzing a code review comment to suggest an approach.
Given the comment and estimated complexity, suggest a brief approach (2-3 sentences).
Also list any additional files that might need changes.""",
            user=f"""Comment: {comment_body}
Category: {comment_category}
Estimated complexity: {result.complexity}/5
Files mentioned: {result.files_likely_affected}""",
            schema=ApproachSuggestion,
        )

        result.suggested_approach = llm_result.suggested_approach
        result.files_likely_affected.extend(llm_result.additional_files)
        result.confident = llm_result.confident and result.confident

        return result.model_dump()

    @app.reasoner()
    async def plan_changes(
        task_id: str,
        comment_body: str,
        analysis: dict,
        repo_path: str,
    ) -> dict:
        """Create a detailed spec for complex tasks."""
        analysis_obj = AnalysisResult(**analysis)

        llm_result = await app.ai(
            system="""You are creating a spec document for a code change.
Be specific about what files to modify and how.
Include risks and questions for the human reviewer.""",
            user=f"""Task: {comment_body}

Analysis:
- Complexity: {analysis_obj.complexity}/5
- Confidence: {analysis_obj.confidence}%
- Files: {analysis_obj.files_likely_affected}
- Approach: {analysis_obj.suggested_approach}

Create a detailed spec.""",
            schema=SpecDocument,
        )

        return llm_result.model_dump()

    @app.reasoner()
    async def execute_changes(
        task_id: str,
        comment_body: str,
        repo_path: str,
        head_branch: str,
        spec: dict | None = None,
    ) -> dict:
        """Execute code changes using the harness."""
        goal = (
            "Address this code review comment:\n\n"
            f"{comment_body}\n\n"
            "Make the requested change and run a focused verification if practical. "
            "Leave the resulting file edits in the repository; the worker will commit them."
        )
        if spec:
            spec_obj = SpecDocument(**spec)
            goal += f"\n\nSpec:\n{spec_obj.proposed_solution}"

        try:

            async def _git(args: list[str]) -> tuple[int, str]:
                proc = await asyncio.create_subprocess_exec(
                    "git",
                    "-C",
                    repo_path,
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                out, _ = await proc.communicate()
                return proc.returncode, out.decode().strip()

            rc_before, before_sha = await _git(["rev-parse", "HEAD"])
            before_sha = before_sha if rc_before == 0 else ""

            await app.harness(
                prompt=goal,
                provider="claude-code",
                tools=["Read", "Write", "Edit"],
                permission_mode="acceptEdits",
                max_turns=20,
                cwd=repo_path,
            )

            rc_sha, sha = await _git(["rev-parse", "HEAD"])
            commit_sha = sha if rc_sha == 0 and sha else None

            rc_status, status_text = await _git(["status", "--porcelain"])
            dirty_files = (
                [
                    (line[3:] if len(line) > 3 and line[2] == " " else line[2:].lstrip())
                    for line in status_text.splitlines()
                    if len(line) > 2
                ]
                if rc_status == 0
                else []
            )

            if commit_sha == before_sha and not dirty_files:
                return ExecutionResult(
                    success=False,
                    error="harness completed without producing changes",
                ).model_dump()

            if dirty_files:
                await _git(["config", "user.email", "nd-worker@example.com"])
                await _git(["config", "user.name", "ND Worker"])
                add_rc, _ = await _git(["add", "--", *dirty_files])
                commit_rc, _ = await _git(
                    [
                        "commit",
                        "-m",
                        f"Address ND task {task_id}",
                    ]
                )
                if add_rc != 0 or commit_rc != 0:
                    return ExecutionResult(
                        success=False,
                        files_changed=dirty_files,
                        commit_sha=commit_sha,
                        error="harness completed with uncommitted changes",
                    ).model_dump()
                rc_sha, sha = await _git(["rev-parse", "HEAD"])
                commit_sha = sha if rc_sha == 0 and sha else None

            if commit_sha == before_sha:
                return ExecutionResult(
                    success=False,
                    error="harness completed without committing changes",
                ).model_dump()

            rc_files, files_text = await _git(
                [
                    "diff",
                    "--name-only",
                    f"{before_sha}..HEAD",
                ],
            )
            files_changed = [f for f in files_text.splitlines() if f] if rc_files == 0 else []

            return ExecutionResult(
                success=True,
                files_changed=files_changed,
                commit_sha=commit_sha,
            ).model_dump()

        except (TimeoutError, httpx.TimeoutException) as e:
            return ExecutionResult(
                success=False,
                error=f"Timeout: {e}",
            ).model_dump()
        except httpx.HTTPError as e:
            return ExecutionResult(
                success=False,
                error=f"HTTP error: {e}",
            ).model_dump()
        except RuntimeError as e:
            return ExecutionResult(
                success=False,
                error=f"Runtime error: {e}",
            ).model_dump()
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Unexpected error: {type(e).__name__}: {e}",
            ).model_dump()

    @app.reasoner()
    async def run_roborev(
        repo_path: str,
        commit_sha: str,
        max_iterations: int = 3,
    ) -> dict:
        """Run roborev-refine for code quality validation."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "roborev",
                "refine",
                "--max-iterations",
                str(max_iterations),
                "--wait",
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            passed = proc.returncode == 0
            findings = []
            if not passed:
                # Parse stderr for findings, filtering empty lines
                stderr_text = stderr.decode(errors="replace")
                raw_lines = stderr_text.split("\n")
                findings = [line.strip() for line in raw_lines if line.strip()][:10]

            return RoborevResult(
                passed=passed,
                iterations=max_iterations,
                final_findings=findings,
            ).model_dump()

        except FileNotFoundError:
            return RoborevResult(
                passed=True,
                iterations=0,
                error="roborev not found",
            ).model_dump()

    @app.reasoner()
    async def draft_response(
        comment_body: str,
        changes_made: list[str],
        commit_sha: str,
        commit_diff: str,
    ) -> dict:
        """Generate response text based on changes made."""

        class ResponseDraft(BaseModel):
            message: str
            confident: bool

        llm_result = await app.ai(
            system="""You are helping draft a reply to a code review comment.
Write a concise, professional message. Mention the commit SHA.
Offer to make adjustments if needed.""",
            user=f"""The author said: {comment_body}

We changed these files: {changes_made}
In this commit: {commit_sha}

Write the reply message and indicate if you're confident the changes fully address their comment.""",
            schema=ResponseDraft,
        )

        # Handle double-nested JSON if the LLM wraps the response
        message = llm_result.message
        confident = llm_result.confident

        if isinstance(message, str) and message.strip().startswith("{"):
            try:
                import json
                nested = json.loads(message)
                # If LLM returned nested JSON, extract the inner values
                if isinstance(nested, dict) and "message" in nested:
                    message = nested["message"]
                    confident = nested.get("confident", confident)
            except (json.JSONDecodeError, TypeError):
                pass  # Use original values if parsing fails

        return DraftResult(
            response_text=message,
            confident=confident,
        ).model_dump()

    @app.reasoner()
    async def publish_changes(
        repo_path: str,
        branch: str,
        platform: str,
        platform_host: str,
        repo_owner: str,
        repo_name: str,
        base_branch: str,
        title: str,
        source_url: str,
        is_issue: bool,
    ) -> dict:
        """Push committed changes and create an MR for issue tasks."""
        if not branch:
            return PublishResult(pushed=False, error="missing branch").model_dump()

        pushed = await workspace.push(
            platform=platform,
            repo_path=repo_path,
            branch=branch,
        )
        if not pushed:
            return PublishResult(pushed=False, error="git push failed").model_dump()

        if not is_issue:
            return PublishResult(pushed=True).model_dump()

        mr_url = await _platform.create_merge_request(
            platform=platform,
            platform_host=platform_host,
            owner=repo_owner,
            repo=repo_name,
            source_branch=branch,
            target_branch=base_branch,
            title=title,
            body=f"Addresses {source_url}",
        )
        if not mr_url:
            return PublishResult(
                pushed=True,
                error="merge request creation failed",
            ).model_dump()
        return PublishResult(pushed=True, merge_request_url=mr_url).model_dump()

    @app.reasoner()
    async def post_response(
        response_text: str,
        dedupe_key: str,
        platform: str,
        platform_host: str,
        repo_owner: str,
        repo_name: str,
        mr_number: int,
    ) -> dict:
        """Post approved response to the MR."""
        parts = dedupe_key.split(":")
        thread_id = parts[-1] if len(parts) >= 7 else ""

        success = await _platform.post_response(
            platform=platform,
            platform_host=platform_host,
            owner=repo_owner,
            repo=repo_name,
            mr_number=mr_number,
            thread_id=thread_id,
            body=response_text,
        )

        return {"posted": success}

    @app.reasoner()
    async def finalize_task(
        task_id: str,
        status: str,
        response_posted: bool,
        commit_sha: str | None = None,
        merge_request_url: str | None = None,
    ) -> dict:
        """Update kata task state after completion."""
        if response_posted:
            if merge_request_url:
                await kata.comment(task_id, f"Merge request created: {merge_request_url}")
            else:
                await kata.comment(
                    task_id,
                    f"Response posted. Commit: {commit_sha or 'N/A'}",
                )
            await kata.label(task_id, "responded")
            await kata.close(task_id, reason="done", comment="Addressed and responded")
        elif status == "failed":
            await kata.label(task_id, "failed")
        else:
            await kata.label(task_id, "needs-human")

        return {"finalized": True, "status": status}

    return app


def _parse_task_body(body: str) -> dict | None:
    """Parse structured task body to extract context.

    Supports both MR-shaped bodies (built by ``KataClient.build_task_body``,
    starting with ``## MR Context``) and issue-shaped bodies (built by
    ``KataClient.build_issue_task_body``, starting with ``## Issue Context``).
    Issue bodies have no branch info; ``prepare_workspace`` will create a
    branch off origin/HEAD.
    """
    context: dict = {}

    # Issue-shaped body. ``## Issue Context`` is the first heading and
    # ``**Issue:** [owner/repo#N](url)`` identifies the source issue.
    issue_match = re.search(
        r"## Issue Context\s*\n.*?\*\*Issue:\*\* \[([^/]+)/([^#]+)#(\d+)\]\((https?://[^)]+)\)",
        body,
        re.DOTALL,
    )
    if issue_match:
        context["category"] = "issue"
        context["repo_owner"] = issue_match.group(1)
        context["repo_name"] = issue_match.group(2)
        context["mr_number"] = int(issue_match.group(3))
        context["mr_url"] = issue_match.group(4)

        title_match = re.search(r"\*\*Title:\*\* (.+)", body)
        if title_match:
            context["mr_title"] = title_match.group(1).strip()

        platform_match = re.search(r"Platform:\*\* (\w+) \(([^)]+)\)", body)
        if platform_match:
            context["platform"] = platform_match.group(1)
            context["platform_host"] = platform_match.group(2)

        # Issue description: text between "## Issue Description\n**Author:** ...\n\n"
        # and end of body.
        desc_match = re.search(
            r"## Issue Description\n\*\*Author:\*\* [^\n]+\n\n(.*)$",
            body,
            re.DOTALL,
        )
        context["comment_body"] = desc_match.group(1).strip() if desc_match else body

        return context

    # MR-shaped body (existing path).
    # Extract MR URL
    mr_match = re.search(r"\[.*?\]\((https?://[^)]+)\)", body)
    if mr_match:
        context["mr_url"] = mr_match.group(1)

    # Extract branch info
    branch_match = re.search(r"Branch:\*\* (\S+) -> (\S+)", body)
    if branch_match:
        context["head_branch"] = branch_match.group(1)
        context["base_branch"] = branch_match.group(2)

    # Extract platform
    platform_match = re.search(r"Platform:\*\* (\w+) \(([^)]+)\)", body)
    if platform_match:
        context["platform"] = platform_match.group(1)
        context["platform_host"] = platform_match.group(2)

    # Extract dedupe key
    dedupe_match = re.search(r"Dedupe Key:\*\* `([^`]+)`", body)
    if dedupe_match:
        context["dedupe_key"] = dedupe_match.group(1)

    # Extract category
    category_match = re.search(r"Category:\*\* (\w+)", body)
    if category_match:
        context["category"] = category_match.group(1)

    # Extract MR title
    title_match = re.search(r"\*\*Title:\*\* (.+)", body)
    if title_match:
        context["mr_title"] = title_match.group(1).strip()

    # Extract repo_owner / repo_name from MR link (format: [owner/repo!number])
    owner_match = re.search(r"\*\*MR:\*\* \[([^/]+)/([^!]+)!", body)
    if owner_match:
        context["repo_owner"] = owner_match.group(1)
        context["repo_name"] = owner_match.group(2)

    # Extract comment body
    comment_match = re.search(
        r"## Original Comment\n\*\*Author:\*\* [^\n]+\n\n(.*?)\n\n## Metadata",
        body,
        re.DOTALL,
    )
    if comment_match:
        context["comment_body"] = comment_match.group(1).strip()
    else:
        context["comment_body"] = body

    # Extract MR number from dedupe key
    if "dedupe_key" in context:
        parts = context["dedupe_key"].split(":")
        if len(parts) >= 5:
            try:
                context["mr_number"] = int(parts[4])
            except ValueError:
                pass

    return context if "comment_body" in context else None
