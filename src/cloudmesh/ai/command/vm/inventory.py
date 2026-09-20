import click
from rich.table import Table
import rich.box as box
from .context import console, get_active_provider, vm_options

@click.group(name="list", invoke_without_command=True)
@click.option("--json", "format_json", is_flag=True, help="Output in JSON")
@click.option("--yaml", "format_yaml", is_flag=True, help="Output in YAML")
@click.option("--csv", "format_csv", is_flag=True, help="Output in CSV")
@click.option("--table", "format_table", is_flag=True, default=True, help="Output in Table")
@vm_options
def list_group(ctx, format_json, format_yaml, format_csv, format_table):
    """Lists VMs or other resources"""
    if ctx.invoked_subcommand is None:
        provider = get_active_provider(ctx)
        vms = provider.list()
        
        if not vms:
            console.print(f"No VMs found on {provider.cloud_name}")
            return

        if format_json:
            import json
            console.print(json.dumps(vms, indent=2))
        elif format_yaml:
            import yaml
            console.print(yaml.dump(vms))
        elif format_csv:
            headers = vms[0].keys()
            console.print(",".join(headers))
            for vm in vms:
                console.print(",".join(str(v) for v in vm.values()))
        else:
            # Use Rich table for a professional look
            table = Table(title=f"VMs in {provider.cloud_name}", box=box.SQUARE, show_header=True, header_style="bold magenta")
            
            headers = vms[0].keys()
            for h in headers:
                table.add_column(h)
            
            for vm in vms:
                table.add_row(*[str(v) for v in vm.values()])
            
            console.print(table)

# Import and add regions command from providers.py
from .providers import list_regions
list_group.add_command(list_regions, name="regions")

@click.command()
@vm_options
def images(ctx):
    """Lists available images"""
    provider = get_active_provider(ctx)
    images_list = provider.get_images()
    if not images_list:
        console.print(f"No images found or not supported by provider '{provider.cloud_name}'.")
        return
    
    # Use Rich table for a professional look
    table = Table(title=f"Available Images in {provider.cloud_name}", box=box.SQUARE, show_header=True, header_style="bold magenta")
    
    headers = images_list[0].keys()
    for h in headers:
        table.add_column(h)
    
    for i in images_list:
        table.add_row(*[str(v) for v in i.values()])
    
    console.print(table)

@click.command()
@vm_options
def flavors(ctx):
    """Lists available hardware profiles"""
    provider = get_active_provider(ctx)
    flavors_list = provider.get_flavors()
    if not flavors_list:
        console.print(f"No flavors found or not supported by provider '{provider.cloud_name}'.")
        return
    
    # Use Rich table for a professional look
    table = Table(title=f"Available Flavors in {provider.cloud_name}", box=box.SQUARE, show_header=True, header_style="bold magenta")
    
    headers = flavors_list[0].keys()
    for h in headers:
        table.add_column(h)
    
    for f in flavors_list:
        table.add_row(*[str(v) for v in f.values()])
    
    console.print(table)
