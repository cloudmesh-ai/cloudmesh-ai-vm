import click
from .._shared.context import console, state
from .._shared.exceptions import handle_errors

@click.command()
@click.pass_context
@click.argument("key")
@handle_errors
def get_config(ctx: click.Context, key: str):
    """Get a specific configuration value."""
    val = state.db.get(key)
    if val is not None:
        console.print(f"{key}: [bold green]{val}[/bold green]")
    else:
        raise click.ClickException(f"Configuration key {key} not found.")

cmd = get_config
