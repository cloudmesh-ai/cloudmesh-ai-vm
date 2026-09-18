# Configuration

\`cloudmesh-ai-vm\` uses a centralized YAML configuration file located at \`~/.config/cloudmesh/clouds.yaml\`. This file stores your global settings, provider credentials, and the state of your VM counters.

## File Structure

Below is a comprehensive example of a \`clouds.yaml\` file covering all supported providers.

\`\`\`yaml
# Global Settings
username: gregor
counter: 0
default_cloud: multipass
last_vm: gregor0

clouds:
  # --- Local Providers ---
  multipass:
    image: 22.04
    cpus: 2
    memory: 4GiB
    disk: 20GiB

  wsl2:
    distro: Ubuntu-22.04
    ssh_link: true  # Symbolically link host .ssh directory

  vbox:
    image: ubuntu-server-22.04.iso
    memory: 2048
    cpus: 1

  # --- OpenStack Providers ---
  jetstream:
    flavour: m1.small
    image: ubuntu-22.04
    auth: /home/user/.config/jetstream/auth.yaml
    security_group: default

  chameleon:
    flavour: c1.small
    image: rocky-linux-8
    auth: /home/user/.config/chameleon/auth.yaml
    project_name: CH-XXXXXX
    site: CHI@TACC

  # --- Hyperscalers (libcloud) ---
  aws:
    access_key: AKIA...
    secret_key: wJal...
    region: us-east-1
    image: ami-0c55b159cbfafe1f0
    size: t2.micro

  azure:
    tenant_id: xxxx-xxxx-xxxx
    subscription_id: xxxx-xxxx-xxxx
    client_id: xxxx-xxxx-xxxx
    client_secret: xxxx-xxxx-xxxx
    image: ubuntu-22.04
    size: Standard_DS1_v2

  google:
    project_id: my-gcp-project
    private_key: /home/user/.config/google/service-account.json
    image: ubuntu-2204-lts
    size: n1-standard-1
\`\`\`

## Field Descriptions

### Global Fields

- \`username\`: Used as a prefix for automatically generated VM names (e.g., \`gregor0\`).
- \`counter\`: Tracks the number of VMs started. Incremented automatically on every \`cmc vm start\` without a name.
- \`default_cloud\`: The provider used when no specific cloud is mentioned.
- \`last_vm\`: Tracks the name of the last VM successfully started. This allows lifecycle commands (stop, delete, etc.) to target the VM without specifying \`--name\`.

### Provider-Specific Fields

- \`auth\`: Path to a YAML file containing credentials (used by OpenStack).
- \`image\`: The OS image identifier for the specific provider.
- \`size\` / \`flavour\`: The hardware profile (CPU/RAM) for the VM.
