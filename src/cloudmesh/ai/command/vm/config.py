import click
import yaml
import os
from .context import console, state, CONFIG_PATH, vm_options

@click.command()
def setup():
    """Initialize a sample configuration file"""
    sample_config = {
        "username": "cloudmesh_user",
        "counter": 0,
        "default_cloud": "multipass",
        "clouds": {
            "multipass": {
                "image": "ubuntu-22.04"
            },
            "aws": {
                "region": "us-east-1",
                "image": "ami-xxxxxxxxxxxxxxxxx"
            },
            "jetstream": {
                "image": "Featured-Minimal-Ubuntu24",
                "flavor": "m3.tiny"
            },
            "chameleon": {
                "image": "CC-Ubuntu24.04",
                "flavor": "m1.small",
                "region": "CHI@TACC"
            }
        }
    }
    
    if os.path.exists(CONFIG_PATH):
        console.print(f"Configuration file already exists at {CONFIG_PATH}")
        return

    console.print("Sample configuration file:")
    console.print("-" * 20)
    console.print(yaml.dump(sample_config, default_flow_style=False))
    console.print("-" * 20)

    if click.confirm("Do you want to save this as your default configuration?"):
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w") as f:
                yaml.dump(sample_config, f, default_flow_style=False)
            console.print(f"Configuration saved to {CONFIG_PATH}")
        except Exception as e:
            console.print(f"[bold red]Error saving configuration: {e}[/bold red]")
    else:
        console.print("Setup cancelled.")

@click.command()
def config():
    """Display the current cloud configuration file."""
    console.print(f"Configuration file location: {CONFIG_PATH}\n")
    try:
        with open(CONFIG_PATH, 'r') as f:
            console.print(f.read())
    except FileNotFoundError:
        console.print(f"[bold red]Configuration file not found at {CONFIG_PATH}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Error reading configuration file: {e}[/bold red]")

@click.command(name="get")
def cloud_get():
    """Get the current default cloud provider"""
    cloud = state.config.default_cloud
    if not cloud:
        console.print("No default cloud provider set. Use 'cmx vm set <provider>' to set one.")
    else:
        console.print(cloud)

@click.command()
@click.argument("cloud")
@vm_options
def set(ctx, cloud):
    """Set the default cloud provider"""
    from cloudmesh.ai.vm.factory import factory
    try:
        # Create a temporary provider to validate the configuration
        provider = factory.create(cloud, state.config)
        errors = provider.validate_config()
        if errors:
            console.print(f"[bold red]Configuration errors for cloud '{cloud}':[/bold red]")
            for err in errors:
                console.print(f"[bold red]  - {err}[/bold red]")
            raise click.ClickException("Cloud configuration is invalid.")
            
        state.config.default_cloud = cloud
        state.save()
        console.print(f"Default cloud set to: {cloud}")
    except Exception as e:
        if isinstance(e, click.ClickException):
            raise e
        raise click.ClickException(f"Could not set default cloud: {e}")
