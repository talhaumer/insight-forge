import os
import time
from typing import List, Dict, Any, Optional
from groq import Groq
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from ..guardrails.prompt_hardening import (
    get_safety_system_prompt,
    sanitize_input,
    validate_output,
    get_retrieval_safety_prompt,
)
from ..observability import metrics_collector
from dotenv import load_dotenv

load_dotenv()


def get_groq_client() -> Optional[ChatGroq]:
    """Get Groq LLM client"""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    return ChatGroq(
        groq_api_key=api_key,
        model_name="llama-3.3-70b-versatile",
        temperature=0.1,
        max_tokens=2048,
    )


def groq_llm_call(
    messages: List[Dict[str, str]], max_retries: int = 2, system_prompt: str = ""
) -> Dict[str, Any]:
    """Make Groq LLM call with retry logic and metrics collection"""
    client = get_groq_client()
    if not client:
        metrics_collector.record_tool_call("groq_llm", 0, success=False)
        return {
            "content": "Groq API key not configured",
            "success": False,
            "error": "Missing GROQ_API_KEY",
        }

    start_time = time.time()

    for attempt in range(max_retries + 1):
        try:
            # Prepare messages
            langchain_messages = []
            if system_prompt:
                langchain_messages.append(SystemMessage(content=system_prompt))

            for msg in messages:
                if msg["role"] == "user":
                    langchain_messages.append(HumanMessage(content=msg["content"]))

            # Make API call
            response = client.invoke(langchain_messages)

            # Record successful call metrics
            latency = time.time() - start_time
            metrics_collector.record_tool_call("groq_llm", latency, success=True)

            # Estimate token usage (rough approximation)
            total_chars = sum(len(msg["content"]) for msg in messages)
            estimated_tokens = total_chars // 4  # Rough estimate: 4 chars per token
            metrics_collector.record_token_usage(estimated_tokens, estimated_tokens)

            return {"content": response.content, "success": True, "error": None}

        except Exception as e:
            if attempt < max_retries:
                # Exponential backoff
                time.sleep(2**attempt)
                continue
            else:
                # Record failed call metrics
                latency = time.time() - start_time
                metrics_collector.record_tool_call("groq_llm", latency, success=False)
                return {
                    "content": f"Groq API call failed: {str(e)}",
                    "success": False,
                    "error": str(e),
                }


def extract_facts_with_groq(
    query: str, search_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Use Groq LLM to extract structured facts from search results"""

    # Sanitize input
    query = sanitize_input(query)

    # Get safety-hardened system prompt
    system_prompt = (
        get_retrieval_safety_prompt()
        + """

EXTRACTION FORMAT:
Return facts in this JSON format:
{
    "facts": [
        {
            "fact": "specific factual statement",
            "source": "source_url",
            "confidence": 0.8
        }
    ],
    "sources": ["url1", "url2"],
    "needs_more_context": false
}"""
    )

    # Prepare search results context (sanitized)
    context = f"Query: {query}\n\nSearch Results:\n"
    for i, result in enumerate(search_results[:5]):  # Limit to top 5 results
        title = sanitize_input(str(result.get("title", "N/A")))
        url = result.get("url", "N/A")
        content = sanitize_input(str(result.get("content", "N/A"))[:500])

        context += f"Result {i+1}:\n"
        context += f"Title: {title}\n"
        context += f"URL: {url}\n"
        context += f"Content: {content}...\n\n"

    messages = [{"role": "user", "content": context}]

    result = groq_llm_call(messages, system_prompt=system_prompt)

    # Validate output for safety
    if result["success"]:
        is_safe, safety_msg = validate_output(result["content"])
        if not is_safe:
            result["success"] = False
            result["error"] = f"Safety validation failed: {safety_msg}"

    return result


def analyze_facts_with_groq(facts: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    """Use Groq LLM to analyze and validate facts"""

    # Sanitize input
    query = sanitize_input(query)

    system_prompt = (
        get_safety_system_prompt()
        + """

ANALYSIS TASK:
Analyze the provided facts and validate them for quality and policy compliance.

ANALYSIS RULES:
1. Validate each fact for accuracy and relevance
2. Check for policy violations (no personal data, secrets, etc.)
3. Assess overall data quality
4. Identify if more context is needed
5. Flag any suspicious or inappropriate content

Return analysis in this JSON format:
{
    "analysis": "brief analysis of the facts",
    "quality_score": 0.8,
    "violations": [],
    "needs_more_context": false,
    "recommendations": ["suggestion1", "suggestion2"]
}"""
    )

    # Sanitize facts context
    facts_context = f"Query: {query}\n\nFacts to analyze:\n"
    for i, fact in enumerate(facts):
        fact_text = sanitize_input(str(fact.get("fact", "")))
        source = fact.get("source", "N/A")
        confidence = fact.get("confidence", 0)
        facts_context += (
            f"{i+1}. {fact_text} (Source: {source}, Confidence: {confidence})\n"
        )

    messages = [{"role": "user", "content": facts_context}]

    result = groq_llm_call(messages, system_prompt=system_prompt)

    # Validate output for safety
    if result["success"]:
        is_safe, safety_msg = validate_output(result["content"])
        if not is_safe:
            result["success"] = False
            result["error"] = f"Safety validation failed: {safety_msg}"

    return result


def generate_report_with_groq(
    query: str,
    facts: List[Dict[str, Any]],
    sources: List[str],
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """Use Groq LLM to generate final research report"""

    # Sanitize input
    query = sanitize_input(query)

    system_prompt = (
        get_safety_system_prompt()
        + """

REPORT GENERATION TASK:
Generate a comprehensive research report based on the provided facts and analysis.

REPORT RULES:
1. Write a professional, objective report
2. Include all relevant facts with proper citations
3. Structure the report logically
4. Use clear, business-appropriate language
5. Include proper references to sources
6. Ensure the report is comprehensive but concise
7. Do not include personal opinions or speculation
8. Focus on actionable insights
9. Maintain factual accuracy and source attribution

Return report in this JSON format:
{
    "topic": "original query",
    "summary": "comprehensive research summary",
    "references": ["url1", "url2"],
    "timestamp": "ISO8601 timestamp",
    "key_insights": ["insight1", "insight2"],
    "recommendations": ["rec1", "rec2"]
}"""
    )

    # Prepare context (sanitized)
    context = f"Research Query: {query}\n\n"
    context += f"Analysis: {sanitize_input(str(analysis.get('analysis', 'N/A')))}\n\n"
    context += f"Quality Score: {analysis.get('quality_score', 'N/A')}\n\n"
    context += "Facts:\n"
    for i, fact in enumerate(facts):
        fact_text = sanitize_input(str(fact.get("fact", "")))
        source = fact.get("source", "N/A")
        context += f"{i+1}. {fact_text} (Source: {source})\n"

    messages = [{"role": "user", "content": context}]

    result = groq_llm_call(messages, system_prompt=system_prompt)

    # Validate output for safety
    if result["success"]:
        is_safe, safety_msg = validate_output(result["content"])
        if not is_safe:
            result["success"] = False
            result["error"] = f"Safety validation failed: {safety_msg}"

    return result
