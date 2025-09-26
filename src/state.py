from typing import TypedDict, List, Dict, Any


class WorkflowState(TypedDict):
    query: str
    context: str
    tools_used: List[str]
    violations: List[str]
    outputs: Dict[str, Any]
    needs_more_context: bool
    tool_error: bool
    policy_violation: bool
    schema_ok: bool
