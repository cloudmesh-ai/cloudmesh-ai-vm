import click
from ._shared.context import console, get_active_provider, vm_options
from ._shared.exceptions import handle_errors
from ._shared.ui import render_table

@click.command()
@click.pass_context
@vm_options
@handle_errors
def image(ctx: click.Context):
    """List available VM image."""
    provider = get_active_provider(ctx)
    imgs = provider.get_images() # Adjusted to use get_images() from MultipassManager
    if imgs:
        render_table("Images", ["Name", "ID"], [[img.get("name", "Unknown"), img.get("id", "Unknown")] for img in imgs])
    else:
        console.print("No images found.")

cmd = image
