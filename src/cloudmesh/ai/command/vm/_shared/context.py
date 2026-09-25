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
        return self._manager.config
    
    def save(self):
        """Saves the current configuration to the file."""
        # YamlDB usually handles auto-flush, but we keep this for API compatibility.
        pass
    
    def increment_counter(self) -> int:
        return self._manager.increment_counter()
    
    def set_last_vm(self, cloud_name: str, vm_name: str):
        self._manager.set_last_vm(cloud_name, vm_name)
    
    def get_last_vm(self, cloud_name: str) -> Optional[str]:
        return self._manager.get_last_vm(cloud_name)
    @property
    def db(self):
        return self._manager.db

    def set_manager(self, manager: StateManager):
        """Allows tests to inject a different StateManager."""
        self._manager = manager

# Create the singleton instance
state = StateProxy()
state.set_manager(state_manager)

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
        # Use StateManager.db.get for the default_cloud value
        default_cloud = state.config.db.get("default_cloud", "multipass") or "multipass"
        
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

def _parse_range(range_str: str) -> List[int]:
    """Parse a range string like '1-5' or '1' into a list of integers."""
    try:
        if '-' in range_str:
            start_str, end_str = range_str.split('-', 1)
            return list(range(int(start_str), int(end_str) + 1))
        return [int(range_str)]
    except ValueError as e:
        # We use click.ClickException here to avoid circular dependency with exceptions.py
        raise click.ClickException(f"Invalid range format '{range_str}'. Expected 'start-end' (e.g. 1-5).") from e

def resolve_vms(ctx: click.Context, name: Optional[str] = None, count: Optional[int] = None, vm_range: Optional[str] = None) -> List[str]:
    """
    Resolves a list of VM names based on a name (single or hostlist), a count, or a range.
    """
    provider = get_active_provider(ctx)
    
    # 1. Determine the base username for range-based resolution
    provider_config = provider.get_cloud_config(provider.cloud_name)
    raw_username = provider_config.get("username") or state.config.db.get("username", "user")
    username = raw_username.replace("_", "-")

    vms: List[str] = []

    if vm_range:
        indices = _parse_range(vm_range)
        vms = [f"{username}-{i}" for i in indices]
        console.print(f"Targeting VMs in range {vm_range} ([bold blue]{', '.join(vms)}[/bold blue])")
    
    elif count:
        all_vms = provider.list()
        if not all_vms:
            raise click.ClickException("No VMs found.")
        
        timestamp_keys = ["created_at", "timestamp", "creation_time", "created"]
        sort_key = None
        for key in timestamp_keys:
            if all_vms and key in all_vms[0]:
                sort_key = key
                break
        
        if sort_key:
            all_vms.sort(key=lambda x: x.get(sort_key) or "", reverse=True)
        
        to_select = all_vms[:count]
        vms = [vm["name"] for vm in to_select]
        console.print(f"Targeting last {count} VMs: [bold blue]{', '.join(vms)}[/bold blue]")
    
    elif name:
        try:
            hl = Hostlist.expand(name)
            vms = list(hl.hosts)
            if len(vms) > 1:
                console.print(f"Expanded hostlist. Targeting VMs: [bold blue]{', '.join(vms)}[/bold blue]")
        except Exception:
            vms = [name]
    
    else:
        vm_name = resolve_vm_name(ctx, name)
        vms = [vm_name]

    return vms

