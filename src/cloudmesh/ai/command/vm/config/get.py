import click
from .._shared.context import console, state
from .._shared.exceptions import handle_errors

@click.command()
@click.argument("key")
@handle_errors
def get_config(ctx: click.Context, key: str):
    """Get a specific configuration value."""
    val = state.config.get(key)
    if val:
        console.print(f"{key}: [bold green]{val}[/bold green]")
    else:
        console.print(f"Configuration key [red]{key}[/red] not found.")

cmd = get_config
