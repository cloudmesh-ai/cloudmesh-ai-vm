import openstack
import sys

# Configuration
CLOUD_NAME = "jetstream"
VM_NAME = "gvonlaszewski-305"

def set_floating_ip():
    print(f"--- Target: Assign FIP to {VM_NAME} ---")
    
    try:
        conn = openstack.connect(cloud=CLOUD_NAME)
        print(f"Successfully connected to {CLOUD_NAME}")
    except Exception as e:
        print(f"Connection Error: {e}")
        return

    # 1. Identify Server
    print(f"Searching for server {VM_NAME}...")
    server = conn.compute.find_server(VM_NAME)
    if not server:
        print(f"Error: Server {VM_NAME} not found.")
        return
    print(f"Found Server: {server.id} | Status: {server.status}")

    # 2. Identify Port
    print("Finding network port for server...")
    try:
        ports = list(conn.network.ports(device_id=server.id))
        if not ports:
            print("Error: No network ports found for this server.")
            return
        port = ports[0]
        print(f"Found port: {port.id}")
    except Exception as e:
        print(f"Port Lookup Error: {e}")
        return

    # 3. Reserve Floating IP
    print("Finding public network and reserving IP...")
    try:
        networks = conn.network.networks(is_router_external=True)
        public_net = next(networks, None)
        if not public_net:
            print("Error: Could not find an external network.")
            return
        
        fip = conn.network.create_ip(floating_network_id=public_net.id)
        print(f"Reserved IP: {fip.floating_ip_address} (ID: {fip.id})")
    except Exception as e:
        print(f"Reservation Error: {e}")
        return

    # 4. Associate IP with Port (The CORRECT Neutron way)
    print(f"Associating IP {fip.id} with port {port.id}...")
    try:
        # Correct SDK method: update the IP to point to the port
        conn.network.update_ip(fip.id, port_id=port.id)
        
        print("\n====================================================")
        print(f"SUCCESS: {VM_NAME} now has Floating IP: {fip.floating_ip_address}")
        print("====================================================")
    except Exception as e:
        print(f"Association Error: {e}")

if __name__ == "__main__":
    set_floating_ip()

