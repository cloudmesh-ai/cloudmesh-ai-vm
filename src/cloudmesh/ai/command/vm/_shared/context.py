import click
import logging
import os
from typing import Optional
from dataclasses import dataclass
from cloudmesh.ai.vm.state_manager import StateManager

@dataclass
class VMContext:
    cloud_override: Optional[str] = None
    interactive: bool = False

# Initialize StateManager with the default config path
CONFIG_PATH = os.path.expanduser("~/.config/cloudmesh/clouds.yaml")
state_manager = StateManager(CONFIG_PATH)

class StateProxy:
    """
    Proxy class to provide easy access to the StateManager.
    """
    @property
    def config(self):
        return state_manager.config
    
    def increment_counter(self) -> int:
        return state_manager.increment_counter()
    
    def set_last_vm(self, cloud_name: str, vm_name: str):
        state_manager.set_last_vm(cloud_name, vm_name)
    
    def get_last_vm(self, cloud_name: str) -> Optional[str]:
        return state_manager.get_last_vm(cloud_name)

# Create a singleton instance for use across the CLI
state = StateProxy()

def cloud_callback(ctx: click.Context, param, value):
    if value:
        if ctx.obj is None:
            ctx.obj = VMContext()
        ctx.obj.cloud_override = value
    return value

def debug_callback(ctx: click.Context, param, value):
    if value:
        logging.getLogger("cloudmesh.ai.vm").setLevel(logging.DEBUG)
    return value

def verbose_callback(ctx: click.Context, param, value):
    if value:
        pass
    return value

def get_active_provider(ctx: click.Context):
    from .providers_utils import register_providers
    register_providers()
    
    default_cloud = "multipass"
    if state.config:
        default_cloud = getattr(state.config, "default_cloud", "multipass") or "multipass"
        
    cloud = ctx.obj.cloud_override if ctx.obj else None
    if not cloud:
        cloud = default_cloud
        
    try:
        from cloudmesh.ai.vm.providers import get_provider
        return get_provider(cloud)
    except Exception as e:
        raise click.ClickException(f"Unsupported or misconfigured cloud provider: {cloud}. Error: {e}")

def resolve_vm_name(ctx: click.Context, name: Optional[str]) -> str:
    if name:
        return name
    
    provider = get_active_provider(ctx)
    cloud_name = provider.cloud_name
    last_vm = state.get_last_vm(cloud_name)
    
    if last_vm:
        return last_vm
    
    raise click.ClickException("No VM name provided and no recent VM found in session. Please provide a name.")

def vm_options(f):
    """Decorator to add common VM options."""
    return f

from rich.console import Console
console = Console()
