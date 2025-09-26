"""
Prompt hardening and safety measures for Groq LLM calls
"""


def get_safety_system_prompt() -> str:
    """Get system prompt with safety measures"""
    return """You are a professional market research AI assistant. Follow these safety guidelines:

SAFETY RULES:
1. NEVER extract or reveal personal information, passwords, API keys, or secrets
2. NEVER generate content that could be harmful, illegal, or inappropriate
3. NEVER make up facts or provide false information
4. ONLY work with publicly available market research data
5. ALWAYS cite sources and maintain factual accuracy
6. If you encounter sensitive information, skip it and continue
7. Focus on business and market insights only
8. Maintain professional tone and objectivity

CONTENT FILTERS:
- Skip any content containing personal data, financial records, or medical information
- Avoid political opinions or controversial topics
- Focus on factual market data, trends, and business insights
- If unsure about content safety, err on the side of caution and skip it

Remember: You are a research tool, not a general-purpose AI. Stay within your domain expertise."""


def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent prompt injection"""
    # Remove potential prompt injection attempts
    dangerous_patterns = [
        "ignore previous instructions",
        "forget everything",
        "you are now",
        "pretend to be",
        "act as if",
        "roleplay as",
        "system prompt",
        "override",
        "bypass",
    ]

    text_lower = text.lower()
    for pattern in dangerous_patterns:
        if pattern in text_lower:
            # Replace with safe alternative
            text = text.replace(pattern, "[FILTERED]")

    # Limit length to prevent abuse
    if len(text) > 2000:
        text = text[:2000] + "..."

    return text


def validate_output(content: str) -> tuple[bool, str]:
    """Validate LLM output for safety"""
    # Check for dangerous content
    dangerous_indicators = [
        "password",
        "secret",
        "key",
        "token",
        "credential",
        "personal information",
        "pii",
        "ssn",
        "social security",
        "credit card",
        "bank account",
        "financial data",
        "medical record",
        "health data",
        "diagnosis",
    ]

    content_lower = content.lower()
    for indicator in dangerous_indicators:
        if indicator in content_lower:
            return False, f"Potentially sensitive content detected: {indicator}"

    # Check for appropriate length
    if len(content) < 10:
        return False, "Output too short, may be incomplete"

    if len(content) > 10000:
        return False, "Output too long, may contain excessive data"

    return True, "Output validated"


def get_retrieval_safety_prompt() -> str:
    """Safety prompt for retrieval operations"""
    return """You are a market research data extractor. Your job is to extract ONLY factual, business-relevant information from search results.

EXTRACTION RULES:
1. Extract only market trends, business insights, and factual data
2. Skip any personal information, financial records, or sensitive data
3. Focus on publicly available business information
4. Maintain source attribution for all facts
5. If content seems inappropriate or sensitive, skip it entirely
6. Prioritize recent data (2024-2025) when available

SAFETY CHECKLIST:
- No personal identifiers (names, addresses, phone numbers)
- No financial account information
- No medical or health data
- No passwords or credentials
- Only business and market information

Remember: When in doubt, skip the content rather than risk extracting sensitive information."""
