"""Task complexity analysis logic."""

import re
from nd.schemas import AnalysisInput, AnalysisResult


# Complexity indicators
TRIVIAL_PATTERNS = [
    r"\btypo\b",
    r"\bspelling\b",
    r"\bcomment\b",
    r"\bdocstring\b",
    r"\brename\b",
]

MINOR_PATTERNS = [
    r"\blogging\b",
    r"\blog\b",
    r"\berror.?message\b",
    r"\bvalidat",
]

MODERATE_PATTERNS = [
    r"\bfunction\b",
    r"\bmethod\b",
    r"\btest\b",
    r"\brefactor\b",
]

SIGNIFICANT_PATTERNS = [
    r"\bfeature\b",
    r"\barchitect",
    r"\bmultiple.?files\b",
    r"\bapi\b",
]

MAJOR_PATTERNS = [
    r"\bdatabase\b",
    r"\bmigrat",
    r"\bbreaking\b",
    r"\bdesign\b",
    r"\bsecurity\b",
]

# File path pattern
FILE_PATH_PATTERN = re.compile(r"[\w./]+\.\w{1,5}")


class TaskAnalyzer:
    """Analyzes task complexity and confidence."""

    def _estimate_complexity(self, comment: str) -> int:
        """
        Estimate task complexity from comment text.

        Returns 1-5 where:
        1 = trivial (typo, comment)
        2 = minor (logging, error message)
        3 = moderate (new function, refactor)
        4 = significant (new feature, multi-file)
        5 = major (architecture, breaking change)
        """
        comment_lower = comment.lower()

        # Check patterns in order of complexity
        for pattern in MAJOR_PATTERNS:
            if re.search(pattern, comment_lower):
                return 5

        for pattern in SIGNIFICANT_PATTERNS:
            if re.search(pattern, comment_lower):
                return 4

        for pattern in MODERATE_PATTERNS:
            if re.search(pattern, comment_lower):
                return 3

        for pattern in MINOR_PATTERNS:
            if re.search(pattern, comment_lower):
                return 2

        for pattern in TRIVIAL_PATTERNS:
            if re.search(pattern, comment_lower):
                return 1

        # Default to moderate if no patterns match
        return 3

    def _extract_likely_files(self, comment: str) -> list[str]:
        """Extract file paths mentioned in the comment."""
        matches = FILE_PATH_PATTERN.findall(comment)
        # Filter out common false positives
        return [
            m for m in matches
            if not m.startswith("http")
            and not m.endswith((".com", ".org", ".io"))
        ]

    def _estimate_confidence(
        self,
        comment: str,
        category: str,
        complexity: int,
        has_file_refs: bool,
    ) -> int:
        """
        Estimate confidence level (0-100).

        Higher confidence when:
        - Comment is explicit and specific
        - File references are provided
        - Complexity is low
        - Category is "request" (explicit action)
        """
        confidence = 70  # Base confidence

        # Adjust for category
        if category == "request":
            confidence += 10
        elif category == "question":
            confidence -= 10
        elif category == "feedback":
            confidence += 5

        # Adjust for complexity
        if complexity <= 2:
            confidence += 15
        elif complexity >= 4:
            confidence -= 20

        # Adjust for file references
        if has_file_refs:
            confidence += 10

        # Adjust for comment clarity
        if "?" in comment:
            confidence -= 5  # Questions reduce confidence
        if len(comment) > 500:
            confidence -= 10  # Long comments often ambiguous

        # Clamp to 0-100
        return max(0, min(100, confidence))

    def analyze_deterministic(self, input_data: AnalysisInput) -> AnalysisResult:
        """
        Perform deterministic analysis of task complexity.

        This provides initial estimates that can be refined by LLM.
        """
        complexity = self._estimate_complexity(input_data.comment_body)
        files = self._extract_likely_files(input_data.comment_body)
        confidence = self._estimate_confidence(
            comment=input_data.comment_body,
            category=input_data.comment_category,
            complexity=complexity,
            has_file_refs=bool(files),
        )

        return AnalysisResult(
            complexity=complexity,
            confidence=confidence,
            reasoning=f"Estimated complexity {complexity}/5 based on keyword analysis",
            suggested_approach="",  # Will be filled by LLM
            files_likely_affected=files,
            confident=confidence >= 70,
        )
