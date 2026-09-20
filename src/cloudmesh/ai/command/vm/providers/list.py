import click
from .._shared.context import console, get_active_provider
from .._shared.exceptions import handle_errors
from .._shared.ui import render_table

@click.command()
@handle_errors
def list_providers(ctx: click.Context):
    """List all available VM providers."""
    from cloudmesh.ai.vm.providers import PROVIDER_MAP
    providers = list(PROVIDER_MAP.keys())
    render_table("Available Providers", ["Provider Name"], [[p] for p in providers])

cmd = list_providers
