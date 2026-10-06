# Changelog

## [1.6.0] - 2026-10-05

### Added
- **Secret Masking**: Implemented a pattern-based redaction utility in `providers_utils.py` to mask sensitive data (tokens, passwords, API keys) in CLI error messages.
- **WSL2 Portability**: Enhanced `Wsl2Manager` to automatically detect the most compatible binary (`wsl.exe` or `wsl`) for seamless operation across Windows CMD, PowerShell, Git Bash, and WSL-native environments.
- **Documentation**: Updated the VM Management Manual to document the new WSL2 environment support.

### Fixed
- **Security Leakage**: Integrated secret masking into `OpenstackManager` to prevent credential exposure in `stderr` logs.
- **Git Tracking**: Removed `cache-username.yaml` from version control and added it to `.gitignore`.

## [1.5.0] - 2026-10-02

### Added
- **Advanced Hostname Resolution**: Implemented regex-based VM identification, allowing users to target groups of VMs using wildcards (e.g., `web-*`) or regular expressions.
- **Hostlist Expansion**: Fixed and implemented the `Hostlist` expansion logic, enabling the use of range patterns like `node[1-3]` to target multiple VMs.
- **VM Existence Validation**: Added a pre-start check to `cmx vm start` that prevents attempting to launch a VM if the name already exists in the provider.
- **Expanded Documentation**: Completed the CLI Reference, Manual, and Provider guides, including new documentation for the Lima provider and a general OpenStack overview.
- **Improved UX**: Renamed "Pro Tips" to "Tips" and updated the documentation navigation for better discoverability.

### Changed
- **Symlink Infrastructure**: Migrated `docs/CHANGELOG.md` and `docs/readme.md` to relative symbolic links to ensure compatibility with CI/CD environments.

## [1.3.0] - 2026-09-18

### Added
- **New CLI Command**: Implemented `cmc vm image` to list available images for the active cloud provider.
- **Cloud Defaults**: Added recommended default images, flavors, and regions for Jetstream and Chameleon Cloud in sample and local configurations.
- **VM Information**: Introduced `info()` method to retrieve detailed VM metadata (ID, State, IPs, RAM, CPUs) across all providers.
- **Provider Validation**: Added `check_requirements()` to unify how the CLI detects if a provider is supported on the current host system.
- **Command Execution**: Added `run_command()` abstract method to the provider interface for remote command execution.

### Fixed
- **OpenStack Resource Visibility**: Resolved an issue where `apache-libcloud` returned empty lists for non-public images and flavors; implemented a robust fallback to the `openstack` CLI for these resources.

### Changed
- **Provider Table**: Changed the "Enabled" status indicator from a yellow dot to a white dot for providers with missing configuration.
- **CLI Output**: Removed debug messages from `cmc vm provider`.
- **OpenStack Driver**: Enhanced `OpenstackManager` to dynamically retrieve and apply the `region` from `~/.config/openstack/clouds.yaml`.
- **Libcloud Initialization**: Modified `LibcloudManager` to avoid hard failures during driver initialization when performing requirement checks.

## [1.2.1] - 2026-09-18

### Fixed
- **Configuration Access**: Resolved a systemic bug where VM managers failed to handle both `dict` and `GlobalConfig` objects; implemented `get_cloud_config` helper in `CloudBaseManager` to unify access.
- **Test Robustness**:
    - Fixed `MagicMock` leakage in `LimaManager` tests that caused incorrect command string assertions.
    - Resolved `test_hello` failure by implementing the missing `hello` CLI command.
    - Corrected exception type expectations in `LibcloudManager` tests.
    - Added pre-start cleanup to Multipass smoke tests to prevent failures when VMs already exist.

### Changed
- **Test Architecture**: Reorganized tests into `tests/unit` and `tests/smoke` directories to separate fast unit tests from slow, environment-dependent smoke tests.

## [1.2.0] - 2026-09-18

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
    - `cmx vm login`: Connect to VMs.
    - `cmx vm reservation`: Hardware lease management for Chameleon Cloud (supports explicit dates or `--duration`).
- **Testing**: Created comprehensive `pytest` suites for all providers using `unittest.mock`.

### Changed
- Updated `README.md` to document new providers, configuration options, and CLI usage.

### Fixed
- Resolved syntax errors in `LibcloudManager` related to method implementation and abstract class requirements.
