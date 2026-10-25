import click

from cloudmesh.ai.command._shared.context import console


@click.command()
@click.argument("name")
@click.pass_context
def info_container(ctx: click.Context, name: str):
    """Get detailed info about a Docker container."""
    manager = ctx.obj
    info = manager.info(name)
    if info:
        console.print(f"[bold]Container Info: {name}[/bold]")
        for k, v in info.items():
            console.print(f" {k}: [blue]{v}[/blue]")
    else:
        console.print(f"[red]Could not retrieve info for container {name}.[/red]")

