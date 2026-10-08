import datetime
import os
import time

# Set OS_CLOUD early to ensure all libraries pick it up
os.environ["OS_CLOUD"] = "chameleon"
os.environ["OS_CLOUD_CONFIG_FILE"] = os.path.expanduser("~/.config/openstack/clouds.yaml")

import chi
from chi import context, lease, server, network, keypair
import sys
import uuid

def banner(msg):
    print("#",  "=" * 60)
    print("#", msg)
    print("#", "=" * 60)

# 1. INITIALIZE CONTEXT OUTSIDE JUPYTER
context.version = "1.0"
context.use_site("KVM@TACC")
# context.use_project("CH-817419")

# Verify authentication by listing flavors
print("Verifying authentication by listing flavors...")
try:
    flavors = chi.server.list_flavors()
    print(f"✅ Successfully authenticated! Found {len(flavors)} flavors.")
    for f in flavors[:5]:
        print(f" - {f.name}: {f.vcpus} vCPUs, {f.ram} MB RAM, {f.disk} GB Disk")
except Exception as e:
    print(f"Authentication check failed: {e}")
    traceback.print_exc()
    sys.exit(1)

banner("flavor done ")

# Set your Chameleon project ID (Replace with your actual CH-XXXXXX project)
# These are now handled by the cloud configuration in clouds.yaml
# context.use_project("CH-817419")
# context.use_site("KVM@TACC")

# Define unique resource names
username = "gregor"
exp_name = "ssh_vm_demo"
server_name = f"{exp_name}-{username}-{uuid.uuid4().hex[:8]}"
lease_name = f"{exp_name}-{username}-{uuid.uuid4().hex[:8]}"
key_name = "gregor-test"

# Ensure keypair exists
print(f"Ensuring keypair '{key_name}' exists...")
try:
    # python-chi Keypair handles creation/retrieval automatically in __init__
    pub_key_path = os.path.expanduser("~/.ssh/id_rsa.pub")
    key = keypair.Keypair(keypair_public_key=pub_key_path)
    print(f"✅ Keypair {key.key_name} is ready")
except Exception as e:
    print(f"Keypair setup failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# 2. Reserve a KVM flavor resource for 6 hours
print("Creating resource lease...")
l = lease.Lease(lease_name, duration=datetime.timedelta(hours=6))
l.add_flavor_reservation(id=chi.server.get_flavor_id("m1.small"), amount=1)
l.submit(idempotent=True)

# 3. Launch the virtual machine instance
print("Launching server instance...")
image_name = "CC-Ubuntu24.04"

s = server.Server(
    name=server_name,
    image_name=image_name,
    flavor_name=l.get_reserved_flavors()[0].name,
    key_name=key.key_name
)
s.submit(idempotent=True, show="text")

# Wait until the instance is active
s.wait()

# 4. Associate a public Floating IP address
print("Associating a floating IP (polling for ready port)...")
fip_addr = None
for i in range(10):
    try:
        fip_addr = s.associate_floating_ip()
        print(f"✅ Floating IP associated: {fip_addr}")
        break
    except chi.exception.ResourceError as e:
        if "None of the ports can route" in str(e):
            print(f"  Port not ready yet, retrying in 3s... ({i+1}/10)")
            time.sleep(3)
        else:
            raise e
else:
    raise chi.exception.ResourceError("Timed out waiting for network ports to route Floating IP")

s.refresh()

# 5. Open Port 22 (SSH) in Security Groups
print("Configuring security groups for SSH...")
sg_list = network.list_security_groups(name_filter="allow-ssh")
if sg_list:
    sg = sg_list[0]
else:
    sg = network.SecurityGroup({
        "name": "allow-ssh",
        "description": "Enable SSH traffic on TCP port 22"
    })
    sg.add_rule("ingress", "tcp", 22)
    sg.submit()

# Attach security group to the server instance
s.add_security_group(sg.id)

# 6. Print the final IP address to use for SSHing
print(f"\nVM is ready! You can SSH in using:")
print(f"ssh cc@{fip_addr}")
