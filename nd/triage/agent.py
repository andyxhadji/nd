"""Triage agent definition with AgentField reasoners."""

from datetime import UTC, datetime

from agentfield import Agent, AIConfig
from pydantic import BaseModel

from nd.clients.kata import KataClient
from nd.clients.middleman import Issue, MiddlemanClient
from nd.config import config
from nd.schemas import (
    ClassificationResult,
    CommentInput,
    IssuePollResult,
    IssueTaskInput,
    PollResult,
    TaskCreationResult,
    TaskInput,
)
from nd.triage.classifier import CommentClassifier


def create_triage_agent(
    node_id: str = "nd-triage",
    ai_config: AIConfig | None = None,
) -> Agent:
    """Create and configure the triage agent."""

    if ai_config is None:
        ai_config = AIConfig(
            model=config.triage_model,
        )

    app = Agent(
        node_id=node_id,
        version="1.0.0",
        agentfield_server=config.agentfield_url,
        ai_config=ai_config,
    )

    # Initialize clients
    middleman = MiddlemanClient(base_url=config.middleman_url)
    kata = KataClient(kata_server=config.kata_server)
    classifier = CommentClassifier()

    @app.on_event("shutdown")
    async def _close_clients() -> None:
        """Close httpx connection pools on agent shutdown."""
        await middleman.close()

    # ========================================================================
    # Reasoners
    # ========================================================================

    @app.reasoner(tags=["entry"])
    # @on_schedule("*/5 * * * *")  # Disabled - trigger manually
    async def poll_comments(payload: dict | None = None) -> dict:
        """
        Poll middleman for new MR comments and create tasks for actionable ones.

        Triggered manually (cron decorator disabled). The `payload` parameter
        accepts the cron event ({expression, fired_at, timezone}) that
        AgentField passes as a single positional argument when triggered via
        cron; it is unused.

        Note: parameter is intentionally NOT named `trigger` or `webhook` —
        AgentField auto-injects those names as kwargs (agent.py:2202-2205),
        which collides with the positional payload from cron triggers.
        """
        # Get last poll timestamp from memory (if available)
        last_poll_str = None
        if app.memory is not None:
            last_poll_str = await app.memory.get("last_poll_timestamp")

        if last_poll_str:
            last_poll = datetime.fromisoformat(last_poll_str)
        else:
            # Default to 24 hours ago on first run
            last_poll = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

        # Fetch comments
        try:
            comments = await middleman.get_comments_since(
                since=last_poll,
                current_users=config.current_users,
            )
        except Exception as e:
            return PollResult(
                comments_found=0,
                tasks_created=0,
                skipped=0,
                errors=[f"Middleman error: {e}"],
            ).model_dump()

        # Classify and create tasks
        tasks_created = 0
        skipped = 0
        errors: list[str] = []

        for comment in comments:
            comment_input = CommentInput(
                body=comment.body,
                author=comment.author,
                mr_title=comment.mr_title,
                mr_number=comment.mr_number,
            )

            # Classify
            classification = await app.call(
                f"{app.node_id}.classify_actionable",
                **comment_input.model_dump(),
            )
            classification = ClassificationResult(**classification)

            if not classification.actionable:
                skipped += 1
                continue

            # Create task
            task_input = TaskInput(
                comment_body=comment.body,
                comment_author=comment.author,
                comment_dedupe_key=comment.dedupe_key,
                mr_number=comment.mr_number,
                mr_title=comment.mr_title,
                mr_url=comment.mr_url,
                head_branch=comment.head_branch,
                base_branch=comment.base_branch,
                platform=comment.platform,
                platform_host=comment.platform_host,
                repo_owner=comment.repo_owner,
                repo_name=comment.repo_name,
                classification=classification,
            )

            result = await app.call(
                f"{app.node_id}.create_task",
                **task_input.model_dump(),
            )
            result = TaskCreationResult(**result)

            if result.created:
                tasks_created += 1
            else:
                if result.skipped_reason != "duplicate":
                    errors.append(f"Failed to create task: {result.skipped_reason}")

        # Update last poll timestamp (only if memory is available)
        if app.memory is not None:
            await app.memory.set(
                "last_poll_timestamp",
                datetime.now(UTC).isoformat(),
            )

        return PollResult(
            comments_found=len(comments),
            tasks_created=tasks_created,
            skipped=skipped,
            errors=errors,
        ).model_dump()

    @app.reasoner()
    async def classify_actionable(
        body: str,
        author: str,
        mr_title: str,
        mr_number: int,
    ) -> dict:
        """Classify whether a comment requires action."""
        comment = CommentInput(
            body=body,
            author=author,
            mr_title=mr_title,
            mr_number=mr_number,
        )

        # Try deterministic classification first
        result = classifier.classify_deterministic(comment)
        if result is not None:
            return result.model_dump()

        # Fall back to LLM classification
        class LLMClassification(BaseModel):
            actionable: bool
            reason: str
            category: str
            confident: bool

        llm_result = await app.ai(
            system="""You classify MR comments as actionable or not.

Actionable comments include:
- Questions directed at the MR author
- Explicit requests to change, fix, add, or remove something
- Review feedback (nit, suggestion, blocking)

Non-actionable comments include:
- Acknowledgments (LGTM, looks good, +1)
- Thanks/gratitude
- Off-topic discussion

Respond with:
- actionable: true/false
- reason: brief explanation
- category: one of "question", "request", "feedback", "acknowledgment", "other"
- confident: true if certain, false if ambiguous""",
            user=f"MR: {mr_title}\n\nComment by {author}:\n{body}",
            schema=LLMClassification,
        )

        return ClassificationResult(
            actionable=llm_result.actionable,
            reason=llm_result.reason,
            category=llm_result.category
            if llm_result.category
            in ("question", "request", "feedback", "acknowledgment", "bot", "other")
            else "other",
            confident=llm_result.confident,
        ).model_dump()

    @app.reasoner()
    async def create_task(
        comment_body: str,
        comment_author: str,
        comment_dedupe_key: str,
        mr_number: int,
        mr_title: str,
        mr_url: str,
        head_branch: str,
        base_branch: str,
        platform: str,
        platform_host: str,
        repo_owner: str,
        repo_name: str,
        classification: dict,
    ) -> dict:
        """Create a kata task for an actionable comment."""
        classification_obj = ClassificationResult(**classification)

        # Check for duplicate
        existing = await kata.search(repo_name, comment_dedupe_key)
        if existing:
            return TaskCreationResult(
                created=False,
                skipped_reason="duplicate",
            ).model_dump()

        # Build task
        title = comment_body.split(".")[0][:80]  # First sentence, max 80 chars
        body = KataClient.build_task_body(
            mr_url=mr_url,
            mr_title=mr_title,
            head_branch=head_branch,
            base_branch=base_branch,
            platform=platform,
            platform_host=platform_host,
            repo_owner=repo_owner,
            repo_name=repo_name,
            mr_number=mr_number,
            comment_author=comment_author,
            comment_body=comment_body,
            dedupe_key=comment_dedupe_key,
            category=classification_obj.category,
        )

        # Create task
        task_id = await kata.create(
            title=title,
            body=body,
            project=repo_name,
            labels=["from-mr", "nd"],
            idempotency_key=comment_dedupe_key,
        )

        if task_id:
            return TaskCreationResult(created=True, task_id=task_id).model_dump()
        else:
            return TaskCreationResult(
                created=False,
                skipped_reason="kata create failed",
            ).model_dump()

    @app.reasoner(tags=["entry"])
    async def poll_issues(payload: dict | None = None) -> dict:
        """
        Poll middleman for open issues assigned to configured usernames
        and create tasks for each.

        Triggered manually. The `payload` parameter accepts the cron event
        that AgentField passes as a single positional argument when triggered
        via cron; it is unused. Parameter is intentionally NOT named `trigger`
        or `webhook` (those names are auto-injected as kwargs by AgentField).
        """
        if not config.assigned_usernames:
            return IssuePollResult(
                issues_found=0,
                tasks_created=0,
                skipped=0,
                errors=["No assigned_usernames configured"],
            ).model_dump()

        all_issues: list[Issue] = []
        errors: list[str] = []

        # Fetch issues for each configured username
        for username in config.assigned_usernames:
            try:
                issues = await middleman.get_issues_assigned_to(username)
                all_issues.extend(issues)
            except Exception as e:
                errors.append(f"Middleman error for {username}: {e}")

        # Deduplicate by issue URL (same issue may be assigned to multiple users)
        seen_urls: set[str] = set()
        unique_issues: list[Issue] = []
        for issue in all_issues:
            if issue.url not in seen_urls:
                seen_urls.add(issue.url)
                unique_issues.append(issue)

        # Create tasks for each issue
        tasks_created = 0
        skipped = 0

        for issue in unique_issues:
            task_input = IssueTaskInput(
                issue_number=issue.number,
                issue_title=issue.title,
                issue_body=issue.body,
                issue_url=issue.url,
                issue_author=issue.author,
                assignees=issue.assignees,
                platform=issue.platform,
                platform_host=issue.platform_host,
                repo_owner=issue.repo_owner,
                repo_name=issue.repo_name,
            )

            result = await app.call(
                f"{app.node_id}.create_issue_task",
                **task_input.model_dump(),
            )
            result = TaskCreationResult(**result)

            if result.created:
                tasks_created += 1
            else:
                skipped += 1

        return IssuePollResult(
            issues_found=len(unique_issues),
            tasks_created=tasks_created,
            skipped=skipped,
            errors=errors,
        ).model_dump()

    @app.reasoner()
    async def create_issue_task(
        issue_number: int,
        issue_title: str,
        issue_body: str,
        issue_url: str,
        issue_author: str,
        assignees: list[str],
        platform: str,
        platform_host: str,
        repo_owner: str,
        repo_name: str,
    ) -> dict:
        """Create a kata task for an issue."""
        # Use issue URL as idempotency key
        idempotency_key = f"issue:{issue_url}"

        # Check for duplicate
        existing = await kata.search(repo_name, idempotency_key)
        if existing:
            return TaskCreationResult(
                created=False,
                skipped_reason="duplicate",
            ).model_dump()

        # Build task
        title = issue_title[:80]
        body = KataClient.build_issue_task_body(
            issue_url=issue_url,
            issue_title=issue_title,
            issue_number=issue_number,
            platform=platform,
            platform_host=platform_host,
            repo_owner=repo_owner,
            repo_name=repo_name,
            issue_author=issue_author,
            issue_body=issue_body,
            assignees=assignees,
        )

        # Create task
        task_id = await kata.create(
            title=title,
            body=body,
            project=repo_name,
            labels=["from-issue", "nd"],
            idempotency_key=idempotency_key,
        )

        if task_id:
            return TaskCreationResult(created=True, task_id=task_id).model_dump()
        else:
            return TaskCreationResult(
                created=False,
                skipped_reason="kata create failed",
            ).model_dump()

    return app
