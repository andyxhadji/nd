"""Comment classification logic."""

import re

from nd.schemas import ClassificationResult, CommentInput

# Known bot patterns
BOT_PATTERNS = [
    r".*\[bot\]$",
    r"^dependabot$",
    r"^renovate$",
    r"^github-actions$",
    r"^gitlab-bot$",
]

# Deterministic actionable patterns
ACTIONABLE_PATTERNS = [
    r"\?",  # Questions
    r"\bplease\b",
    r"\bcan you\b",
    r"\bcould you\b",
    r"\bfix\b",
    r"\bchange\b",
    r"\bupdate\b",
    r"\badd\b",
    r"\bremove\b",
    r"^nit:",
    r"^suggestion:",
    r"^todo:",
    r"^blocking:",
]

# Deterministic non-actionable patterns (exact or near-exact)
NON_ACTIONABLE_EXACT = {
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


class CommentClassifier:
    """Classifies MR comments as actionable or not."""

    def _is_bot(self, author: str) -> bool:
        """Check if author is a known bot."""
        author_lower = author.lower()
        for pattern in BOT_PATTERNS:
            if re.match(pattern, author_lower):
                return True
        return False

    def _is_non_actionable(self, body: str) -> bool:
        """Check if body matches non-actionable patterns."""
        normalized = body.strip().lower()
        return normalized in NON_ACTIONABLE_EXACT

    def _matches_actionable_pattern(self, body: str) -> bool:
        """Check if body matches actionable patterns."""
        body_lower = body.lower()
        for pattern in ACTIONABLE_PATTERNS:
            if re.search(pattern, body_lower):
                return True
        return False

    def classify_deterministic(self, comment: CommentInput) -> ClassificationResult | None:
        """
        Attempt deterministic classification.

        Returns ClassificationResult if deterministic rules match,
        None if LLM classification is needed.
        """
        # Check bot first
        if self._is_bot(comment.author):
            return ClassificationResult(
                actionable=False,
                reason=f"Author '{comment.author}' is a known bot",
                category="bot",
                confident=True,
            )

        # Check non-actionable patterns
        if self._is_non_actionable(comment.body):
            return ClassificationResult(
                actionable=False,
                reason="Comment matches non-actionable pattern",
                category="acknowledgment",
                confident=True,
            )

        # Check actionable patterns
        if self._matches_actionable_pattern(comment.body):
            # Determine category based on pattern
            body_lower = comment.body.lower()
            if any(p in body_lower for p in ["nit:", "suggestion:"]):
                category = "feedback"
            elif any(
                p in body_lower
                for p in [
                    "can you",
                    "could you",
                    "please",
                    "fix",
                    "change",
                    "update",
                    "add",
                    "remove",
                ]
            ):
                category = "request"
            elif "?" in comment.body:
                category = "question"
            else:
                category = "request"

            return ClassificationResult(
                actionable=True,
                reason="Comment matches actionable pattern",
                category=category,
                confident=True,
            )

        # No deterministic match - needs LLM
        return None
