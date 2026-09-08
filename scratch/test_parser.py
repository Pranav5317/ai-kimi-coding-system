import json
import re

def robust_parse_tool_call(text: str):
    """
    Parses a tool call from text even if it contains malformed JSON or unescaped quotes in 'content'.
    """
    # 1. Try standard json.loads
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict) and ("name" in data or "function" in data):
            return data
    except Exception:
        pass

    # 2. Extract {"name": "...", ...} using regex
    match = re.search(r'\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"(?:parameters|arguments)"\s*:\s*(\{.*\})\s*\}', text, re.DOTALL)
    if match:
        tool_name = match.group(1)
        params_raw = match.group(2)
        try:
            params = json.loads(params_raw)
            return {"name": tool_name, "parameters": params}
        except Exception:
            # Extract path and content individually
            path_match = re.search(r'"path"\s*:\s*"([^"]+)"', params_raw)
            path = path_match.group(1) if path_match else None
            
            # Content might have unescaped quotes
            content_match = re.search(r'"content"\s*:\s*"(.*)"\s*,\s*"path"', params_raw, re.DOTALL)
            if not content_match:
                content_match = re.search(r'"content"\s*:\s*"(.*)"\s*\}', params_raw, re.DOTALL)
            
            content = content_match.group(1) if content_match else ""
            if path:
                return {"name": tool_name, "parameters": {"path": path, "content": content}}

    return None

test_c_text = '{"name": "create_file", "parameters": {"content":"def greet(name: str) -> str:\\n    \\"\\"\\"Return a greeting message.\\"\\":\\n    return f\\"Hello, {name}!\\"\\n\\ndef add(a: int, b: int) -> int:\\n    return a + b\\n\\nif __name__ == \\"__main__\\":\\n    msg = greet(\\"World\\")\\n    print(f\\"Message: {msg}\\")\\n    print(\\"Sum:\\", add(5, 7))\\n", "path":"backend/utils.py"}}'
parsed = robust_parse_tool_call(test_c_text)
print("PARSED:", json.dumps(parsed, indent=2))

