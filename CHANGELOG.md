# Changelog

## [1.2.0] - 2026-09-18

### Added
- **Architectural Refinement**:
    - Implemented typed configuration models using Python dataclasses for improved type safety and IDE support.
    - Introduced a `ProviderFactory` with a registry pattern to decouple the CLI from specific provider implementations.
    - Created a `StateManager` to handle persistent state separately from static configuration.
- **UX Enhancements**:
    - **Contextual Memory**: Added `last_vm` tracking, allowing lifecycle commands (`stop`, `delete`, etc.) to target the most recent VM without specifying `--name`.
    - **Global Cloud Override**: Added a `--cloud` flag to the `vm` command group for one-off provider overrides.
- **Feature Expansion**:
    - **Resource Discovery**: Added `cmc vm flavors`, `cmc vm keys`, and `cmc vm security-groups` to explore cloud resources.
    - **SSH Configuration**: Added `cmc vm ssh-config` to suggest `~/.ssh/config` entries for existing VMs.
- **Documentation**: Updated README and MkDocs with new feature guides and CLI examples.

## [1.1.0] - 2026-09-18

### Added
- **Engineering Robustness**: Implemented a structured custom exception hierarchy (`CloudMeshError` $\rightarrow$ `ProviderError`) and a centralized logging framework to replace generic print statements.
- **Comprehensive Documentation**: Established an extensible documentation system using MkDocs and the Material theme.
    - Detailed guides for Local, OpenStack, and Hyperscaler providers.
    - Full CLI reference with usage examples.
    - Architecture overview explaining the Provider Pattern.
- **CI/CD Automation**: Added GitHub Actions workflow for automatic publishing of documentation to GitHub Pages.
- **Documentation Infrastructure**: Created `requirements-docs.txt` and `mkdocs.yml` aligned with Cloudmesh AI organizational standards.

### Changed
- **LibcloudManager**: Refactored to use the new logging system and custom exception hierarchy for better error reporting.

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
