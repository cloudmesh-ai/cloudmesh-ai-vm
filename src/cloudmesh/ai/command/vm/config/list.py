import click
from .._shared.context import console, state
from .._shared.exceptions import handle_errors
from .._shared.ui import render_table

@click.command()
@click.pass_context
@handle_errors
def list_config(ctx: click.Context):
    """List all VM configuration settings."""
    config = state.db.dict()
    render_table("VM Configuration", ["Key", "Value"], [[k, v] for k, v in config.items()])

cmd = list_config
