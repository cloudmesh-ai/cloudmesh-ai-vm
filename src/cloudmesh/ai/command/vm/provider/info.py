import click
from .._shared.context import console, get_active_provider, vm_options, state
from .._shared.exceptions import handle_errors
from .._shared.ui import render_table

@click.command()
@click.pass_context
@vm_options
@handle_errors
def provider_info(ctx: click.Context) -> None:
    """Display detailed information about the active VM provider."""
    provider = get_active_provider(ctx)
    
    try:
        # Fetch provider-specific info
        info = provider.get_provider_info()
        
        if not info:
            console.print(f"No detailed information available for provider: {provider.cloud_name}")
            return
        
        # Prepare data for table
        rows = [[k, v] for k, v in info.items()]
        
        table_title = f"Provider Info: {provider.cloud_name}"
        render_table(table_title, ["Key", "Value"], rows)
        
    except Exception as e:
        # handle_errors usually catches this, but we can be explicit
        raise click.ClickException(str(e))

# To make 'cmx vm provider info' work, we register the function as 'cmd'
cmd = provider_info
