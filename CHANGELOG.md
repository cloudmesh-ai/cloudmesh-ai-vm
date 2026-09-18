# Changelog

## [1.0.0] - 2026-09-18

### Added
- **Core Architecture**: Implemented Provider Pattern using `CloudBaseManager` (ABC) to unify VM management across multiple providers.
- **Local Providers**:
    - `MultipassManager`: Full lifecycle support with custom resource configuration.
    - `Wsl2Manager`: Support for distribution management and SSH key linking.
    - `VBoxManager`: Headless VM management via `VBoxManage`.
- **OpenStack Providers**:
    - `OpenstackManager`: Base class for OpenStack operations using `libcloud`.
    - `JetstreamManager`: Implementation for Jetstream cloud.
    - `ChameleonManager`: Implementation for Chameleon Cloud, including a specialized `reservation` (lease) system via `python-chi`.
- **Hyperscaler Providers**:
    - `LibcloudManager`: Generic base for libcloud-supported hyperscalers.
    - `AwsManager`: Integration for Amazon EC2.
    - `AzureManager`: Integration for Azure VMs.
    - `GoogleManager`: Integration for Google Compute Engine.
- **CLI Tool**: Developed the `cmc` command-line interface using `click`.
    - `cmc vm set`: Change default cloud provider.
    - `cmc vm start`: Launch a VM with automatic naming.
    - `cmc vm stop/delete/suspend/restart`: VM lifecycle management.
    - `cmc vm list`: List VMs in Table, JSON, YAML, or CSV formats.
    - `cmc vm login`: Connect to VMs.
    - `cmc vm reservation`: Hardware lease management for Chameleon Cloud (supports explicit dates or `--duration`).
- **Testing**: Created comprehensive `pytest` suites for all providers using `unittest.mock`.

### Changed
- Updated `README.md` to document new providers, configuration options, and CLI usage.

### Fixed
- Resolved syntax errors in `LibcloudManager` related to method implementation and abstract class requirements.
