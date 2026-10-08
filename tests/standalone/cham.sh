#!/bin/bash
# cham.sh - Shell script version of cham.py for debugging
# Use: ./cham.sh [options]

set -e

# Defaults
CLOUD="chameleon"
VM_NAME="gregor-chameleon-vm"
LEASE_NAME="kvm-flavor-lease"
DURATION=1
COUNT=1
IMAGE="CC-Ubuntu22.04"
FLAVOR="m1.medium"
NETWORK="sharednet1"
SECGROUP="default"
KEYPAIR="chameleon-tmp-key"
KEYFILE="$HOME/.ssh/id_rsa.pub"
USER="cc"
EXT_NET="public"

# Allow overrides via environment variables
CLOUD=${CLOUD:-$CLOUD}
VM_NAME=${VM_NAME:-$VM_NAME}

export OS_CLOUD=$CLOUD
echo "Using cloud: $OS_CLOUD"

# --- Step 0: Auth and Endpoints ---
echo "--- Step 0: Getting Token and Blazar URL ---"
TOKEN=$(openstack token issue -f value -c id)

# Search the catalog for a reservation or blazar endpoint
# We use a more cautious jq filter to avoid null iteration errors
BLAZAR_URL=$(openstack catalog list -f json | jq -r '.[].endpoints[]? | select(.url != null) | select(.url | contains("reservation") or contains("blazar"))' | head -n 1 | sed 's#/$##')

if [ -z "$BLAZAR_URL" ]; then
    echo "Unable to find Blazar URL via catalog. Using verified TACC endpoint..."
    BLAZAR_URL="https://kvm.tacc.chameleoncloud.org:1234/v1"
fi

if [ -z "$TOKEN" ]; then
    echo "Failed to get token"
    exit 1
fi
echo "Blazar URL: $BLAZAR_URL"

# Add a short random suffix to VM name
if command -v uuidgen >/dev/null 2>&1; then
    VM_NAME="${VM_NAME}-$(uuidgen | tr -d '-' | cut -c1-8)"
else
    VM_NAME="${VM_NAME}-$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 8)"
fi

echo "--- Step 1: Create Flavor Lease ---"
# Create lease and capture ID
LEASE_NAME_UNIQUE="${LEASE_NAME}-$(date +%Y%m%d-%H%M%S)"
END_DATE=$(date -u -v+${DURATION}H +"%Y-%m-%d %H:%M")

# Resolve flavor name to ID for the API call
FLAVOR_ID=$(openstack flavor show "$FLAVOR" -f value -c id)

echo "Command: curl -X POST $BLAZAR_URL/leases -H \"X-Auth-Token: $TOKEN\" -H \"Content-Type: application/json\" -d '{\"name\": \"$LEASE_NAME_UNIQUE\", \"start_date\": \"now\", \"end_date\": \"$END_DATE\", \"reservations\": [{\"resource_type\": \"flavor:instance\", \"flavor_id\": \"$FLAVOR_ID\", \"amount\": $COUNT}]}'"

LEASE_RESPONSE=$(curl -s -X POST "$BLAZAR_URL/leases" \
    -H "X-Auth-Token: $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"$LEASE_NAME_UNIQUE\",
        \"start_date\": \"now\",
        \"end_date\": \"$END_DATE\",
        \"reservations\": [
            {
                \"resource_type\": \"flavor:instance\",
                \"flavor_id\": \"$FLAVOR_ID\",
                \"amount\": $COUNT,
                \"affinity\": null
            }
        ]
    }")

if [[ -z "$LEASE_RESPONSE" ]]; then
    echo "Lease creation failed: No response from server"
    exit 1
fi

if ! echo "$LEASE_RESPONSE" | jq -e . >/dev/null 2>&1; then
    echo "Lease creation failed: Server returned non-JSON response"
    echo "Response: $LEASE_RESPONSE"
    exit 1
fi

LEASE_ID=$(echo "$LEASE_RESPONSE" | jq -r '.lease.id // empty')

if [ -z "$LEASE_ID" ]; then
    echo "Lease creation failed: No lease ID in response"
    echo "Response: $LEASE_RESPONSE"
    exit 1
fi
echo "Lease ID: $LEASE_ID"

echo "--- Step 2: Wait for Lease to be ACTIVE ---"
while true; do
    LEASE_JSON=$(curl -s -X GET "$BLAZAR_URL/leases/$LEASE_ID" -H "X-Auth-Token: $TOKEN")
    STATUS=$(echo "$LEASE_JSON" | jq -r '.lease.status // empty' | tr '[:lower:]' '[:upper:]')
    echo "Current status: $STATUS"
    if [ "$STATUS" == "ACTIVE" ]; then
        break
    elif [[ "$STATUS" =~ (ERROR|FAILED|TERMINATED|DELETED) ]]; then
        echo "Lease entered terminal state: $STATUS"
        exit 1
    fi
    sleep 10
done

echo "--- Step 3: Find Reserved Flavor ---"
LEASE_JSON=$(curl -s -X GET "$BLAZAR_URL/leases/$LEASE_ID" -H "X-Auth-Token: $TOKEN")
RES_ID=$(echo "$LEASE_JSON" | jq -r '.lease.reservations[0].id // empty')
# Reserved flavors are named "reservation:<res_id>"
# openstack flavor list does not have a --name filter; we grep the list instead.
RESERVED_FLAVOR=$(openstack flavor list -f value -c name | grep "reservation:$RES_ID")
echo "Reserved Flavor: $RESERVED_FLAVOR"
echo "Reservation ID: $RES_ID"


echo "--- Step 4: Ensure Keypair ---"
if ! openstack keypair show "$KEYPAIR" >/dev/null 2>&1; then
    echo "Command: openstack keypair create --public-key $KEYFILE $KEYPAIR"
    openstack keypair create --public-key "$KEYFILE" "$KEYPAIR"
else
    echo "Keypair $KEYPAIR already exists."
fi

echo "--- Step 5: Ensure Security Group Rule ---"
echo "Command: openstack security group rule create --protocol tcp --dst-port 22 --remote-ip 0.0.0.0/0 $SECGROUP"
# Ignore error if rule already exists
openstack security group rule create --protocol tcp --dst-port 22 --remote-ip 0.0.0.0/0 "$SECGROUP" || echo "Rule might already exist"

echo "--- Step 6: Allocate Floating IP ---"
# Try to find an existing DOWN floating IP first
FIP_ADDR=$(openstack floating ip list --status DOWN -f value -c floating_ip_address | head -n 1)
if [ -n "$FIP_ADDR" ]; then
    echo "Reusing existing FIP: $FIP_ADDR"
else
    echo "Command: openstack floating ip create $EXT_NET"
    FIP_ADDR=$(openstack floating ip create "$EXT_NET" -f value -c floating_ip_address)
    echo "Allocated FIP: $FIP_ADDR"
fi

echo "--- Step 7: Boot Server ---"
echo "Command: openstack server create --flavor $RESERVED_FLAVOR --image $IMAGE --network $NETWORK --security-group $SECGROUP --key-name $KEYPAIR --property reservation=$RES_ID $VM_NAME"
SERVER_ID=$(openstack server create \
    --flavor "$RESERVED_FLAVOR" \
    --image "$IMAGE" \
    --network "$NETWORK" \
    --security-group "$SECGROUP" \
    --key-name "$KEYPAIR" \
    --property reservation="$RES_ID" \
    "$VM_NAME" -f value -c id)
echo "Server ID: $SERVER_ID"

echo "--- Step 8: Wait for Server ACTIVE ---"
openstack server show "$SERVER_ID" # initial check
while true; do
    STATUS=$(openstack server show "$SERVER_ID" -f value -c status)
    echo "Server status: $STATUS"
    if [ "$STATUS" == "ACTIVE" ]; then
        break
    elif [ "$STATUS" == "ERROR" ]; then
        echo "Server entered ERROR state"
        exit 1
    fi
    sleep 10
done

echo "--- Step 9: Attach Floating IP ---"
echo "Command: openstack server add floating ip $SERVER_ID $FIP_ADDR"
openstack server add floating ip "$SERVER_ID" "$FIP_ADDR"

echo "--- Step 10: Test SSH ---"
echo "Command: ssh -i $HOME/.ssh/id_rsa $USER@$FIP_ADDR 'uname -a'"
echo "Waiting for port 22..."
until nc -z -w 5 "$FIP_ADDR" 22; do
    echo "Still waiting for SSH..."
    sleep 5
done
ssh -i "$HOME/.ssh/id_rsa" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$USER@$FIP_ADDR" "uname -a"

echo "--- Done ---"
echo "VM Name: $VM_NAME"
echo "IP Address: $FIP_ADDR"
echo "SSH: ssh -i $HOME/.ssh/id_rsa $USER@$FIP_ADDR"
