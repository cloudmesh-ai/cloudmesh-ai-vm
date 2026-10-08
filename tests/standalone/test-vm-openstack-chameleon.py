#!/usr/bin/env python3

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

import openstack


def get_connection(cloud_name: str) -> openstack.connection.Connection:
    """Connect to OpenStack using clouds.yaml entry."""
    try:
        conn = openstack.connect(cloud=cloud_name)
        conn.authorize()
        return conn
    except Exception as exc:
        sys.exit(f"❌ Failed to connect to cloud '{cloud_name}': {exc}")


def get_blazar_url(conn: openstack.connection.Connection) -> str:
    """Discover the Blazar reservation service endpoint URL from Keystone."""
    try:
        return conn.session.get_endpoint(service_type="reservation", interface="public")
    except Exception:
        # Some catalogs register it as 'climate' or have internal URL only
        try:
            return conn.session.get_endpoint(service_type="climate", interface="public")
        except Exception:
            return None


def create_reservation(
    conn: openstack.connection.Connection,
    blazar_url: str,
    lease_name: str,
    duration_hours: int = 2,
    node_type: str = "compute_haswell",
    count: int = 1,
) -> dict:
    """Create a reservation / lease in Blazar."""
    now = datetime.now(timezone.utc)
    # Start slightly in the future (1 minute) to allow clock skew
    start_date = (now + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
    end_date = (now + timedelta(hours=duration_hours)).strftime("%Y-%m-%d %H:%M")

    print(f"📅 Creating Blazar reservation '{lease_name}' for {count}x '{node_type}' node(s)...")
    print(f"   Window: {start_date} -> {end_date} UTC ({duration_hours}h duration)")

    payload = {
        "name": lease_name,
        "start_date": start_date,
        "end_date": end_date,
        "reservations": [
            {
                "resource_type": "physical:host",
                "min": count,
                "max": count,
                "resource_properties": json.dumps(["==", "$node_type", node_type]),
                "hypervisor_properties": "",
            }
        ],
        "events": [],
    }

    resp = conn.session.post(f"{blazar_url.rstrip('/')}/leases", json=payload)
    if resp.status_code not in (200, 201):
        # If physical:host fails (e.g. on virtual KVM), try virtual:instance
        err_msg = resp.text
        if "physical:host" in err_msg or "resource_type" in err_msg.lower():
            print("   ↳ Host reservation rejected, trying virtual instance reservation...")
            payload["reservations"] = [
                {
                    "resource_type": "virtual:instance",
                    "amount": count,
                    "vcpus": 2,
                    "memory_mb": 2048,
                    "disk_gb": 20,
                }
            ]
            resp2 = conn.session.post(f"{blazar_url.rstrip('/')}/leases", json=payload)
            if resp2.status_code in (200, 201):
                lease_data = resp2.json().get("lease", {})
                print(f"✅ Lease requested successfully: ID={lease_data.get('id')}")
                return lease_data
        sys.exit(f"❌ Failed to create Blazar reservation: HTTP {resp.status_code} - {resp.text}")

    lease_data = resp.json().get("lease", {})
    print(f"✅ Lease requested successfully: ID={lease_data.get('id')}")
    return lease_data


def wait_for_reservation_active(
    conn: openstack.connection.Connection,
    blazar_url: str,
    lease_id: str,
    timeout: int = 300,
) -> tuple[dict, str]:
    """
    Poll the Blazar lease until its status reaches ACTIVE.
    Verifies that the lease and individual reservations are ACTIVE.
    Returns (lease_data, reservation_id).
    """
    print(f"⏳ Waiting for reservation lease '{lease_id}' to become ACTIVE (up to {timeout}s)...")
    start_time = time.time()
    last_status = None

    while time.time() - start_time < timeout:
        resp = conn.session.get(f"{blazar_url.rstrip('/')}/leases/{lease_id}")
        if resp.status_code != 200:
            sys.exit(f"❌ Failed to poll lease: HTTP {resp.status_code} - {resp.text}")

        lease = resp.json().get("lease", {})
        status = lease.get("status", "").upper()

        if status != last_status:
            print(f"   ↳ Lease status: {status}")
            last_status = status

        if status == "ACTIVE":
            reservations = lease.get("reservations", [])
            active_res = [r for r in reservations if r.get("status", "").upper() == "ACTIVE"]
            print("✅ Reservation is confirmed ACTIVE!")
            print(f"   Active reservations: {len(active_res)} / {len(reservations)}")

            reservation_id = None
            for r in reservations:
                rid = r.get("id")
                rtype = r.get("resource_type")
                rstatus = r.get("status")
                print(f"   - Reservation ID: {rid} | Type: {rtype} | Status: {rstatus}")
                if rstatus == "ACTIVE" and not reservation_id:
                    reservation_id = rid

            return lease, reservation_id

        if status in ("ERROR", "FAILED", "TERMINATED"):
            sys.exit(f"❌ Lease failed with status: {status}. Degraded: {lease.get('degraded')}")

        time.sleep(5)

    sys.exit(f"❌ Timeout waiting for reservation lease '{lease_id}' to become ACTIVE.")


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
    """Find image by name or ID, with fallback to Ubuntu images."""
    img = conn.compute.find_image(identifier) or conn.image.find_image(identifier)
    if not img:
        # Search for available images
        images = list(conn.compute.images())
        for fallback in ("CC-Ubuntu22.04", "CC-Ubuntu20.04", "Ubuntu 22.04", "Featured-Ubuntu22"):
            match = next((i for i in images if fallback.lower() in i.name.lower()), None)
            if match:
                print(f"⚠️  Image '{identifier}' not found. Using fallback image: {match.name}")
                return match
        sys.exit(f"❌ Image '{identifier}' not found.")
    return img


def find_flavor(conn: openstack.connection.Connection, identifier: str):
    flavor = conn.compute.find_flavor(identifier)
    if not flavor:
        # Look for small/standard flavors
        flavors = list(conn.compute.flavors())
        for fallback in ("m1.small", "m1.medium", "baremetal"):
            match = next((f for f in flavors if f.name == fallback), None)
            if match:
                print(f"⚠️  Flavor '{identifier}' not found. Using fallback flavor: {match.name}")
                return match
        sys.exit(f"❌ Flavor '{identifier}' not found.")
    return flavor


def find_network(conn: openstack.connection.Connection, identifier: str):
    net = conn.network.find_network(identifier)
    if not net:
        # Auto-detect private/shared network on Chameleon
        networks = list(conn.network.networks())
        for candidate in ("sharednet1", "auto_allocated_network", "private"):
            match = next((n for n in networks if n.name == candidate), None)
            if match:
                print(f"⚠️  Network '{identifier}' not found. Using '{match.name}'")
                return match
        if networks:
            first_net = next((n for n in networks if not n.is_router_external), networks[0])
            print(f"⚠️  Network '{identifier}' not found. Using '{first_net.name}'")
            return first_net
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
        # Search for external network
        for net in conn.network.networks():
            if net.is_router_external:
                ext_net = net
                break
    if not ext_net:
        sys.exit(f"❌ External network '{external_network_name}' not found.")

    fip = conn.network.create_ip(floating_network_id=ext_net.id)
    print(f"✅ Allocated floating IP: {fip.floating_ip_address}")
    return fip


def create_server(
    conn: openstack.connection.Connection,
    name: str,
    image,
    flavor,
    network,
    security_group,
    keypair_name: str,
    reservation_id: str = None,
    wait_seconds: int = 600,
):
    print(f"🚀 Booting VM '{name}'...")
    kwargs = {
        "name": name,
        "image_id": image.id,
        "flavor_id": flavor.id,
        "networks": [{"uuid": network.id}],
        "security_groups": [{"name": security_group.name}],
        "key_name": keypair_name,
    }

    if reservation_id:
        print(f"📌 Passing active reservation ID '{reservation_id}' in scheduler_hints.")
        kwargs["scheduler_hints"] = {"reservation": reservation_id}

    server = conn.compute.create_server(**kwargs)
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
        description="Launch a Chameleon VM (default: KVM@TACC) with reservation verification and floating IP."
    )
    parser.add_argument(
        "--cloud",
        default="chameleon",
        help="Cloud entry in clouds.yaml (default: 'chameleon' for KVM@TACC)",
    )
    parser.add_argument("--name", default="my-chameleon-vm", help="Name for the new VM")
    parser.add_argument("--lease-name", default="gregor-test-lease", help="Name for the Blazar lease")
    parser.add_argument("--duration", type=int, default=1, help="Reservation duration in hours (default: 1)")
    parser.add_argument("--node-type", default="compute_haswell", help="Node type for reservation (default: compute_haswell)")
    parser.add_argument("--skip-reservation", action="store_true", help="Skip creating a Blazar reservation")
    parser.add_argument("--image", default="CC-Ubuntu22.04", help="Image name or ID")
    parser.add_argument("--flavor", default="m1.small", help="Flavor name or ID")
    parser.add_argument("--network", default="sharednet1", help="Network name or ID")
    parser.add_argument("--secgroup", default="default", help="Security group name/ID")
    parser.add_argument("--keypair", default="gregor-tmp-key", help="Keypair name to create/use")
    parser.add_argument("--keyfile", default=str(Path.home() / ".ssh/id_rsa.pub"), help="Public SSH key path")
    parser.add_argument("--privkey", default=str(Path.home() / ".ssh/id_rsa"), help="Private SSH key path")
    parser.add_argument("--command", default="uname -a", help="Command to run on the VM via SSH")
    parser.add_argument("--ssh-timeout", type=int, default=120, help="Seconds to wait for SSH to become ready")
    parser.add_argument("--user", default="cc", help="Default SSH user for Chameleon OS image (default: cc)")
    parser.add_argument("--ext-net", default="public", help="External network for floating IPs")
    parser.add_argument("--wait", type=int, default=600, help="Seconds to wait for VM ACTIVE state")
    return parser.parse_args()


def main():
    args = parse_args()
    print(f"🔍 Connecting to Chameleon Cloud ('{args.cloud}')...")
    conn = get_connection(args.cloud)

    region = conn.config.region_name or "KVM@TACC"
    print(f"📋 Chameleon Target Region: {region}")

    # 1. Handle Blazar Reservation
    blazar_url = get_blazar_url(conn)
    reservation_id = None
    lease_id = None

    if not args.skip_reservation:
        if blazar_url:
            print(f"📋 Discovered Blazar Reservation Endpoint: {blazar_url}")
            lease_data = create_reservation(
                conn=conn,
                blazar_url=blazar_url,
                lease_name=args.lease_name,
                duration_hours=args.duration,
                node_type=args.node_type,
            )
            lease_id = lease_data.get("id")

            # Verify reservation is active
            active_lease, reservation_id = wait_for_reservation_active(
                conn=conn,
                blazar_url=blazar_url,
                lease_id=lease_id,
                timeout=300,
            )
        else:
            print("ℹ️  Blazar reservation service is not registered in Keystone for this site.")
            print("   Proceeding with direct on-demand VM launch (standard for KVM@TACC).")
    else:
        print("⏭️  Skipping reservation step as requested (--skip-reservation).")

    # 2. Keypair
    keypair_name = ensure_keypair(conn, args.keypair, Path(args.keyfile))

    # 3. Resolve Resources
    image = find_image(conn, args.image)
    flavor = find_flavor(conn, args.flavor)
    network = find_network(conn, args.network)
    secgroup = find_security_group(conn, args.secgroup)

    # 4. Floating IP
    fip = allocate_floating_ip(conn, external_network_name=args.ext_net)

    # 5. Boot VM
    server = create_server(
        conn,
        name=args.name,
        image=image,
        flavor=flavor,
        network=network,
        security_group=secgroup,
        keypair_name=keypair_name,
        reservation_id=reservation_id,
        wait_seconds=args.wait,
    )

    # 6. Attach Floating IP
    attach_floating_ip(conn, server, fip)

    # 7. Test SSH Connection
    priv_key_path = Path(args.privkey)
    if not priv_key_path.is_file() and args.keyfile.endswith(".pub"):
        candidate = Path(args.keyfile[:-4])
        if candidate.is_file():
            priv_key_path = candidate

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
    if lease_id and blazar_url:
        print(f"   curl -X DELETE {blazar_url}/leases/{lease_id} (or via blazar client)")


if __name__ == "__main__":
    main()
