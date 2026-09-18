# Managing Virtual Machines with OpenStack SDK

This chapter provides a comprehensive guide to programmatically managing Virtual Machines (VMs) on OpenStack-based clouds (such as Jetstream2 and Chameleon Cloud) using the `openstacksdk`. It progresses from a simple provisioning script to a professional multi-cloud abstraction layer and a command-line interface.

## Quick Start: Launching an SSH-Accessible VM

The following script demonstrates the end-to-end process of launching a VM: uploading an SSH key, configuring a security group to allow port 22, booting the instance, and attaching a floating IP for external access.

```python
import time
import openstack

# Initialize connection (reads from environment variables or ~/.config/openstack/clouds.yaml)
conn = openstack.connect(cloud="openstack") 

def create_ssh_vm():
    # 1. Configuration parameters - Adjust these to match your environment
    IMAGE_NAME = "Ubuntu 22.04"
    FLAVOR_NAME = "m1.small"
    NETWORK_NAME = "private-network"
    EXT_NET_NAME = "public-network"
    KEY_NAME = "my-ssh-key"
    PUBLIC_KEY_FILE = "~/.ssh/id_rsa.pub"
    SEC_GROUP_NAME = "ssh-allowed-secgroup"
    SERVER_NAME = "ssh-accessible-vm"

    print("Fetching cloud resources...")
    image = conn.compute.find_image(IMAGE_NAME)
    flavor = conn.compute.find_flavor(FLAVOR_NAME)
    network = conn.network.find_network(NETWORK_NAME)

    if not all([image, flavor, network]):
        raise ValueError("One or more resources (Image, Flavor, Network) could not be found.")

    # 2. Upload SSH Key Pair
    print(f"Ensuring key pair '{KEY_NAME}' exists...")
    keypair = conn.compute.find_keypair(KEY_NAME)
    if not keypair:
        with open(PUBLIC_KEY_FILE, "r") as f:
            public_key = f.read().strip()
        keypair = conn.compute.create_keypair(name=KEY_NAME, public_key=public_key)
        print(f"Uploaded SSH public key: {KEY_NAME}")

    # 3. Create Security Group and allow SSH (Port 22)
    print(f"Configuring Security Group '{SEC_GROUP_NAME}'...")
    secgroup = conn.network.find_security_group(SEC_GROUP_NAME)
    if not secgroup:
        secgroup = conn.network.create_security_group(
            name=SEC_GROUP_NAME, description="Allow inbound SSH traffic"
        )
        conn.network.create_security_group_rule(
            security_group_id=secgroup.id,
            direction="ingress",
            ethertype="IPv4",
            protocol="tcp",
            port_range_min=22,
            port_range_max=22,
            remote_ip_prefix="0.0.0.0/0",
        )
        print("Created security group rule for SSH (port 22).")

    # 4. Boot the Server
    print(f"Creating server '{SERVER_NAME}'...")
    server = conn.compute.create_server(
        name=SERVER_NAME,
        image_id=image.id,
        flavor_id=flavor.id,
        networks=[{"uuid": network.id}],
        key_name=keypair.name,
        security_groups=[{"name": secgroup.name}],
    )

    print("Waiting for server to build...")
    server = conn.compute.wait_for_server(server, timeout=300)

    # 5. Allocate and Attach a Floating IP
    print("Attaching Floating IP...")
    ext_net = conn.network.find_network(EXT_NET_NAME)
    floating_ip = conn.network.create_ip(floating_network_id=ext_net.id)
    server_port = list(conn.network.ports(device_id=server.id))[0]
    conn.network.update_ip(floating_ip, port_id=server_port.id)

    print("\n" + "=" * 50)
    print(f"VM Successfully Created!\nInstance Name : {server.name}\nFloating IP   : {floating_ip.floating_ip_address}")
    print(f"\nLog in via: ssh ubuntu@{floating_ip.floating_ip_address}")
    print("=" * 50)

if __name__ == "__main__":
    create_ssh_vm()
```

## Authentication and Configuration

### Using `clouds.yaml`

The standard way to manage OpenStack credentials is via a `clouds.yaml` file located at `~/.config/openstack/clouds.yaml`. This allows you to define multiple cloud environments and switch between them easily.

#### Multi-Cloud Configuration Example

```yaml
active_cloud: jetstream2

clouds:
  # Jetstream2 (Indiana University / ACCESS)
  jetstream2:
    auth_type: "v3applicationcredential"
    auth:
      auth_url: "https://js2.jetstream-cloud.org:8001/v3"
      application_credential_id: "YOUR_ID"
      application_credential_secret: "YOUR_SECRET"
    region_name: "iu"
    identity_api_version: "3"
    interface: "public"

  # Chameleon Cloud (CHI@TACC Baremetal)
  chi_tacc:
    auth_type: "v3applicationcredential"
    auth:
      auth_url: "https://chi.tacc.chameleoncloud.org:5000/v3"
      application_credential_id: "YOUR_ID"
      application_credential_secret: "YOUR_SECRET"
    region_name: "RegionOne"
    identity_api_version: "3"
    interface: "public"
```

#### Setting a Default Cloud

You can set a default cloud so that `openstack.connect()` requires no arguments:
1. **In `clouds.yaml`**: Add `active_cloud: cloud_name` at the root level.
2. **Environment Variable**: Set `export OS_CLOUD=cloud_name` in your shell profile.

## Advanced Architecture: Multi-Cloud Abstraction

To avoid writing provider-specific code, you can implement an abstract base class that defines a common interface for all cloud managers.

### The Abstract Interface

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class AbstractCloudManager(ABC):
    """Abstract Base Class for managing Cloud Instances."""

    @property
    @abstractmethod
    def region(self) -> str: pass

    @region.setter
    @abstractmethod
    def region(self, value: str) -> None: pass

    @property
    @abstractmethod
    def image(self) -> Optional[str]: pass

    @abstractmethod
    def set(self, cloud_name: Optional[str] = None, yaml_path: Optional[str] = None, 
            image: Optional[str] = None, network: Optional[str] = None, 
            key_name: Optional[str] = None, key_path: Optional[str] = None, 
            region: Optional[str] = None) -> None:
        """Load configuration and initialize connection."""
        pass

    @abstractmethod
    def boot(self, name: str, flavor: str = "m1.small") -> Dict[str, Any]: pass

    @abstractmethod
    def stop(self, instance_id: str) -> bool: pass

    @abstractmethod
    def start(self, instance_id: str) -> bool: pass

    @abstractmethod
    def destroy(self, instance_id: str) -> bool: pass

    @abstractmethod
    def info(self, instance_id: str) -> Dict[str, Any]: pass
```

### Concrete OpenStack Implementation

The `OpenStackManager` implements the abstract interface using the `openstacksdk`.

```python
import openstack
from openstack.config import loader
from typing import Any, Dict, Optional

class OpenStackManager(AbstractCloudManager):
    def __init__(self, cloud_name: Optional[str] = None):
        self.conn: Optional[openstack.connection.Connection] = None
        self._region: Optional[str] = None
        self._image_id: Optional[str] = None
        self.network_id: Optional[str] = None
        self.key_name: Optional[str] = None
        if cloud_name:
            self.set(cloud_name=cloud_name)

    @property
    def region(self) -> str: return self._region or ""

    @region.setter
    def region(self, value: str) -> None:
        self._region = value
        if self.conn:
            self.conn = openstack.connect(cloud=self.conn.config.name, region_name=value)

    @property
    def image(self) -> Optional[str]: return self._image_id

    def set(self, cloud_name=None, yaml_path=None, image=None, network=None, 
            key_name=None, key_path=None, region=None) -> None:
        config_loader = loader.OpenStackConfig(config_files=[yaml_path] if yaml_path else None)
        target_cloud = cloud_name or config_loader.get_one_cloud().name
        cloud_region = region or config_loader.get_one_cloud(cloud=target_cloud).get_region_name()
        
        self.conn = openstack.connect(cloud=target_cloud, region_name=cloud_region)
        self._region = self.conn.config.region_name

        if image: self.set_image(image)
        if network: self.set_network(network)
        if key_name: self.set_key(key_name, public_key_path=key_path)

    def set_image(self, image_name_or_id: str) -> None:
        img = self.conn.image.find_image(image_name_or_id)
        if not img: raise ValueError(f"Image {image_name_or_id} not found.")
        self._image_id = img.id

    def set_network(self, network_name_or_id: str) -> None:
        net = self.conn.network.find_network(network_name_or_id)
        if not net: raise ValueError(f"Network {network_name_or_id} not found.")
        self.network_id = net.id

    def set_key(self, key_name: str, public_key_path: Optional[str] = None) -> None:
        keypair = self.conn.compute.find_keypair(key_name)
        if not keypair and public_key_path:
            with open(public_key_path, "r") as f:
                pub_key = f.read().strip()
            self.conn.compute.create_keypair(name=key_name, public_key=pub_key)
        self.key_name = key_name

    def boot(self, name: str, flavor: str = "m1.small") -> Dict[str, Any]:
        flv = self.conn.compute.find_flavor(flavor)
        server = self.conn.compute.create_server(
            name=name, image_id=self._image_id, flavor_id=flv.id,
            networks=[{"uuid": self.network_id}], key_name=self.key_name,
        )
        server = self.conn.compute.wait_for_server(server, timeout=300)
        return {"id": server.id, "name": server.name, "status": server.status, "addresses": server.addresses}

    def stop(self, instance_id: str) -> bool:
        server = self.conn.compute.find_server(instance_id)
        if server:
            self.conn.compute.stop_server(server)
            return True
        return False

    def start(self, instance_id: str) -> bool:
        server = self.conn.compute.find_server(instance_id)
        if server:
            self.conn.compute.start_server(server)
            return True
        return False

    def destroy(self, instance_id: str) -> bool:
        server = self.conn.compute.find_server(instance_id)
        if server:
            self.conn.compute.delete_server(server)
            return True
        return False

    def info(self, instance_id: str) -> Dict[str, Any]:
        server = self.conn.compute.find_server(instance_id)
        return {"id": server.id, "name": server.name, "status": server.status, "addresses": server.addresses} if server else {}
```

## Cloud Management CLI (CMC)

The `cmc` tool provides a command-line interface to the `OpenStackManager`, allowing users to manage VMs without writing Python scripts.

### Features
- **State Persistence**: Saves current cloud, network, and image settings in `~/.cmc/config.json`.
- **Auto-Naming**: If no name is provided during `boot`, the tool generates sequential names (e.g., `vm-001`, `vm-002`).
- **Namespace Commands**: Uses `cmc cloud <command>` for clarity.

### Implementation Snippet (Main Loop)
```python
# Usage Example:
# cmc cloud set --name=jetstream2 --image=Featured-Ubuntu22 --network=auto_allocated_network
# cmc cloud boot my-vm
# cmc cloud info
# cmc cloud destroy
```

### Setup and Alias
To make the tool easily accessible, you can create a shell alias:
```bash
chmod +x cmc.py
sudo ln -s $(pwd)/cmc.py /usr/local/bin/cmc
echo 'alias vm="cmc cloud"' >> ~/.zshrc
source ~/.zshrc
```

Now you can use `vm` as a shorthand:
- `vm set --name=jetstream2`
- `vm boot demo-instance`
- `vm info`
- `vm stop`