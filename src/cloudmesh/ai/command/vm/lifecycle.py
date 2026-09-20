import click
from .context import console, get_active_provider, vm_options

@click.command()
@click.argument("name")
@vm_options
def start(ctx, name):
    """Starts a VM"""
    provider = get_active_provider(ctx)
    if provider.start(name):
        console.print(f"Successfully started VM {name}.")
    else:
        console.print(f"[bold red]Failed to start VM {name}.[/bold red]")

@click.command()
@click.argument("name")
@vm_options
def stop(ctx, name):
    """Stops a VM"""
    provider = get_active_provider(ctx)
    if provider.stop(name):
        console.print(f"Successfully stopped VM {name}.")
    else:
        console.print(f"[bold red]Failed to stop VM {name}.[/bold red]")

@click.command()
@click.argument("name")
@vm_options
def restart(ctx, name):
    """Restarts a VM"""
    provider = get_active_provider(ctx)
    if provider.restart(name):
        console.print(f"Successfully restarted VM {name}.")
    else:
        console.print(f"[bold red]Failed to restart VM {name}.[/bold red]")

@click.command()
@click.argument("name")
@vm_options
def suspend(ctx, name):
    """Suspends a VM"""
    provider = get_active_provider(ctx)
    if provider.suspend(name):
        console.print(f"Successfully suspended VM {name}.")
    else:
        console.print(f"[bold red]Failed to suspend VM {name}.[/bold red]")

@click.command()
@click.argument("name")
@vm_options
def delete(ctx, name):
    """Deletes a VM"""
    provider = get_active_provider(ctx)
    if provider.delete(name):
        console.print(f"Successfully deleted VM {name}.")
    else:
        console.print(f"[bold red]Failed to delete VM {name}.[/bold red]")

@click.command()
@click.argument("name")
@click.argument("command")
@vm_options
def run(ctx, name, command):
    """Executes a command on a VM"""
    provider = get_active_provider(ctx)
    result = provider.run_command(name, command)
    if result:
        console.print(result)
    else:
        console.print(f"[bold red]Failed to execute command on VM {name}.[/bold red]")

@click.command()
@click.argument("name")
@vm_options
def shelve(ctx, name):
    """Shelve the VM (OpenStack only)"""
    provider = get_active_provider(ctx)
    if not hasattr(provider, "shelve"):
        console.print(f"[bold red]Error: Provider '{provider.cloud_name}' does not support shelving.[/bold red]")
        return
    if provider.shelve(name):
        console.print(f"Successfully shelved VM {name}.")
    else:
        console.print(f"[bold red]Failed to shelve VM {name}.[/bold red]")

@click.command()
@click.argument("name")
@vm_options
def unshelve(ctx, name):
    """Unshelve the VM (OpenStack only)"""
    provider = get_active_provider(ctx)
    if not hasattr(provider, "unshelve"):
        console.print(f"[bold red]Error: Provider '{provider.cloud_name}' does not support unshelving.[/bold red]")
        return
    if provider.unshelve(name):
        console.print(f"Successfully unshelved VM {name}.")
    else:
        console.print(f"[bold red]Failed to unshelve VM {name}.[/bold red]")
