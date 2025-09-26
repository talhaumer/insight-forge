"""
Observability and tracing module for LangSmith integration
"""

import os
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from langsmith import Client
from langsmith.wrappers import wrap_openai
from langchain_core.tracers import LangChainTracer
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.messages import BaseMessage
from dotenv import load_dotenv

load_dotenv()


class MetricsCollector:
    """Collect metrics during workflow execution"""

    def __init__(self):
        self.metrics = {
            "token_usage": {
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "groq_calls": 0,
            },
            "tool_latency": {
                "tavily_search": [],
                "groq_llm": [],
                "retriever": [],
                "total_time": 0,
            },
            "failures": {
                "tool_errors": 0,
                "schema_violations": 0,
                "policy_violations": 0,
                "fallback_usage": 0,
            },
            "workflow_stats": {
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "avg_execution_time": 0,
            },
        }
        self.start_time = None
        self.current_run_id = None

    def start_run(self, run_id: str):
        """Start tracking a new run"""
        self.current_run_id = run_id
        self.start_time = time.time()
        self.metrics["workflow_stats"]["total_runs"] += 1

    def end_run(self, success: bool = True):
        """End current run tracking"""
        if self.start_time:
            execution_time = time.time() - self.start_time
            self.metrics["tool_latency"]["total_time"] = execution_time

            if success:
                self.metrics["workflow_stats"]["successful_runs"] += 1
            else:
                self.metrics["workflow_stats"]["failed_runs"] += 1

            # Update average execution time
            total_runs = self.metrics["workflow_stats"]["total_runs"]
            current_avg = self.metrics["workflow_stats"]["avg_execution_time"]
            self.metrics["workflow_stats"]["avg_execution_time"] = (
                current_avg * (total_runs - 1) + execution_time
            ) / total_runs

    def record_tool_call(self, tool_name: str, latency: float, success: bool = True):
        """Record tool call metrics"""
        if tool_name in self.metrics["tool_latency"]:
            self.metrics["tool_latency"][tool_name].append(latency)

        if not success:
            self.metrics["failures"]["tool_errors"] += 1

    def record_token_usage(self, prompt_tokens: int, completion_tokens: int):
        """Record token usage"""
        self.metrics["token_usage"]["prompt_tokens"] += prompt_tokens
        self.metrics["token_usage"]["completion_tokens"] += completion_tokens
        self.metrics["token_usage"]["total_tokens"] += prompt_tokens + completion_tokens
        self.metrics["token_usage"]["groq_calls"] += 1

    def record_violation(self, violation_type: str):
        """Record policy or schema violations"""
        if violation_type == "schema":
            self.metrics["failures"]["schema_violations"] += 1
        elif violation_type == "policy":
            self.metrics["failures"]["policy_violations"] += 1

    def record_fallback(self):
        """Record fallback usage"""
        self.metrics["failures"]["fallback_usage"] += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return self.metrics.copy()


class CustomCallbackHandler(BaseCallbackHandler):
    """Custom callback handler for LangSmith tracing"""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs
    ) -> None:
        """Called when LLM starts"""
        pass

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """Called when LLM ends"""
        if hasattr(response, "llm_output") and response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})
            if token_usage:
                prompt_tokens = token_usage.get("prompt_tokens", 0)
                completion_tokens = token_usage.get("completion_tokens", 0)
                self.metrics_collector.record_token_usage(
                    prompt_tokens, completion_tokens
                )

    def on_llm_error(self, error: Exception, **kwargs) -> None:
        """Called when LLM encounters an error"""
        self.metrics_collector.record_tool_call("groq_llm", 0, success=False)


def setup_langsmith() -> Optional[Client]:
    """Setup LangSmith client"""
    api_key = os.getenv("LANGSMITH_API_KEY")
    project_name = os.getenv("LANGSMITH_PROJECT", "pr-abandoned-ceramics-69")

    if not api_key:
        print("Warning: LANGSMITH_API_KEY not found. Tracing disabled.")
        return None

    try:
        client = Client(api_key=api_key)
        # Set environment variables for LangChain integration
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGCHAIN_PROJECT"] = project_name

        print(f"LangSmith tracing enabled for project: {project_name}")
        return client
    except Exception as e:
        print(f"Failed to setup LangSmith: {e}")
        return None


def create_tracer(
    project_name: str = "pr-abandoned-ceramics-69",
) -> Optional[LangChainTracer]:
    """Create LangChain tracer"""
    if not os.getenv("LANGSMITH_API_KEY"):
        return None

    try:
        tracer = LangChainTracer(project_name=project_name)
        return tracer
    except Exception as e:
        print(f"Failed to create tracer: {e}")
        return None


def export_trace_to_json(trace_data: Dict[str, Any], filename: str = None) -> str:
    """Export trace data to JSON file"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"trace_{timestamp}.json"

    # Ensure artifacts directory exists
    project_root = Path(__file__).parent.parent
    artifacts_dir = project_root / "artifacts"
    os.makedirs(artifacts_dir, exist_ok=True)

    filepath = os.path.join(artifacts_dir, filename)

    with open(filepath, "w") as f:
        json.dump(trace_data, f, indent=2, default=str)

    print(f"Trace exported to: {filepath}")
    return filepath


def create_sample_trace() -> Dict[str, Any]:
    """Create a sample trace for demonstration"""
    return {
        "run_id": "sample_run_001",
        "timestamp": datetime.now().isoformat(),
        "query": "AI market growth predictions 2025",
        "workflow_steps": [
            {
                "step": "researcher",
                "start_time": "2025-01-27T10:00:00Z",
                "end_time": "2025-01-27T10:00:15Z",
                "duration": 15.2,
                "status": "success",
                "tools_used": ["tavily_search"],
                "facts_extracted": 5,
                "sources_found": 3,
            },
            {
                "step": "analyst",
                "start_time": "2025-01-27T10:00:15Z",
                "end_time": "2025-01-27T10:00:25Z",
                "duration": 10.1,
                "status": "success",
                "violations": 0,
                "quality_score": 0.85,
            },
            {
                "step": "writer",
                "start_time": "2025-01-27T10:00:25Z",
                "end_time": "2025-01-27T10:00:35Z",
                "duration": 9.8,
                "status": "success",
                "report_generated": True,
                "schema_valid": True,
            },
        ],
        "metrics": {
            "total_execution_time": 35.1,
            "token_usage": {
                "total_tokens": 2847,
                "prompt_tokens": 1923,
                "completion_tokens": 924,
                "groq_calls": 3,
            },
            "tool_latency": {"tavily_search": 8.5, "groq_llm": 12.3, "retriever": 2.1},
            "failures": {
                "tool_errors": 0,
                "schema_violations": 0,
                "policy_violations": 0,
                "fallback_usage": 0,
            },
        },
        "output": {
            "topic": "AI market growth predictions 2025",
            "summary": "The AI market is projected to grow significantly in 2025...",
            "references": [
                "https://example.com/ai-market-report-2025",
                "https://example.com/tech-trends-2025",
            ],
            "timestamp": "2025-01-27T10:00:35Z",
            "facts": [
                {
                    "fact": "AI market expected to reach $500B by 2025",
                    "source": "https://example.com/ai-market-report-2025",
                    "confidence": 0.9,
                }
            ],
        },
    }


def generate_metrics_summary(metrics: Dict[str, Any]) -> str:
    """Generate a human-readable metrics summary"""
    summary = f"""
# Workflow Metrics Summary

## Token Usage
- Total Tokens: {metrics['token_usage']['total_tokens']:,}
- Prompt Tokens: {metrics['token_usage']['prompt_tokens']:,}
- Completion Tokens: {metrics['token_usage']['completion_tokens']:,}
- Groq API Calls: {metrics['token_usage']['groq_calls']}

## Tool Performance
- Average Tavily Search Latency: {sum(metrics['tool_latency']['tavily_search'])/len(metrics['tool_latency']['tavily_search']) if metrics['tool_latency']['tavily_search'] else 0:.2f}s
- Average Groq LLM Latency: {sum(metrics['tool_latency']['groq_llm'])/len(metrics['tool_latency']['groq_llm']) if metrics['tool_latency']['groq_llm'] else 0:.2f}s
- Total Execution Time: {metrics['tool_latency']['total_time']:.2f}s

## Reliability
- Total Runs: {metrics['workflow_stats']['total_runs']}
- Successful Runs: {metrics['workflow_stats']['successful_runs']}
- Failed Runs: {metrics['workflow_stats']['failed_runs']}
- Success Rate: {(metrics['workflow_stats']['successful_runs']/metrics['workflow_stats']['total_runs']*100) if metrics['workflow_stats']['total_runs'] > 0 else 0:.1f}%
- Average Execution Time: {metrics['workflow_stats']['avg_execution_time']:.2f}s

## Error Tracking
- Tool Errors: {metrics['failures']['tool_errors']}
- Schema Violations: {metrics['failures']['schema_violations']}
- Policy Violations: {metrics['failures']['policy_violations']}
- Fallback Usage: {metrics['failures']['fallback_usage']}
- Fallback Rate: {(metrics['failures']['fallback_usage']/metrics['workflow_stats']['total_runs']*100) if metrics['workflow_stats']['total_runs'] > 0 else 0:.1f}%
"""
    return summary.strip()


# Global metrics collector instance
metrics_collector = MetricsCollector()
