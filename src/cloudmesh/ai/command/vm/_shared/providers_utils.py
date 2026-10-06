import logging
import re
from rich.console import Console

console = Console()

def sanitize_output(text: str) -> str:
    """
    Removes sensitive information from CLI output using pattern matching.
    Replaces secrets, tokens, and passwords with [REDACTED].
    """
    if not text:
        return ""

    # Patterns to redact: (Pattern, Replacement)
    patterns = [
        (r'(?i)(bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*', r'\1[REDACTED]'),
        (r'(?i)(api_key\s*[:=]?\s*)[^&\s]+', r'\1[REDACTED]'),
        (r'(?i)(password\s*[:=]?\s*)[^&\s]+', r'\1[REDACTED]'),
        (r'(?i)(secret\s*[:=]?\s*)[^&\s]+', r'\1[REDACTED]'),
        (r'(?i)(token\s*[:=]?\s*)[^&\s]+', r'\1[REDACTED]'),
        (r'(?i)(auth_token\s*[:=]?\s*)[^&\s]+', r'\1[REDACTED]'),
    ]

    sanitized = text
    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized)

    return sanitized

def register_providers():
    """
    Registers all VM providers using entry points.
    This ensures that the provider map is populated before commands run.
    """
    try:
        from cloudmesh.ai.vm.providers import register_providers as _reg
        _reg()
    except Exception as e:
        logging.error(f"Failed to register providers: {e}")

def format_provider_errors(error: Exception) -> str:
    """Formats provider-specific errors into a user-friendly string."""
    return f"Provider Error: {str(error)}"
