import datetime
import os
import sys
import time
import traceback
import uuid

from chi_auth import authenticate_chi_from_cloud
import chi
from chi import keypair, lease, network, server


def banner(msg):
    print("#", "=" * 60)
    print("#", msg)
    print("#", "=" * 60)


# 1. INITIALIZE CHI CONTEXT via clouds.yaml shim
# Use the standard OS_CLOUD environment variable, or default to 'chameleon'
CLOUD_NAME = os.getenv("OS_CLOUD", "chameleon")
print(f"Authenticating using cloud: {CLOUD_NAME}...")

try:
    authenticate_chi_from_cloud(CLOUD_NAME)
except Exception as e:
    print(f"Authentication shim failed: {e}")
    sys.exit(1)

# Set site directly
chi.context.use_site("KVM@TACC")

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

banner("flavor done")

# Define unique resource names
username = "gregor"
exp_name = "ssh_vm_yaml_test"
server_name = f"{exp_name}-{username}-{uuid.uuid4().hex[:8]}"
lease_name = f"{exp_name}-{username}-{uuid.uuid4().hex[:8]}"
key_name = "gregor-test"

# 2. ENSURE KEYPAIR EXISTS
print(f"Ensuring keypair '{key_name}' exists...")
try:
    key_filename = os.path.expanduser("~/.ssh/id_rsa.pub")

    print()
    print(f"Public key path: {key_filename}")
    print(f"Public key name: {key_name}")
    print()

    key = keypair.Keypair(keypair_public_key=key_filename, key_name=key_name)

    print(f"✅ Keypair {key.key_name} is ready")
except Exception as e:
    print(f"Keypair setup failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# 3. RESERVE A KVM FLAVOR RESOURCE FOR 6 HOURS
print("Creating resource lease...")
l = lease.Lease(lease_name, duration=datetime.timedelta(hours=6))
l.add_flavor_reservation(id=chi.server.get_flavor_id("m1.small"), amount=1)
l.submit(idempotent=True)

# 4. LAUNCH THE VIRTUAL MACHINE INSTANCE
print("Launching server instance...")
image_name = "CC-Ubuntu24.04"

s = server.Server(
    name=server_name,
    image_name=image_name,
    flavor_name=l.get_reserved_flavors()[0].name,
    key_name=key.key_name,
)
s.submit(idempotent=True, show="text")

# Wait until instance is active
s.wait()

# 5. ASSOCIATE A PUBLIC FLOATING IP ADDRESS
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
    raise chi.exception.ResourceError(
        "Timed out waiting for network ports to route Floating IP"
    )

s.refresh()

# 6. OPEN PORT 22 (SSH) IN SECURITY GROUPS
print("Configuring security groups for SSH...")
sg_list = network.list_security_groups(name_filter="allow-ssh")
if sg_list:
    sg = sg_list[0]
else:
    sg = network.SecurityGroup(
        {"name": "allow-ssh", "description": "Enable SSH traffic on TCP port 22"}
    )
    sg.add_rule("ingress", "tcp", 22)
    sg.submit()

# Attach security group to the server instance
s.add_security_group(sg.id)

# 7. PRINT SSH CONNECTION DETAILS

print(f"\nVM is ready! You can SSH in using:")
print(f"ssh cc@{fip_addr}")

