import click

from cloudmesh.ai.command._shared.context import (
    console,
    get_active_provider,
    resolve_vm_name,
    vm_options,
)
from cloudmesh.ai.command._shared.exceptions import handle_errors


@click.command()
@click.pass_context
@vm_options
@handle_errors
def ssh_config(ctx: click.Context, name: str | None = None, **kwargs):
    """
    Generate SSH configuration for the VM.
    """
    provider = get_active_provider(ctx)
    # Provider usually has a method to generate the config or we can format it
    vm_name = resolve_vm_name(ctx, name)
    config = (
        provider.get_ssh_config(vm_name)
        if hasattr(provider, "get_ssh_config")
        else None
    )
    if config:
        console.print(config)
    else:
        console.print("Could not generate SSH config.")


cmd = ssh_config
