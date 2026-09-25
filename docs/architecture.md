# Architecture

`cloudmesh-ai-vm` is built on the **Provider Pattern**, ensuring that the core CLI logic is completely decoupled from the specific implementation details of any cloud provider.

## The Provider Hierarchy

The system uses a multi-layered inheritance structure to maximize code reuse.

### 1. CloudBaseManager (ABC)

The `CloudBaseManager` is an Abstract Base Class (ABC) that defines the "contract" for all providers. It ensures that every manager implements a consistent set of methods:

- `start()`, `stop()`, `delete()`, `list()`, `login()`, `suspend()`, `restart()`
- `get_flavors()`, `get_keys()`, and security group management (`get_security_groups()`, `create_security_group()`, etc.)

### 2. LibcloudManager (Intermediate Base)

Because many clouds (AWS, Azure, Google, and some OpenStack) are supported by the `libcloud` library, we use `LibcloudManager` to implement the generic logic for these providers. This prevents us from writing the same `stop` or `list` logic multiple times.

### 3. Concrete Providers

Concrete classes (e.g., `AwsManager`, `MultipassManager`) inherit from either `LibcloudManager` or `CloudBaseManager`. Their primary responsibility is:

- **Authentication**: Implementing `_get_driver()` to handle API keys and credentials.
- **Specialization**: Implementing provider-specific features (like Chameleon's reservations).

## Command Structure & Discovery

The CLI utilizes a **Recursive File-System-Based Loader**. Instead of a static command registry, the tool dynamically scans the `src/cloudmesh/ai/command/vm/` directory:

- **Files** (e.g., `start.py`) are automatically registered as commands.
- **Folders** (e.g., `config/`) are registered as command subgroups.

This design physically prevents naming collisions and allows the CLI to scale effortlessly as new commands are added.

## Data Flow

1. **CLI Entry Point (`vm_group`)**: Initializes the `VMContext` (handling `--cloud` overrides and `--interactive` mode).
2. **Dynamic Loading**: The recursive loader maps the user's input to the corresponding command module.
3. **Contextual Resolution**: The command resolves the active provider using the `state` proxy and the `VMContext`.
4. **Provider Execution**: The command calls the appropriate method on the Provider class (e.g., `provider.start()`).
5. **State Update**: Upon success, the CLI updates the `clouds.yaml` state (e.g., incrementing the VM counter or updating `last_vm`).
6. **Output Rendering**: The result is formatted using `rich` and displayed to the user.

## Extensibility

To add a new command:
1. Create a new `.py` file in `src/cloudmesh/ai/command/vm/`.
2. Define a `click` command and export it as `cmd`.

To add a new provider:
1. Create a new class inheriting from `CloudBaseManager` (or `LibcloudManager`).
2. Implement the required abstract methods.
3. Add the provider mapping to the provider factory.
