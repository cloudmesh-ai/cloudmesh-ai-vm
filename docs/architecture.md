# Architecture

\`cloudmesh-ai-vm\` is built on the **Provider Pattern**, ensuring that the core CLI logic is completely decoupled from the specific implementation details of any cloud provider.

## The Provider Hierarchy

The system uses a multi-layered inheritance structure to maximize code reuse.

### 1. CloudBaseManager (ABC)

The \`CloudBaseManager\` is an Abstract Base Class (ABC) that defines the "contract" for all providers. It ensures that every manager implements a consistent set of methods:

- \`start()`, \`stop()`, \`delete()`, \`list()`, \`login()`, \`suspend()`, \`restart()\`
- \`get_flavors()`, \`get_keys()`, \`get_security_groups()\`

### 2. LibcloudManager (Intermediate Base)

Because many clouds (AWS, Azure, Google, and some OpenStack) are supported by the \`libcloud\` library, we use \`LibcloudManager\` to implement the generic logic for these providers. This prevents us from writing the same \`stop\` or \`list\` logic multiple times.

### 3. Concrete Providers

Concrete classes (e.g., \`AwsManager\`, \`MultipassManager\`) inherit from either \`LibcloudManager\` or \`CloudBaseManager\`. Their primary responsibility is:

- **Authentication**: Implementing \`_get_driver()\` to handle API keys and credentials.
- **Specialization**: Implementing provider-specific features (like Chameleon's reservations).

## Data Flow

1. **CLI Layer (\`main.py\`)**: Receives a command (e.g., \`vm start\`).
2. **Factory**: Looks up the active cloud in \`clouds.yaml\` and instantiates the corresponding Provider class.
3. **Provider**: Executes the requested operation using the cloud's API (via \`libcloud\` or native tools).
4. **CLI Layer**: Formats the result and displays it to the user.

## Extensibility

To add a new provider:

1. Create a new class inheriting from \`CloudBaseManager\` (or \`LibcloudManager\`).
2. Implement the required abstract methods.
3. Add the provider mapping to the \`PROVIDERS\` registry in \`main.py\`.
