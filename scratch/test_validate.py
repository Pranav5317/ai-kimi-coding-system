import json
import re

def validate_file_content(content: str) -> tuple[bool, str]:
    """
    Validates whether the content argument for create_file/edit_file looks like a valid,
    non-truncated string.
    """
    if content is None:
        return False, "Content parameter is missing (None)."
    
    stripped = content.strip()
    
    # Check for obvious truncated code patterns
    truncated_patterns = [
        r'^print\s*\(?$',
        r'^[a-zA-Z_]\w*\s*\(+$',
        r'^[a-zA-Z_]\w*\s*=\s*$',
        r'^def\s+\w+\s*\(?$',
    ]
    
    for pattern in truncated_patterns:
        if re.match(pattern, stripped):
            return False, (
                f"The content appears to be truncated ('{stripped}'). "
                "Please provide the complete, untruncated file content with all quotation marks properly escaped."
            )
            
    return True, ""

# Test truncation check
print(validate_file_content("print("))
print(validate_file_content('print("Hello from backend!")'))

