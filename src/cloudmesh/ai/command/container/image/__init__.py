import click
from cloudmesh.ai.command._shared.context import console

@click.group()
def image():
    """Manage Docker images."""
    pass

@image.command("list")
@click.pass_context
def list_images(ctx: click.Context):
    """List Docker images."""
    manager = ctx.obj
    images = manager.list_images()
    if not images:
        console.print("No images found.")
        return
    
    console.print("[bold]Docker Images:[/bold]")
    for img in images:
        tags = ", ".join(img['tags']) if img['tags'] else "none"
        console.print(f"- {tags} ({img['id'][:12]})")

@image.command("pull")
@click.argument("image_name")
@click.pass_context
def pull_image(ctx: click.Context, image_name: str):
    """Pull a Docker image."""
    manager = ctx.obj
    if manager.pull_image(image_name):
        console.print(f"[green]Successfully pulled image {image_name}[/green]")
    else:
        console.print(f"[red]Failed to pull image {image_name}[/red]")

@image.command("delete")
@click.argument("image_id")
@click.pass_context
def delete_image(ctx: click.Context, image_id: str):
    """Delete a Docker image."""
    manager = ctx.obj
    if manager.delete_image(image_id):
        console.print(f"[green]Successfully deleted image {image_id}[/green]")
    else:
        console.print(f"[red]Failed to delete image {image_id}[/red]")
