#!/usr/bin/env python3

import argparse
import subprocess
import sys
import time
from pathlib import Path
import yaml
import openstack
from keystoneauth1.exceptions.connection import ConnectFailure


HEAT_TEMPLATE = """
heat_template_version: 2021-04-16

description: >
  Hot template to deploy a VM with a Neutron port, security group,
  and floating IP on OpenStack.

parameters:
  server_name:
    type: string
    description: Name for the VM instance
    default: gregor-heat-vm

  image:
    type: string
    description: Image name or ID
    default: Featured-Ubuntu22

  flavor:
    type: string
    description: Flavor name or ID
    default: m3.small

  network:
    type: string
    description: Private network name or ID
    default: auto_allocated_network

  security_group:
    type: string
    description: Security group name or ID
    default: default

  key_name:
    type: string
    description: Public SSH keypair name
    default: gregor-tmp-key

  public_network:
    type: string
    description: External floating IP network
    default: public

resources:
  port:
    type: OS::Neutron::Port
    properties:
      network: { get_param: network }
      security_groups:
        - { get_param: security_group }

  server:
    type: OS::Nova::Server
    properties:
      name: { get_param: server_name }
      image: { get_param: image }
      flavor: { get_param: flavor }
      key_name: { get_param: key_name }
      networks:
        - port: { get_resource: port }

  floating_ip:
    type: OS::Neutron::FloatingIP
    properties:
      floating_network: { get_param: public_network }
      port_id: { get_resource: port }

outputs:
  server_id:
    description: Created Server ID
    value: { get_resource: server }

  floating_ip_address:
    description: Allocated Floating IP address
    value: { get_attr: [floating_ip, floating_ip_address] }
"""


def get_connection(cloud_name: str) -> openstack.connection.Connection:
    """Connect to OpenStack using clouds.yaml entry."""
    try:
        conn = openstack.connect(cloud=cloud_name)
        conn.authorize()
        return conn
    except Exception as exc:
        sys.exit(f"❌ Failed to connect to cloud '{cloud_name}': {exc}")


def check_heat_service_available(conn: openstack.connection.Connection, cloud_name: str):
    """Verify that Heat is in the catalog AND its endpoint is actually responding."""
    if not conn.has_service("orchestration"):
        sys.exit(
            f"❌ The cloud '{cloud_name}' does not have the Orchestration (Heat) service registered in its catalog."
        )

    try:
        # Ping the orchestration endpoint to verify connectivity
        conn.orchestration.get("/", connect_retries=1)
    except (ConnectFailure, Exception) as exc:
        sys.exit(
            f"❌ The Heat Orchestration endpoint for '{cloud_name}' is not reachable:\n"
            f"   {exc}\n\n"
            f"ℹ️  Jetstream-2 has the 'orchestration' service registered in Keystone, but the Heat\n"
            f"   daemon on port 8004 is disabled / connection refused by the cloud provider.\n"
            f"   For Jetstream-2, use OpenStackSDK (tests/standalone/test-vm-opensdk.py) or Terraform."
        )


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


def wait_for_stack_stages(conn: openstack.connection.Connection, stack, wait_seconds: int = 600):
    """
    Monitor Heat stack progression through its resource lifecycle stages.
    Heat uses a DAG to order dependencies (Port -> Server -> FloatingIP).
    """
    print(f"⏳ Waiting for Heat stack '{stack.name}' to complete (up to {wait_seconds}s)...")
    start_time = time.time()
    seen_events = set()

    while time.time() - start_time < wait_seconds:
        # Stream individual resource state transitions (stages)
        try:
            for event in conn.orchestration.events(stack):
                if event.id not in seen_events:
                    seen_events.add(event.id)
                    res_name = getattr(event, "resource_name", "resource")
                    res_status = getattr(event, "resource_status", "")
                    reason = getattr(event, "resource_status_reason", "")
                    print(f"   ↳ [Stage] {res_name}: {res_status} ({reason})")
        except Exception:
            pass

        current = conn.orchestration.get_stack(stack.id, resolve_outputs=True)
        status = getattr(current, "status", "")

        if status == "CREATE_COMPLETE":
            print(f"✅ Stack '{stack.name}' reached CREATE_COMPLETE!")
            return current
        if "FAILED" in status:
            reason = getattr(current, "status_reason", "Unknown failure")
            sys.exit(f"❌ Heat stack failed: {status} - {reason}")

        time.sleep(5)

    sys.exit(f"❌ Timeout waiting for Heat stack '{stack.name}' to reach CREATE_COMPLETE.")


def extract_stack_output(stack, output_key: str) -> str:
    """Extract a resolved output value from stack outputs."""
    outputs = getattr(stack, "outputs", []) or []
    for out in outputs:
        if isinstance(out, dict) and out.get("output_key") == output_key:
            return out.get("output_value")
    return None


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
        description="Deploy a VM with a public IP using OpenStack Heat (Orchestration)."
    )
    parser.add_argument("--cloud", default="jetstream", help="Cloud entry name in clouds.yaml")
    parser.add_argument("--stack-name", default="gregor-heat-stack", help="Heat stack name")
    parser.add_argument("--name", default="gregor-heat-vm", help="Name for the new VM")
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
    parser.add_argument("--wait", type=int, default=600, help="Seconds to wait for stack completion")
    return parser.parse_args()


def main():
    args = parse_args()
    conn = get_connection(args.cloud)

    # Check if Heat is available and reachable
    check_heat_service_available(conn, args.cloud)

    # Ensure keypair exists before stack launch
    keypair_name = ensure_keypair(conn, args.keypair, Path(args.keyfile))

    # Check for existing stack with the same name
    existing_stack = conn.orchestration.find_stack(args.stack_name)
    if existing_stack:
        sys.exit(
            f"❌ A Heat stack named '{args.stack_name}' already exists (ID: {existing_stack.id}).\n"
            f"   Delete it first with: openstack stack delete {args.stack_name}"
        )

    stack_params = {
        "server_name": args.name,
        "image": args.image,
        "flavor": args.flavor,
        "network": args.network,
        "security_group": args.secgroup,
        "key_name": keypair_name,
        "public_network": args.ext_net,
    }

    template_dict = yaml.safe_load(HEAT_TEMPLATE)

    print(f"🚀 Creating Heat stack '{args.stack_name}'...")
    stack = conn.orchestration.create_stack(
        name=args.stack_name,
        template=template_dict,
        parameters=stack_params,
        timeout_mins=max(args.wait // 60, 1),
    )

    # Monitor stack lifecycle stages and resource completion
    completed_stack = wait_for_stack_stages(conn, stack, wait_seconds=args.wait)

    floating_ip = extract_stack_output(completed_stack, "floating_ip_address")
    server_id = extract_stack_output(completed_stack, "server_id")

    if not floating_ip:
        sys.exit("❌ Could not determine floating IP address from Heat stack outputs.")

    print(f"\n🌐 Floating IP: {floating_ip}")
    print(f"🖥️  Server ID:   {server_id}")

    # Determine private key path
    priv_key_path = Path(args.privkey)
    if not priv_key_path.is_file() and args.keyfile.endswith(".pub"):
        candidate = Path(args.keyfile[:-4])
        if candidate.is_file():
            priv_key_path = candidate

    # Test login and execute remote command
    test_ssh_connection(
        user=args.user,
        ip=floating_ip,
        priv_key_path=priv_key_path,
        command=args.command,
        timeout=args.ssh_timeout,
    )

    print("\n🔎  All done!  Connect with:")
    print(f"   ssh -i {priv_key_path} {args.user}@{floating_ip}")
    print("\n🧹  Cleanup when finished (deletes all resources created by Heat):")
    print(f"   openstack stack delete {args.stack_name}")


if __name__ == "__main__":
    main()
