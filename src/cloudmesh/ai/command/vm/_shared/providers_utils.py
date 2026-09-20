import logging
from rich.console import Console

console = Console()

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
