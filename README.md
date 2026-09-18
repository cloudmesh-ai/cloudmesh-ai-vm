# cloudmesh-ai-vm

`cloudmesh-ai-vm` is a Python-based command-line tool designed to simplify the management of Virtual Machines (VMs) across multiple cloud environments. By providing a unified interface, it abstracts the complexities of different cloud providers, allowing users to start, stop, and manage VMs using a consistent set of commands.

The project supports multiple cloud environments including major hyperscalers (AWS, Azure, Google), OpenStack-based clouds (such as Jetstream and Chameleon), and local virtualization providers (such as Multipass, WSL2, or VirtualBox).

## Features

- **Multi-Cloud Support**: Unified management for AWS, Azure, Google, Jetstream, Chameleon, and local providers.
- **Consistent CLI**: A powerful command-line interface built with `click`.
- **Automated Naming**: Automatic VM naming based on username and an incrementing counter.
- **Configuration Management**: Centralized settings stored in a YAML configuration file.
- **Flexible Output**: VM listing supports multiple formats including Table, JSON, YAML, and CSV.
- **Provider Abstraction**: A pluggable provider architecture using the Provider Pattern and `libcloud`.

## Installation

### Prerequisites

- Python 3.x
- `pip` (Python package manager)

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd cloudmesh-ai-vm
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install the CLI tool:
   ```bash
   pip install .
   ```

## Configuration

The tool uses a configuration file located at `~/.config/cloudmesh/clouds.yaml` to manage default parameters and state.

### Example `clouds.yaml`

```yaml
username: gregor
counter: 0
default_cloud: multipass
clouds:
  # Local Providers
  multipass:
    image: 22.04
    cpus: 2
    memory: 4GiB
    disk: 20GiB
  
  # OpenStack Providers
  jetstream:
    flavour: m1.small
    image: ubuntu-22.04
    security_group: default
    auth: /path/to/jetstream/credentials
  chameleon:
    flavour: c1.small
    image: rocky-linux-8
    auth: /path/to/chameleon/credentials
    project_name: CH-XXXXXX
    site: CHI@TACC

  # Hyperscalers (via Libcloud)
  aws:
    access_key: YOUR_ACCESS_KEY
    secret_key: YOUR_SECRET_KEY
    region: us-east-1
    image: ami-xxxxxx
    size: t2.micro
  azure:
    tenant_id: YOUR_TENANT_ID
    subscription_id: YOUR_SUB_ID
    client_id: YOUR_CLIENT_ID
    client_secret: YOUR_CLIENT_SECRET
    image: ubuntu-22.04
    size: Standard_DS1_v2
  google:
    project_id: YOUR_PROJECT_ID
    private_key: /path/to/service-account.json
    image: ubuntu-2204-lts
    size: n1-standard-1
```

## Usage

The primary entry point is the `cmc` command.

### Cloud Management

- **Set Default Cloud**:
  ```bash
  cmc vm set multipass
  ```
  *(Sets the active provider to multipass, wsl2, vbox, jetstream, chameleon, aws, azure, or google)*

- **Reservation (Chameleon Only)**:
  ```bash
  cmc vm reservation --name my-lease --node-type compute_skylake --count 1
  ```
  *Creates a hardware reservation in Chameleon Cloud using python-chi.*

### VM Lifecycle

- **Start a VM**:
  ```bash
  cmc vm start
  ```
  *Starts a VM using the default name `<username><counter+1>` and increments the counter in `clouds.yaml`.*

- **Start a VM with a Specific Name**:
  ```bash
  cmc vm start --name=my-special-vm
  ```
  *Starts a VM with the provided name; does not increment the counter.*

- **Stop a VM**:
  ```bash
  cmc vm stop [--name=NAME]
  ```

- **Login to a VM**:
  ```bash
  cmc vm login [--name=NAME]
  ```

- **Suspend a VM**:
  ```bash
  cmc vm suspend [--name=NAME]
  ```

- **Restart a VM**:
  ```bash
  cmc vm restart [--name=NAME]
  ```

- **Delete a VM**:
  ```bash
  cmc vm delete [--name=NAME]
  ```

### Inspection

- **List VMs**:
  ```bash
  cmc vm list [--json | --yaml | --csv | --table]
  ```
  *Lists all managed VMs in the desired format.*

## Architecture

The project follows a **Provider Pattern**. The `main.py` CLI layer interacts with a generic `CloudBaseManager` interface, which is implemented by specific manager classes.

### Directory Structure
```text
cloudmesh-ai-vm/
├── src/
│   ├── CloudBaseManager.py       # Abstract Base Class defining the provider interface
│   ├── LibcloudManager.py        # Generic base for libcloud-supported clouds
│   ├── main.py                   # CLI Entry point (using click)
│   ├── openstack/
│   │   ├── OpenstackManager.py   # Base OpenStack functionality
│   │   ├── JetstreamManager.py   # Jetstream implementation
│   │   └── ChameleonManager.py   # Chameleon implementation
│   ├── aws/
│   │   └── AwsManager.py         # AWS implementation
│   ├── azure/
│   │   └── AzureManager.py       # Azure implementation
│   ├── google/
│   │   └── GoogleManager.py      # Google GCE implementation
│   └── local/
│       ├── Wsl2Manager.py        # WSL2 implementation
│       ├── MultipassManager.py   # Multipass implementation
│       └── VBoxManager.py        # VirtualBox implementation
└── ...
```

### Implementation Logic

The tool dynamically loads the provider based on the configuration:
```python
PROVIDERS = {
    "aws": "src.aws.AwsManager.Provider",
    "multipass": "src.local.MultipassManager.Provider",
    # ...
}
```
The `LibcloudManager` class provides a unified implementation for providers that share the `libcloud` API, reducing code duplication across Hyperscaler managers.

## Contributing

This project is a collaborative effort. Contributions are managed via GitHub:

1. **Issue Tracking**: Check the GitHub Issues tab for assigned tasks.
2. **Collaboration**: Use pair programming and GitHub Pull Requests to integrate changes.
3. **Support**: If you fall behind or encounter blockers, reach out to your teammates or ask on Piazza.
