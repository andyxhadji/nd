"""Mock LLM service for E2E testing without API keys.

This module provides deterministic responses for app.ai() calls based on
simple heuristics, allowing full agent workflow testing without LLM API costs.
"""

import re


class MockLLMService:
    """Mock LLM that returns deterministic responses based on input patterns."""

    @staticmethod
    def classify_comment(body: str, author: str = "") -> dict:
        """Mock triage classification.

        Mimics nd/triage/classifier.py deterministic logic with LLM-style output.
        """
        body_lower = body.lower().strip()

        # Bot detection
        bot_patterns = [r".*\[bot\]$", r"^dependabot$", r"^renovate$"]
        if any(re.match(pattern, author.lower()) for pattern in bot_patterns):
            return {
                "actionable": False,
                "category": "bot",
                "reason": "Comment from automated bot",
                "confident": True,
            }

        # Exact non-actionable matches
        non_actionable = {
            "lgtm",
            "looks good",
            "looks good!",
            "looks good to me",
            "approved",
            "+1",
            "thanks",
            "thank you",
            "thanks!",
            "thank you!",
            "nice",
            "nice!",
            "great",
            "great!",
        }
        if body_lower in non_actionable:
            return {
                "actionable": False,
                "category": "acknowledgment",
                "reason": f"Standard acknowledgment: '{body_lower}'",
                "confident": True,
            }

        # Actionable patterns
        if re.search(r"\?", body):
            return {
                "actionable": True,
                "category": "question",
                "reason": "Contains question mark",
                "confident": True,
            }

        actionable_keywords = [
            "please",
            "can you",
            "could you",
            "fix",
            "change",
            "update",
            "add",
            "remove",
            "refactor",
        ]
        if any(kw in body_lower for kw in actionable_keywords):
            return {
                "actionable": True,
                "category": "request",
                "reason": "Contains action request keyword",
                "confident": True,
            }

        # Explicit review markers
        review_markers = ["nit:", "suggestion:", "todo:", "blocking:"]
        if any(body_lower.startswith(marker) for marker in review_markers):
            return {
                "actionable": True,
                "category": "review",
                "reason": "Explicit review feedback marker",
                "confident": True,
            }

        # Default: uncertain, lean toward actionable if not empty
        if len(body.strip()) > 5:
            return {
                "actionable": True,
                "category": "feedback",
                "reason": "Substantive comment, likely actionable",
                "confident": False,
            }

        return {
            "actionable": False,
            "category": "comment",
            "reason": "Short or unclear comment",
            "confident": False,
        }

    @staticmethod
    def analyze_complexity(body: str) -> dict:
        """Mock worker complexity analysis.

        Mimics nd/worker/analyzer.py heuristic scoring with LLM-style output.
        """
        score = 30  # Base score
        body_lower = body.lower()

        # Keyword-based scoring
        simple_keywords = ["log", "typo", "rename", "comment"]
        medium_keywords = ["fix", "update", "change", "add", "remove"]
        complex_keywords = [
            "refactor",
            "implement",
            "design",
            "architecture",
            "performance",
            "optimization",
            "migration",
            "database",
        ]

        if any(kw in body_lower for kw in simple_keywords):
            score = min(score, 25)
        if any(kw in body_lower for kw in medium_keywords):
            score = max(score, 50)
        if any(kw in body_lower for kw in complex_keywords):
            score = max(score, 75)

        # Length-based adjustment
        word_count = len(body.split())
        if word_count < 10:
            score = min(score, 30)
        elif word_count > 50:
            score = max(score, 60)

        # Multiple files/scopes indicator
        if re.search(r"\band\b.*\band\b", body_lower) or body_lower.count(",") > 2:
            score = min(score + 15, 100)

        # Determine reasoning
        if score <= 30:
            reasoning = "Simple change - likely a quick fix or small update"
        elif score <= 50:
            reasoning = "Moderate complexity - standard feature or bug fix"
        elif score <= 70:
            reasoning = "Significant change - requires careful implementation"
        else:
            reasoning = "Complex task - involves multiple components or design decisions"

        return {
            "complexity": score,
            "reasoning": reasoning,
        }

    @staticmethod
    def plan_changes(task_body: str, mr_context: dict = None) -> dict:
        """Mock worker planning.

        Returns a simple implementation plan based on task content.
        """
        body_lower = task_body.lower()
        steps = []

        # Detect task type and generate appropriate plan
        if "test" in body_lower:
            steps = [
                "Review existing test coverage",
                "Identify test cases to add",
                "Implement new tests",
                "Verify tests pass",
            ]
        elif "fix" in body_lower or "bug" in body_lower:
            steps = [
                "Reproduce the issue",
                "Identify root cause",
                "Implement fix",
                "Add regression test",
                "Verify fix works",
            ]
        elif "refactor" in body_lower:
            steps = [
                "Analyze current implementation",
                "Design improved structure",
                "Refactor incrementally",
                "Ensure tests still pass",
            ]
        elif "add" in body_lower or "implement" in body_lower:
            steps = [
                "Review requirements",
                "Design solution approach",
                "Implement core functionality",
                "Add tests",
                "Update documentation if needed",
            ]
        else:
            # Generic plan
            steps = [
                "Understand the request",
                "Identify files to modify",
                "Make necessary changes",
                "Test the changes",
            ]

        return {
            "plan": "\n".join(f"{i + 1}. {step}" for i, step in enumerate(steps)),
            "estimated_files": 2 if "simple" in body_lower else 3,
            "approach": "incremental" if len(steps) > 3 else "direct",
        }

    @staticmethod
    def draft_response(task_body: str, outcome: str, commit_sha: str = None) -> dict:
        """Mock worker response drafting.

        Creates a simple response based on task outcome.
        """
        # Extract task summary
        first_line = task_body.split("\n")[0][:100]

        if outcome == "success":
            response = f"I've completed the requested changes: {first_line}\n\n"
            if commit_sha:
                response += f"Changes are in commit {commit_sha[:7]}.\n\n"
            response += "Please review when you have a chance."
        elif outcome == "needs_review":
            response = f"I've analyzed this request: {first_line}\n\n"
            response += "Before proceeding, I'd like to confirm the approach. "
            response += "Please let me know if this looks good."
        else:
            response = f"I encountered an issue with: {first_line}\n\n"
            response += "Could you provide more details or clarify the requirements?"

        return {
            "response": response,
            "tone": "professional",
        }

    @classmethod
    def handle_ai_call(cls, system: str, user: str, **kwargs) -> dict:
        """Main dispatcher for app.ai() calls.

        Routes to appropriate mock method based on system prompt patterns.
        """
        system_lower = system.lower()

        # Triage classification
        if "classify" in system_lower and "actionable" in system_lower:
            # Extract comment body from user prompt
            # Typically: "Body: <text>\nAuthor: <name>"
            body = user
            author = ""
            if "Author:" in user:
                parts = user.split("Author:")
                body = parts[0].replace("Body:", "").strip()
                author = parts[1].strip()

            return cls.classify_comment(body, author)

        # Worker complexity analysis
        if "complexity" in system_lower or "estimate" in system_lower:
            return cls.analyze_complexity(user)

        # Worker planning
        if "plan" in system_lower or "implementation" in system_lower:
            return cls.plan_changes(user)

        # Worker response drafting
        if "draft" in system_lower or "response" in system_lower:
            outcome = "success"  # Default
            commit_sha = None
            if "commit" in user.lower():
                # Try to extract commit SHA from user prompt
                import re

                match = re.search(r"[0-9a-f]{7,40}", user)
                if match:
                    commit_sha = match.group(0)
            return cls.draft_response(user, outcome, commit_sha)

        # Fallback: return generic successful response
        return {
            "result": "mock response",
            "status": "success",
        }
