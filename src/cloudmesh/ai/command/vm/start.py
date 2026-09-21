import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options, state
from ._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name", required=False)
@vm_options
@handle_errors
def start(ctx: click.Context, name: Optional[str] = None) -> None:
    """
    Starts or launches a VM. If no name is provided, a name will be generated 
    based on {username}-{counter} from the configuration.
    
    Example:
        cmx vm start my-vm
        cmx vm start
    """
    provider = get_active_provider(ctx)
    
    # 1. Resolve VM Name
    if not name:
        # Generate name using username and incremented counter from state
        # Try to get provider-specific username first, then fallback to global username
        provider_config = provider.get_cloud_config(provider.cloud_name)
        raw_username = provider_config.get("username") or state.config.username or "user"
        username = raw_username.replace("_", "-")
        
        counter = state.increment_counter()
        name = f"{username}-{counter}"
        console.print(f"No name provided. Generating VM name: [bold blue]{name}[/bold blue]")
    
    # 2. Start the VM
    result = provider.start(name=name)
    
    if result:
        # The provider returns the final name of the VM
        vm_name = result if isinstance(result, str) else name
        state.set_last_vm(provider.cloud_name, vm_name)
        console.print(f"Successfully started VM [bold green]{vm_name}[/bold green].")
    else:
        raise VMCommandError(f"Failed to start VM {name}.")

cmd = start
