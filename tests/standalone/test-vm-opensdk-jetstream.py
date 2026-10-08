#!/usr/bin/env python3

import argparse
import subprocess
import sys
import time
from pathlib import Path

import openstack


def get_connection(cloud_name: str) -> openstack.connection.Connection:
    """Connect to OpenStack using clouds.yaml entry."""
    try:
        conn = openstack.connect(cloud=cloud_name)
        conn.authorize()
        return conn
    except Exception as exc:
        sys.exit(f"❌ Failed to connect to cloud '{cloud_name}': {exc}")


def ensure_keypair(conn: openstack.connection.Connection, name: str, pub_key_path: Path) -> str:
    """Ensure keypair exists, creating it from pub_key_path if missing."""
    kp = conn.compute.find_keypair(name)
    if kp:
        print(f"✅ Keypair '{name}' already exists.")
        return kp.name

    print(f"🔑 Creating keypair '{name}' from {pub_key_path}...")
    if not pub_key_path.is_file():
        sys.exit(f"❌ Public key file not found at {pub_key_path}")

    with pub_key_path.open() as f:
        pub_key = f.read().strip()

    kp = conn.compute.create_keypair(name=name, public_key=pub_key)
    return kp.name


def find_image(conn: openstack.connection.Connection, identifier: str):
    img = conn.compute.find_image(identifier) or conn.image.find_image(identifier)
    if not img:
        sys.exit(f"❌ Image '{identifier}' not found.")
    return img


def find_flavor(conn: openstack.connection.Connection, identifier: str):
    flavor = conn.compute.find_flavor(identifier)
    if not flavor:
        sys.exit(f"❌ Flavor '{identifier}' not found.")
    return flavor


def find_network(conn: openstack.connection.Connection, identifier: str):
    net = conn.network.find_network(identifier)
    if not net:
        sys.exit(f"❌ Network '{identifier}' not found.")
    return net


def find_security_group(conn: openstack.connection.Connection, identifier: str):
    sg = conn.network.find_security_group(identifier)
    if not sg:
        sys.exit(f"❌ Security group '{identifier}' not found.")
    return sg


def allocate_floating_ip(conn: openstack.connection.Connection, external_network_name: str = "public"):
    print(f"🌐 Allocating floating IP from '{external_network_name}'...")
    ext_net = conn.network.find_network(external_network_name)
    if not ext_net:
        sys.exit(f"❌ External network '{external_network_name}' not found.")
    fip = conn.network.create_ip(floating_network_id=ext_net.id)
    print(f"✅ Allocated floating IP: {fip.floating_ip_address}")
    return fip


def create_server(conn: openstack.connection.Connection, name, image, flavor, network, security_group, keypair_name, wait_seconds):
    print(f"🚀 Booting VM '{name}'...")
    server = conn.compute.create_server(
        name=name,
        image_id=image.id,
        flavor_id=flavor.id,
        networks=[{"uuid": network.id}],
        security_groups=[{"name": security_group.name}],
        key_name=keypair_name,
    )
    print(f"⏳ Waiting for server to become ACTIVE (up to {wait_seconds}s)...")
    server = conn.compute.wait_for_server(
        server,
        status="ACTIVE",
        failures=["ERROR"],
        interval=10,
        wait=wait_seconds,
    )
    print("✅ Server is ACTIVE!")
    return server


def attach_floating_ip(conn: openstack.connection.Connection, server, fip):
    print(f"🔗 Attaching {fip.floating_ip_address} to {server.name}...")
    try:
        conn.compute.add_floating_ip_to_server(server, fip.floating_ip_address)
    except Exception:
        ports = list(conn.network.ports(device_id=server.id))
        if not ports:
            sys.exit("❌ No ports found on the server – cannot attach floating IP")
        conn.network.add_ip_to_port(ports[0], fip)
    print("✅ Floating IP attached.")


def test_ssh_connection(user: str, ip: str, priv_key_path: Path, command: str = "uname -a", timeout: int = 120) -> bool:
    """Wait for SSH to become ready and execute a remote command."""
    print(f"\n🔐 Testing SSH login and running '{command}' on {user}@{ip}...")
    if not priv_key_path.is_file():
        print(f"⚠️  Private key file not found at {priv_key_path}; skipping SSH test.")
        return False

    ssh_cmd = [
        "ssh",
        "-i", str(priv_key_path),
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=5",
        "-o", "BatchMode=yes",
        f"{user}@{ip}",
        command,
    ]

    start_time = time.time()
    last_err = ""
    while time.time() - start_time < timeout:
        res = subprocess.run(ssh_cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"✅ SSH login successful! Command output:\n{res.stdout.strip()}")
            return True
        last_err = res.stderr.strip()
        time.sleep(5)

    print(f"❌ Failed to connect via SSH within {timeout}s.")
    if last_err:
        print(f"   Last error: {last_err}")
    return False


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create a Jetstream-2 VM with a public IP using OpenStackSDK."
    )
    parser.add_argument("--cloud", default="jetstream", help="Cloud entry name in clouds.yaml")
    parser.add_argument("--name", default="gregor-opensdk-vm", help="Name for the new VM")
    parser.add_argument("--image", default="Featured-Ubuntu22", help="Image name or ID")
    parser.add_argument("--flavor", default="m3.small", help="Flavor name or ID")
    parser.add_argument("--network", default="auto_allocated_network", help="Private network name or ID")
    parser.add_argument("--secgroup", default="default", help="Security group name/ID")
    parser.add_argument("--keypair", default="gregor-tmp-key", help="Keypair name to create/use")
    parser.add_argument("--keyfile", default=str(Path.home() / ".ssh/id_rsa.pub"), help="Public SSH key path")
    parser.add_argument("--privkey", default=str(Path.home() / ".ssh/id_rsa"), help="Private SSH key path")
    parser.add_argument("--command", default="uname -a", help="Command to run on the VM via SSH")
    parser.add_argument("--ssh-timeout", type=int, default=120, help="Seconds to wait for SSH to become ready")
    parser.add_argument("--user", default="ubuntu", help="Default SSH user for the OS image")
    parser.add_argument("--ext-net", default="public", help="External network for floating IPs")
    parser.add_argument("--wait", type=int, default=600, help="Seconds to wait for ACTIVE state")
    return parser.parse_args()


def main():
    args = parse_args()
    conn = get_connection(args.cloud)

    image = find_image(conn, args.image)
    flavor = find_flavor(conn, args.flavor)
    network = find_network(conn, args.network)
    secgroup = find_security_group(conn, args.secgroup)
    keypair_name = ensure_keypair(conn, args.keypair, Path(args.keyfile))

    fip = allocate_floating_ip(conn, external_network_name=args.ext_net)
    server = create_server(
        conn,
        name=args.name,
        image=image,
        flavor=flavor,
        network=network,
        security_group=secgroup,
        keypair_name=keypair_name,
        wait_seconds=args.wait,
    )
    attach_floating_ip(conn, server, fip)

    # Determine private key path
    priv_key_path = Path(args.privkey)
    if not priv_key_path.is_file() and args.keyfile.endswith(".pub"):
        candidate = Path(args.keyfile[:-4])
        if candidate.is_file():
            priv_key_path = candidate

    # Test login and execute remote command
    test_ssh_connection(
        user=args.user,
        ip=fip.floating_ip_address,
        priv_key_path=priv_key_path,
        command=args.command,
        timeout=args.ssh_timeout,
    )

    print("\n🔎  All done!  Connect with:")
    print(f"   ssh -i {priv_key_path} {args.user}@{fip.floating_ip_address}")
    print("\n🧹  Cleanup when finished:")
    print(f"   openstack server delete {server.id}")
    print(f"   openstack floating ip delete {fip.id}")


if __name__ == "__main__":
    main()