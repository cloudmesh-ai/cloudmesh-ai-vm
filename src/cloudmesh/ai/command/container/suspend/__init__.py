import click
from cloudmesh.ai.command._shared.context import console

@click.group()
def suspend():
    """Pause and resume Docker containers."""
    pass

@suspend.command("pause")
@click.argument("name")
@click.pass_context
def pause_container(ctx: click.Context, name: str):
    """Pause a Docker container."""
    manager = ctx.obj
    if manager.pause(name):
        console.print(f"[green]Container {name} paused.[/green]")
    else:
        console.print(f"[red]Failed to pause container {name}.[/red]")

@suspend.command("resume")
@click.argument("name")
@click.pass_context
def resume_container(ctx: click.Context, name: str):
    """Resume a paused Docker container."""
    manager = ctx.obj
    if manager.unpause(name):
        console.print(f"[green]Container {name} resumed.[/green]")
    else:
        console.print(f"[red]Failed to resume container {name}.[/red]")
