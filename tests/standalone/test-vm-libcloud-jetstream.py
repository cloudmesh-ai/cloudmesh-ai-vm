#!/usr/bin/env python3

import argparse
import sys
import time
from pathlib import Path
import yaml
from libcloud.compute.types import Provider, NodeState
from libcloud.compute.providers import get_driver
from libcloud.common.openstack import OpenStackException


def load_cloud_config(cloud_name: str) -> dict:
    clouds_path = Path.home() / ".config" / "openstack" / "clouds.yaml"
    if not clouds_path.is_file():
        sys.exit(f"❌ clouds.yaml not found at {clouds_path}")

    with clouds_path.open() as f:
        data = yaml.safe_load(f) or {}

    clouds = data.get("clouds", data) if isinstance(data, dict) else {}
    if not isinstance(clouds, dict) or cloud_name not in clouds:
        sys.exit(f"❌ Cloud '{cloud_name}' not defined in {clouds_path}")

    cfg = clouds[cloud_name]
    if not isinstance(cfg, dict):
        sys.exit(f"❌ Cloud configuration for '{cloud_name}' must be a dictionary.")

    auth = cfg.get("auth", {})
    if not isinstance(auth, dict):
        auth = {}

    auth_url = auth.get("auth_url") or cfg.get("auth_url")
    if not auth_url:
        sys.exit(f"❌ Could not find 'auth_url' for cloud '{cloud_name}' in {clouds_path}.")

    # Libcloud Keystone v3 connection appends '/v3/auth/tokens' to the auth path.
    # If the URL ends with /v3 or /v3.0, strip it to prevent 404 (/v3/v3/auth/tokens).
    auth_url = auth_url.rstrip("/")
    if auth_url.endswith("/v3"):
        auth_url = auth_url[:-3]
    elif auth_url.endswith("/v3.0"):
        auth_url = auth_url[:-5]

    app_cred_id = auth.get("application_credential_id") or cfg.get("application_credential_id")
    app_cred_secret = auth.get("application_credential_secret") or cfg.get("application_credential_secret")
    app_cred_name = auth.get("application_credential_name") or cfg.get("application_credential_name")

    region_name = cfg.get("region_name") or auth.get("region_name")

    cloud_cfg: dict = {
        "ex_force_auth_url": auth_url,
    }
    if region_name:
        cloud_cfg["ex_force_service_region"] = region_name

    if (app_cred_id or app_cred_name) and app_cred_secret:
        # Libcloud Keystone v3 application credentials identifier
        cloud_cfg["ex_force_auth_version"] = "3.x_appcred"
        cloud_cfg["key"] = app_cred_id or app_cred_name
        cloud_cfg["secret"] = app_cred_secret
    else:
        # Standard username/password fallback
        cloud_cfg["ex_force_auth_version"] = "3.x_password"
        cloud_cfg["key"] = auth.get("username") or cfg.get("username", "")
        cloud_cfg["secret"] = auth.get("password") or cfg.get("password", "")
        cloud_cfg["ex_tenant_name"] = auth.get("project_name") or cfg.get("project_name")
        cloud_cfg["ex_user_domain_name"] = auth.get("user_domain_name") or cfg.get("user_domain_name", "Default")
        cloud_cfg["ex_project_domain_name"] = auth.get("project_domain_name") or cfg.get("project_domain_name", "Default")

    return cloud_cfg


def get_driver_instance(cloud_cfg: dict):
    OpenStack = get_driver(Provider.OPENSTACK)
    try:
        driver = OpenStack(**cloud_cfg)
        driver.list_key_pairs()
        return driver
    except OpenStackException as exc:
        sys.exit(f"❌ Failed to authenticate to OpenStack: {exc}")


def ensure_keypair(driver, name, pub_key_path):
    existing_keypairs = [k.name for k in driver.list_key_pairs()]
    if name in existing_keypairs:
        print(f"✅ Keypair '{name}' already exists.")
        return name

    print(f"🔑 Creating keypair '{name}' from {pub_key_path}...")
    if not pub_key_path.is_file():
        sys.exit(f"❌ Public key file not found at {pub_key_path}")
    with pub_key_path.open() as f:
        pub_key = f.read().strip()

    if hasattr(driver, "import_key_pair_from_string"):
        driver.import_key_pair_from_string(name, pub_key)
    elif hasattr(driver, "ex_create_keypair"):
        driver.ex_create_keypair(name, pub_key)
    elif hasattr(driver, "create_key_pair"):
        driver.create_key_pair(name, pub_key)
    return name


def find_image(driver, identifier):
    for img in driver.list_images():
        if identifier in (img.name, img.id):
            return img
    sys.exit(f"❌ Image '{identifier}' not found.")


def find_size(driver, identifier):
    for size in driver.list_sizes():
        if identifier in (size.name, size.id):
            return size
    sys.exit(f"❌ Flavor '{identifier}' not found.")


def find_network(driver, identifier):
    list_func = getattr(driver, "ex_list_networks", getattr(driver, "list_networks", None))
    if not list_func:
        sys.exit("❌ Driver does not support listing networks.")
    for net in list_func():
        if identifier in (net.name, net.id):
            return net
    sys.exit(f"❌ Network '{identifier}' not found.")


def find_security_group(driver, identifier):
    list_func = getattr(driver, "ex_list_security_groups", getattr(driver, "list_security_groups", None))
    if not list_func:
        sys.exit("❌ Driver does not support listing security groups.")
    for sg in list_func():
        if identifier in (sg.name, sg.id):
            return sg
    sys.exit(f"❌ Security group '{identifier}' not found.")


def allocate_floating_ip(driver, external_network_name):
    print(f"🌐 Allocating floating IP from '{external_network_name}'...")
    if hasattr(driver, "ex_create_floating_ip"):
        fip = driver.ex_create_floating_ip(ip_pool=external_network_name)
    elif hasattr(driver, "ex_allocate_floating_ip"):
        fip = driver.ex_allocate_floating_ip(external_network_name)
    else:
        sys.exit("❌ Driver does not support creating floating IPs.")
    print(f"✅ Allocated floating IP: {fip.ip_address}")
    return fip


def create_server(driver, name, image, size, network, security_group, keypair_name, wait_seconds):
    print(f"🚀 Booting VM '{name}'...")
    node = driver.create_node(
        name=name,
        image=image,
        size=size,
        networks=[network],
        ex_security_groups=[security_group],
        ex_keyname=keypair_name,
    )
    print(f"⏳ Waiting for server to become ACTIVE (up to {wait_seconds}s)...")
    start_time = time.time()
    while time.time() - start_time < wait_seconds:
        details = None
        if hasattr(driver, "ex_get_node_details"):
            try:
                details = driver.ex_get_node_details(node.id)
            except Exception:
                pass
        if not details:
            nodes = [n for n in driver.list_nodes() if n.id == node.id]
            if nodes:
                details = nodes[0]

        if details:
            status = getattr(details, "extra", {}).get("status", "")
            vm_state = getattr(details, "extra", {}).get("vm_state", "")
            if details.state == NodeState.RUNNING or status == "ACTIVE" or vm_state == "active":
                print("✅ Server is ACTIVE!")
                return details
            if details.state == NodeState.ERROR or status == "ERROR" or vm_state == "error":
                sys.exit("❌ Server entered ERROR state.")
        time.sleep(10)
    sys.exit("❌ Timeout waiting for server to become ACTIVE.")


def attach_floating_ip(driver, node, fip):
    print(f"🔗 Attaching {fip.ip_address} to {node.name}...")
    if hasattr(driver, "ex_attach_floating_ip_to_node"):
        driver.ex_attach_floating_ip_to_node(node, fip)
    elif hasattr(driver, "ex_associate_floating_ip"):
        driver.ex_associate_floating_ip(node, fip)
    else:
        sys.exit("❌ Driver does not support attaching floating IP.")
    print("✅ Floating IP attached.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create a Jetstream-2 VM with a public IP using Libcloud."
    )
    parser.add_argument("--cloud", default="jetstream", help="Cloud entry name in clouds.yaml")
    parser.add_argument("--name", default="gregor-libcloud-vm", help="Name for the new VM")
    parser.add_argument("--image", default="Featured-Ubuntu22", help="Image name or ID")
    parser.add_argument("--flavor", default="m3.small", help="Flavor name or ID")
    parser.add_argument("--network", default="auto_allocated_network", help="Private network name or ID")
    parser.add_argument("--secgroup", default="default", help="Security group name/ID")
    parser.add_argument("--keypair", default="gregor-tmp-key", help="Keypair name to create/use")
    parser.add_argument("--keyfile", default=str(Path.home() / ".ssh/id_rsa.pub"), help="Public SSH key path")
    parser.add_argument("--user", default="ubuntu", help="Default SSH user for the OS image")
    parser.add_argument("--ext-net", default="public", help="External network for floating IPs")
    parser.add_argument("--wait", type=int, default=600, help="Seconds to wait for ACTIVE state")
    return parser.parse_args()


def main():
    args = parse_args()
    cloud_cfg = load_cloud_config(args.cloud)
    driver = get_driver_instance(cloud_cfg)

    image = find_image(driver, args.image)
    size = find_size(driver, args.flavor)
    network = find_network(driver, args.network)
    secgroup = find_security_group(driver, args.secgroup)
    keypair_name = ensure_keypair(driver, args.keypair, Path(args.keyfile))

    fip = allocate_floating_ip(driver, external_network_name=args.ext_net)
    node = create_server(
        driver,
        name=args.name,
        image=image,
        size=size,
        network=network,
        security_group=secgroup,
        keypair_name=keypair_name,
        wait_seconds=args.wait,
    )
    attach_floating_ip(driver, node, fip)

    print("\n🔎  All done!  Connect with:")
    print(f"   ssh -i ~/.ssh/id_rsa {args.user}@{fip.ip_address}")
    print("\n🧹  Cleanup when finished:")
    print(f"   openstack server delete {node.id}")
    print(f"   openstack floating ip delete {fip.id}")


if __name__ == "__main__":
    main()