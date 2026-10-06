import click
import ast
from .._shared.context import console, state
from .._shared.exceptions import handle_errors

def parse_value(value: str):
    """Attempt to parse value as boolean, integer, or float; fallback to string."""
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value

@click.command()
@click.argument("key")
@click.argument("value")
@handle_errors
def set_config(ctx: click.Context, key: str, value: str):
    """Set a configuration value."""
    parsed_val = parse_value(value)
    state.config.set(key, parsed_val)
    console.print(f"Configured [bold green]{key}[/bold green] = {parsed_val} ({type(parsed_val).__name__}).")

cmd = set_config
