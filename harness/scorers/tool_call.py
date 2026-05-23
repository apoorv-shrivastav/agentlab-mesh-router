import ast

from common.schema import AgentResponse


def verify_tool_call_syntax(code_str: str, expected_tool: str) -> bool:
    """
    Uses Python's AST parser to inspect if a specific tool call is present in the code.
    Used for verifying custom python tool integration.
    """
    try:
        tree = ast.parse(code_str)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == expected_tool:
                    return True
                elif isinstance(node.func, ast.Attribute) and node.func.attr == expected_tool:
                    return True
    except SyntaxError:
        return False
    return False

def score_response_tool_calls(response: AgentResponse, expected_tool: str) -> bool:
    """
    Checks if the expected tool was recorded in the response's tool calls metadata.
    """
    for call in response.tool_calls:
        if call.get("name") == expected_tool:
            return True
    # Fallback to scanning self_reports for explicit logging
    if expected_tool == "report" and len(response.self_reports) > 0:
        return True
    return False
