# Using Chameleon Cloud with Python

This chapter describes how to programmatically interact with Chameleon Cloud using the `python-chi` library. It covers resource discovery, reservation management, and launching bare-metal instances.

## Introduction

Chameleon Cloud provides a reservation-based resource allocation model for bare-metal nodes. To use these resources, you must first create a lease (reservation), wait for it to become active, and then launch instances against that reservation.

## Prerequisites

### Installation

Install the necessary libraries in your local environment or Jupyter session:

```bash
pip install python-chi docopt
```

### Configuration

You must have your environment configured via your project's OpenStack `clouds.yaml` or `openrc` credentials file to authenticate with the Chameleon API.

## Resource Discovery

Before attempting a reservation, it is best practice to check the availability of hardware resources.

### Checking Resource Availability

The following script allows you to search for available compute nodes or devices based on a specified start date and duration.

```python
"""Chameleon Cloud Resource Availability Checker.

Usage:
  check_chameleon_resources.py [--site=<site>] [--project=<project>] [--resource-type=<type>] [--start=<datetime>] [--duration=<hours>]
  check_chameleon_resources.py (-h | --help)

Options:
  -h --help                         Show this screen.
  --site=<site>                     Chameleon site [default: CHI@UC]
  --project=<project>               Chameleon project name [default: CHI-XXXXXX]
  --resource-type=<type>            Resource category to check: nodes or devices [default: nodes]
  --start=<datetime>                Start time window (YYYY-MM-DD HH:MM) [default: now]
  --duration=<hours>                Duration of use in hours [default: 3]
"""

from datetime import datetime, timedelta
from docopt import docopt
from chi import context, hardware
from chi.clients import blazar

def main():
    args = docopt(__doc__)
    
    site = args["--site"]
    project = args["--project"]
    resource_type = args["--resource-type"].lower()
    start_str = args["--start"]
    duration_hours = float(args["--duration"])

    # Configure session context
    context.use_site(site)
    context.use_project(project)

    # Parse start time
    if start_str.lower() == "now":
        start_time = datetime.now()
    else:
        start_time = datetime.strptime(start_str, "%Y-%m-%d %H:%M")

    duration = timedelta(hours=duration_hours)
    end_time = start_time + duration

    print(f"Site: {site} | Project: {project}")
    print(f"Checking availability for [{resource_type.upper()}] from {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')} ({duration_hours}h duration)\n")

    blazar_client = blazar()

    if resource_type == "nodes":
        items = hardware.get_nodes(all_sites=False)
        types = sorted(list(set(n.type for n in items)))
        
        print(f"{'Node Type':<30} | {'Total':<8} | {'Available'}")
        print("-" * 52)
        
        for nt in types:
            matching = [n for n in items if n.type == nt]
            total_count = len(matching)
            available_count = 0
            
            for node in matching:
                host_id = next((h["id"] for h in blazar_client.host.list() if h.get("uid") == node.uid), None)
                if not host_id:
                    continue
                allocation = blazar_client.host.get_allocation(host_id)
                reservations = allocation.get("reservations", []) if allocation else []
                
                is_free = True
                for res in reservations:
                    res_start = datetime.strptime(res["start_date"], "%Y-%m-%d %H:%M")
                    res_end = datetime.strptime(res["end_date"], "%Y-%m-%d %H:%M")
                    if start_time < res_end and end_time > res_start:
                        is_free = False
                        break
                if is_free:
                    available_count += 1

            print(f"{nt:<30} | {total_count:<8} | {available_count}")

    elif resource_type == "devices":
        items = hardware.get_devices()
        types = sorted(list(set(d.device_type for d in items)))
        
        print(f"{'Device Type':<30} | {'Total':<8} | {'Available'}")
        print("-" * 52)
        
        for dt in types:
            matching = [d for d in items if d.device_type == dt]
            total_count = len(matching)
            available_count = 0
            
            for dev in matching:
                _, next_slot = dev.next_free_timeslot(minimum_hours=int(duration_hours))
                if next_slot and next_slot <= end_time:
                    available_count += 1
                elif not next_slot:
                    available_count += 1
                    
            print(f"{dt:<30} | {total_count:<8} | {available_count}")
    else:
        print(f"Unknown resource type '{resource_type}'. Please specify 'nodes' or 'devices'.")

if __name__ == "__main__":
    main()
```

### Example Usage

**Check default compute nodes for a 4-hour block starting immediately:**
```bash
python check_chameleon_resources.py --duration=4
```

**Check specialized devices (accelerators/FPGAs) at CHI@TACC for a custom window:**
```bash
python check_chameleon_resources.py --site=CHI@TACC --resource-type=devices --start="2026-06-01 14:00" --duration=2
```

## Provisioning Bare-Metal Instances

Once you have identified an available node type, you can reserve and launch a compute instance.

### Reserving and Launching Ubuntu 26.04

This script reserves a compute node via a lease, waits for the lease to become active, and then launches an instance using the `CC-Ubuntu26.04` image.

```python
import os
from datetime import timedelta
from chi import context, lease, server

# 1. Configure target site and project
context.use_site("CHI@UC")
context.use_project("CHI-XXXXXX")  # Replace with your Chameleon project name

# 2. Define Lease and Server parameters
username = os.getenv("USER", "chameleon-user")
lease_name = f"{username}-ubuntu26-lease"
server_name = f"{username}-ubuntu26-server"

# Specify the target node type (e.g., compute_cascadelake_r)
node_type = "compute_cascadelake_r" 

print(f"Creating lease '{lease_name}' for node type '{node_type}'...")

# 3. Create and submit the reservation lease
l = lease.Lease(
    name=lease_name,
    duration=timedelta(hours=2)  # Adjust duration as needed
)
l.add_node_reservation(node_type=node_type, amount=1)
l.add_fip_reservation(amount=1)  # Reserve a floating IP for external access

# Submit the lease and block execution until it becomes active
l.submit(wait_for_active=True)
print(f"Lease active! Reservation ID: {l.node_reservations[0]['id']}")

# 4. Launch the Ubuntu 26.04 instance against the active reservation
print(f"Launching server '{server_name}' using image 'CC-Ubuntu26.04'...")

s = server.Server(
    name=server_name,
    reservation_id=l.node_reservations[0]["id"],
    image_name="CC-Ubuntu26.04",
    # key_name="your-ssh-key-name" # Uncomment and specify your SSH keypair
)

# Submit server creation and wait for it to be fully up and running
s.submit(wait_for_active=True)
print(f"Server '{server_name}' successfully launched and running!")

# 5. Associate Floating IP
try:
    floating_ips = l.get_reserved_floating_ips()
    if floating_ips:
        fip = floating_ips[0]
        s.associate_floating_ip(fip)
        print(f"Associated Floating IP {fip} to server.")
        print(f"You can now SSH into your instance using: ssh cc@{fip}")
except Exception as e:
    print(f"Could not automatically associate floating IP: {e}")
```

## Advanced Use Cases

Chameleon Cloud is particularly useful for:

- **HPC & ML Benchmarking**: Running MLCommons/MLPerf suites, PyTorch, vLLM, and Ollama on dedicated GPUs without hypervisor jitter.
- **Software-Defined Networking (SDN)**: Customizing layer-2 topologies using Chameleon's portable networking tools.
- **Operating System Research**: Testing custom Linux kernel patches on raw bare-metal hardware.

## Best Practices

- **Clean Up Leases**: Always terminate your leases when finished. Unused active leases block other researchers from accessing hardware.
- **Automate with Scripts**: Use the CLI and Python scripts to speed up repeated experiment iterations.
- **Use Floating IPs**: Essential for secure external connection to your bare-metal nodes.
- **Refer to Official Docs**: For more detailed information, visit the [Chameleon Cloud Documentation](https://chameleoncloud.readthedocs.io/).