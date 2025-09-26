import re
from typing import List

# Simple keyword-based moderation
BANNED_PATTERNS = [
    r"\bpassword\b|\bsecret\b|\btoken\b",
    r"\bpersonal\s+information\b|\bpii\b",
    r"\bfinancial\s+data\b|\bcredit\s+card\b",
    r"\bmedical\s+record\b|\bhealth\s+data\b",
]


def check_content(content: str) -> List[str]:
    """Check content for policy violations"""
    violations = []
    content_lower = content.lower()

    for pattern in BANNED_PATTERNS:
        if re.search(pattern, content_lower):
            violations.append(f"Potential violation: {pattern}")

    return violations


def is_safe_content(content: str) -> bool:
    """Simple safety check"""
    violations = check_content(content)
    return len(violations) == 0
