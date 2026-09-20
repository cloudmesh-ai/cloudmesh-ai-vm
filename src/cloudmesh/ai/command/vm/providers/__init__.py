import click

@click.group()
def providers_group():
    """Manage VM cloud providers."""
    pass

cmd = providers_group
