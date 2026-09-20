import click

@click.group()
def key_group():
    """Manage VM SSH keys."""
    pass

cmd = key_group
