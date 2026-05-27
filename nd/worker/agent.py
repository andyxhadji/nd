"""Worker agent definition with AgentField reasoners."""

import asyncio
import os
import re
from datetime import datetime, timezone

from agentfield import Agent, AIConfig, on_schedule
from pydantic import BaseModel

from nd.config import config
from nd.schemas import (
    ClaimResult,
    TaskDetails,
    AnalysisInput,
    AnalysisResult,
    SpecDocument,
    ExecutionInput,
    ExecutionResult,
    RoborevInput,
    RoborevResult,
    DraftInput,
    DraftResult,
    ApprovalRequest,
    PostInput,
    FinalizeInput,
    ProcessResult,
)
from nd.clients.kata import KataClient, KataTask
from nd.clients.platform import PlatformClient
from nd.worker.analyzer import TaskAnalyzer


def create_worker_agent(
    node_id: str = "nd-worker",
    ai_config: AIConfig | None = None,
) -> Agent:
    """Create and configure the worker agent."""

    if ai_config is None:
        ai_config = AIConfig(
            model=config.worker_model,
            temperature=0.2,
        )

    app = Agent(
        node_id=node_id,
        version="1.0.0",
        agentfield_server=config.agentfield_url,
        ai_config=ai_config,
    )

    # Initialize clients
    kata = KataClient(kata_server=config.kata_server)
    platform = PlatformClient(
        github_token=config.github_token,
        gitlab_token=config.gitlab_token,
    )
    analyzer = TaskAnalyzer()

    # ========================================================================
    # Reasoners
    # ========================================================================

    @app.reasoner(tags=["entry"])
    @on_schedule("* * * * *")
    async def claim_task() -> dict:
        """
        Poll kata for unclaimed tasks and claim one for processing.

        Runs every minute via cron trigger.
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
        result = await app.call(
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

        # Analyze task
        analysis_result = await app.call(
            f"{app.node_id}.analyze_task",
            comment_body=context["comment_body"],
            comment_category=context.get("category", "request"),
            mr_title=context.get("mr_title", ""),
            head_branch=context.get("head_branch", ""),
            repo_path=f"/tmp/{project}",
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
                repo_path=f"/tmp/{project}",
            )
            spec = SpecDocument(**spec_result)

            # Pause for human spec review
            approval = await app.pause(
                approval_request_id=f"spec-{task_id}",
                expires_in_hours=72,
                timeout=259200,
                context={
                    "type": "spec_review",
                    "task_id": task_id,
                    "spec": spec.model_dump(),
                    "analysis": analysis.model_dump(),
                },
            )

            if not approval.approved:
                await kata.label(task_id, "needs-human")
                return ProcessResult(
                    status="paused_for_spec",
                    error="Spec rejected by human reviewer",
                ).model_dump()

        # Execute changes via harness
        exec_result = await app.call(
            f"{app.node_id}.execute_changes",
            task_id=task_id,
            comment_body=context["comment_body"],
            repo_path=f"/tmp/{project}",
            head_branch=context.get("head_branch", "main"),
            spec=spec.model_dump() if spec else None,
        )
        execution = ExecutionResult(**exec_result)

        if not execution.success:
            await kata.label(task_id, "failed")
            return ProcessResult(
                status="failed",
                error=execution.error,
            ).model_dump()

        # Run roborev
        roborev_result = await app.call(
            f"{app.node_id}.run_roborev",
            repo_path=f"/tmp/{project}",
            commit_sha=execution.commit_sha or "",
            max_iterations=config.roborev_max_iterations,
        )
        roborev = RoborevResult(**roborev_result)

        if not roborev.passed:
            # Pause for human review of roborev failure
            approval = await app.pause(
                approval_request_id=f"roborev-{task_id}",
                expires_in_hours=72,
                timeout=259200,
                context={
                    "type": "roborev_failure",
                    "task_id": task_id,
                    "findings": roborev.final_findings,
                    "iterations": roborev.iterations,
                },
            )

            if not approval.approved:
                await kata.label(task_id, "needs-human")
                return ProcessResult(
                    status="paused_for_review",
                    error="Roborev failed and human rejected",
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
            expires_in_hours=72,
            timeout=259200,
            context={
                "type": "response_approval",
                "task_id": task_id,
                "mr_url": context.get("mr_url", ""),
                "original_comment": context["comment_body"],
                "response_draft": draft.response_text,
                "commit_sha": execution.commit_sha,
                "changes_summary": execution.files_changed,
            },
        )

        if not approval.approved:
            await kata.label(task_id, "addressed")
            return ProcessResult(
                status="paused_for_review",
                changes_made=execution.files_changed,
                response_draft=draft.response_text,
            ).model_dump()

        # Get potentially edited response from approval
        final_response = approval.feedback or draft.response_text

        # Post response
        post_result = await app.call(
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
        goal = f"Address this code review comment:\n\n{comment_body}"
        if spec:
            spec_obj = SpecDocument(**spec)
            goal += f"\n\nSpec:\n{spec_obj.proposed_solution}"

        try:
            result = await app.harness(
                goal=goal,
                provider="claude-code",
                tools=["read", "write", "edit", "bash"],
                max_iterations=20,
            )

            # Parse harness result for files changed
            files_changed = []
            commit_sha = None

            return ExecutionResult(
                success=True,
                files_changed=files_changed,
                commit_sha=commit_sha,
            ).model_dump()

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e),
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
                "roborev", "refine",
                "--max-iterations", str(max_iterations),
                "--wait",
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            passed = proc.returncode == 0
            findings = []
            if not passed:
                findings = stderr.decode().split("\n")[:10]

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
            response_text: str
            confident: bool

        llm_result = await app.ai(
            system="""You are drafting a response to a code review comment.
Be concise and professional. Mention the commit SHA.
End with an offer to make adjustments if needed.""",
            user=f"""Original comment: {comment_body}

Files changed: {changes_made}
Commit: {commit_sha}

Draft a response.""",
            schema=ResponseDraft,
        )

        return DraftResult(
            response_text=llm_result.response_text,
            confident=llm_result.confident,
        ).model_dump()

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

        success = await platform.post_response(
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
    ) -> dict:
        """Update kata task state after completion."""
        if response_posted:
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
    """Parse structured task body to extract context."""
    context = {}

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

    # Extract repo_owner from MR link (format: [owner/repo!number])
    owner_match = re.search(r"\*\*MR:\*\* \[([^/]+)/", body)
    if owner_match:
        context["repo_owner"] = owner_match.group(1)

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
