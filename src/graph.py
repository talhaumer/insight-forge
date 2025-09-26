from typing import Dict, Any
from langgraph.graph import StateGraph, END
from .state import WorkflowState
from .agents import market_researcher, analyst, writer, reviewer
from .fallbacks import create_fallback_response
from .observability import (
    setup_langsmith,
    create_tracer,
    metrics_collector,
    export_trace_to_json,
)


def should_continue_to_analyst(state: WorkflowState) -> str:
    """Decide whether to continue to analyst or handle errors"""
    if state.get("tool_error", False):
        return "reviewer"
    return "analyst"


def should_continue_to_writer(state: WorkflowState) -> str:
    """Decide whether to continue to writer or reviewer"""
    if state.get("policy_violation", False) or not state.get("schema_ok", True):
        return "reviewer"
    return "writer"


def create_workflow() -> StateGraph:
    """Create the market research workflow graph"""
    workflow = StateGraph(WorkflowState)

    # Add nodes
    workflow.add_node("researcher", market_researcher)
    workflow.add_node("analyst", analyst)
    workflow.add_node("writer", writer)
    workflow.add_node("reviewer", reviewer)

    # Add edges
    workflow.set_entry_point("researcher")
    workflow.add_conditional_edges(
        "researcher",
        should_continue_to_analyst,
        {"analyst": "analyst", "reviewer": "reviewer"},
    )
    workflow.add_conditional_edges(
        "analyst",
        should_continue_to_writer,
        {"writer": "writer", "reviewer": "reviewer"},
    )
    workflow.add_edge("writer", END)
    workflow.add_edge("reviewer", END)

    return workflow


def run_market_research(query: str) -> Dict[str, Any]:
    """Run the complete market research workflow with observability"""
    import time
    from datetime import datetime

    # Setup observability
    langsmith_client = setup_langsmith()
    tracer = create_tracer()

    # Start metrics collection
    run_id = f"workflow_{int(time.time())}"
    metrics_collector.start_run(run_id)

    # Initialize state
    initial_state: WorkflowState = {
        "query": query,
        "context": "",
        "tools_used": [],
        "violations": [],
        "outputs": {},
        "needs_more_context": False,
        "tool_error": False,
        "policy_violation": False,
        "schema_ok": True,
    }

    # Create and run workflow
    workflow = create_workflow()
    app = workflow.compile()

    # Add tracer if available
    if tracer:
        app = app.with_config({"callbacks": [tracer]})

    start_time = time.time()
    success = True

    try:
        result = app.invoke(initial_state)
        final_result = result["outputs"].get(
            "report", create_fallback_response(query, "Workflow failed")
        )

        # Record successful completion
        metrics_collector.end_run(success=True)

        # Export trace if LangSmith is available
        if langsmith_client:
            trace_data = {
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "result": final_result,
                "metrics": metrics_collector.get_metrics(),
                "execution_time": time.time() - start_time,
            }
            export_trace_to_json(trace_data, f"workflow_trace_{run_id}.json")

        return final_result

    except Exception as e:
        success = False
        metrics_collector.end_run(success=False)
        metrics_collector.record_tool_call("workflow", 0, success=False)

        # Export error trace
        if langsmith_client:
            error_trace = {
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "error": str(e),
                "metrics": metrics_collector.get_metrics(),
                "execution_time": time.time() - start_time,
            }
            export_trace_to_json(error_trace, f"error_trace_{run_id}.json")

        return create_fallback_response(query, str(e))
