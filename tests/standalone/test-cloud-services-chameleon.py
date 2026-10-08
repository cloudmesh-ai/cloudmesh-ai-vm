#!/usr/bin/env python3

import argparse
import socket
import sys
from urllib.parse import urlparse

import openstack
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Probe and test reachability of all registered OpenStack services on Chameleon Cloud."
    )
    parser.add_argument(
        "--cloud",
        default="chameleon",
        help="Chameleon cloud entry in clouds.yaml (e.g., 'chameleon' for KVM@TACC or 'uc' for CHI@UC; default: chameleon)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Timeout in seconds for probing each endpoint (default: 3.0)",
    )
    return parser.parse_args()


def check_tcp_port(host: str, port: int, timeout: float = 3.0) -> bool:
    """Test raw TCP connectivity to host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def probe_endpoint(url: str, timeout: float = 3.0) -> dict:
    """Probe an endpoint URL for TCP reachability and HTTP response status."""
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    # 1. First test raw TCP connectivity
    tcp_ok = check_tcp_port(host, port, timeout=timeout)
    if not tcp_ok:
        return {
            "status": "TCP_REFUSED",
            "message": f"Connection refused / unreachable on {host}:{port}",
            "ok": False,
        }

    # 2. Test HTTP response
    try:
        resp = requests.get(url, timeout=timeout, verify=False)
        return {
            "status": f"HTTP {resp.status_code}",
            "message": f"Responded with HTTP {resp.status_code}",
            "ok": True,
        }
    except requests.exceptions.SSLError:
        return {
            "status": "SSL_ERROR",
            "message": "TCP open, SSL verification error",
            "ok": True,
        }
    except requests.exceptions.RequestException as exc:
        return {
            "status": "HTTP_ERROR",
            "message": f"TCP open, HTTP request failed ({exc.__class__.__name__})",
            "ok": False,
        }


def main():
    args = parse_args()
    print(f"🔍 Connecting to Chameleon Cloud ('{args.cloud}')...")

    try:
        conn = openstack.connect(cloud=args.cloud)
        conn.authorize()
    except Exception as exc:
        sys.exit(f"❌ Failed to connect to Chameleon cloud '{args.cloud}': {exc}")

    session = conn.session
    access_data = session.auth.get_access(session)
    catalog = access_data.service_catalog.catalog

    if not catalog:
        sys.exit(f"❌ No service catalog returned for cloud '{args.cloud}'.")

    region = conn.config.region_name or "Default Region"
    print(f"📋 Chameleon Region: {region}")
    print(f"📋 Found {len(catalog)} services in Keystone catalog. Probing endpoints...\n")

    results = []

    for entry in sorted(catalog, key=lambda x: x.get("type", "")):
        srv_type = entry.get("type", "unknown")
        srv_name = entry.get("name", "unknown")

        public_eps = [
            ep.get("url")
            for ep in entry.get("endpoints", [])
            if ep.get("interface") == "public"
        ]
        endpoint_url = public_eps[0] if public_eps else None

        if not endpoint_url:
            all_eps = [ep.get("url") for ep in entry.get("endpoints", [])]
            endpoint_url = all_eps[0] if all_eps else "N/A"

        if endpoint_url == "N/A":
            probe = {"status": "NO_ENDPOINT", "message": "No endpoint URL defined", "ok": False}
        else:
            probe = probe_endpoint(endpoint_url, timeout=args.timeout)

        results.append({
            "type": srv_type,
            "name": srv_name,
            "url": endpoint_url,
            "probe": probe,
        })

    # Print summary table
    col_type = 20
    col_name = 16
    col_status = 18
    col_url = 52

    header = f"{'Service Type':<{col_type}} {'Name':<{col_name}} {'Status':<{col_status}} {'Endpoint URL'}"
    separator = "-" * (col_type + col_name + col_status + col_url)

    print(header)
    print(separator)

    for item in results:
        probe = item["probe"]
        icon = "✅" if probe["ok"] else "❌"
        status_text = f"{icon} {probe['status']}"
        print(f"{item['type']:<{col_type}} {item['name']:<{col_name}} {status_text:<{col_status}} {item['url']}")

    print(separator)

    # Highlight Heat Orchestration status on Chameleon
    heat_item = next((r for r in results if "orchestrat" in r["type"] or "heat" in r["name"]), None)
    if heat_item:
        print("\n🔥 Heat Orchestration Status on Chameleon:")
        if heat_item["probe"]["ok"]:
            print(f"   ✅ Heat is ACTIVE and responding at {heat_item['url']}.")
        else:
            print(f"   ❌ Heat is REGISTERED in Keystone, but endpoint is NOT RESPONDING.")
            print(f"      Detail: {heat_item['probe']['message']}")
    else:
        print(f"\n🔥 Heat Orchestration is NOT registered in Keystone catalog for '{args.cloud}'.")

    # Highlight Blazar Reservation status on Chameleon (key Chameleon service)
    blazar_item = next((r for r in results if "reservation" in r["type"] or "blazar" in r["name"] or "climate" in r["type"]), None)
    if blazar_item:
        print("\n📅 Blazar Reservation (Lease) Status:")
        if blazar_item["probe"]["ok"]:
            print(f"   ✅ Blazar is ACTIVE and responding at {blazar_item['url']}.")
        else:
            print(f"   ❌ Blazar is registered but endpoint is NOT responding.")


if __name__ == "__main__":
    main()
