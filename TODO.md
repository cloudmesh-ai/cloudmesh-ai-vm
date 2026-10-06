# TODO: VM Framework Enhancements

## High Priority (Correctness & Stability)
- [x] **Standardize State Polling**: Implement a `wait_for_status(vm_name, target_status, timeout)` method in `BaseVMProvider` and implement it in OpenStack/Multipass to prevent "race conditions" during start/stop.
- [x] **Implement `get_provider_info`**: Ensure every manager implements this so the `cmx vm provider get` command returns useful version/status data instead of a generic error.
- [x] **Standardize Exception Handling**: Replace mixed use of `RuntimeError`, `ValueError`, and `VMProviderError` with a consistent hierarchy based on `cloudmesh.ai.vm.exceptions`.
- [x] **Implement VM existence checks**: Add a `exists(name)` method to `BaseVMProvider` and use it across all providers before performing operations like `stop` or `delete` to avoid noisy stack traces.

## Medium Priority (Feature Parity)
- [x] **Lifecycle Parity**: Implement `restart`, `reset`, and `suspend` for all cloud-based providers (AWS, Azure, Google, Oracle) to match local provider capabilities.
- [x] **Expand Security Group Support**: Implement `create_security_group` and `add_security_group_rule` for Azure and Google providers.
- [x] **Network Feature Parity**: Implement `assign_floating_ip` and `release_floating_ip` for AWS, Azure, and Google providers.
- [x] **Region Discovery**: Implement `list_regions` for all cloud-based providers to allow users to switch regions via CLI.
- [x] **Key Management Parity**: Implement `upload_key` and `delete_key` consistently across all providers. 
    - *Note: Not supported for local providers (WSL2, VBox, Lima) as they use host-based SSH keys.*
- [ ] NOT NEEDED: **Key Rotation**: Add `rotate_key` to `BaseVMProvider` and implement it for providers that support SSH key updates.

## Low Priority (UX & Polish)
- [ ] **Unified CLI Output**: Standardize the return format of `list()` and `info()` methods across all providers to ensure consistent table rendering in the CLI.
- [ ] **Interactive VM Console**: Implement a `console` command to attach to a VM's serial console where supported (e.g., Multipass, OpenStack).
- [ ] **Enhanced Cost Templates**: Replace the `.md` cost templates with a structured JSON/YAML format that can be parsed by the `get_cost` method for real-time estimation.
- [ ] **Unified IP Abstraction**: Create a `NetworkInterface` class to handle the differences between Floating IPs, Public IPs, and Internal IPs across providers.

## Provider Compliance Suite Enhancements
- [x] **Robust Instantiation & Mocking**: Implement a `MockDriver` factory to replace `MagicMock` and allow actual provider logic to be tested without real API calls.
- [x] **Integration Testing Mode**: Add a `COMPLIANCE_MODE` environment variable to switch between `unit` and `integration` (real cloud) tests.
- [ ] **Compliance Matrix Reporting**: Create a custom report/table showing the compliance status of every provider across all tested features.
- [ ] **Negative & Edge-Case Testing**: Add tests for invalid VM names, invalid configurations, and unauthorized API access.
- [ ] **Strict Interface Validation**: Use the `inspect` module to verify that provider method signatures match `BaseVMProvider` exactly.
- [ ] NOT NEEDED: **Configuration Granularity**: Split the centralized `all_providers.json` into individual config files per provider.

## Governance & Strategic Growth
- [ ] NOT NEEDED AT THIS TIME: **The "Compliance Gate"**: Integrate the compliance suite into CI/CD to block PRs that introduce non-compliant providers.
- [x] **Developer "Onboarding Kit"**: Create a `COMPLIANCE_GUIDE.md` documenting the provider contract and how to implement new compliant providers.
- [ ] **Performance SLAs**: Add timing benchmarks to ensure the `list()` and `info()` methods meet minimum speed requirements.
- [ ] NOT NEEDED: **The "Compliance Badge" in the UI**: Feed compliance results into `PROVIDER_METADATA` to show a "Verified" badge in the CLI.
- [x] **Consistent UX Scenarios**: Implement "Scenario Tests" (e.g., Zero-to-Hero flow) to ensure consistent behavior across clouds.
- [ ] **Security & Hygiene Compliance**: Add checks for credential leakage in logs and resource cleanup (no zombie resources on failure).

## Testing and fixing

In addition to the general code improvements the code also needs to be tested. Each student ought to take at least 2 cloud providers and test the programs in great detail. While automating the test so they can be run repeatedly without effort. The suggestion is to have some file 

test/test-<cloud>-with-credentials.py

That tests the specified cloud .

We have 

* Local Providers
    * Multipass (partially tested)
    * Lima (not tested)
    * WSL2 (not tested)
    * VirtualBox (not tested)
* OpenStack Providers
    * Jetstream (partially tested)
    * Chameleon (partially tested)
* Hyperscaler Providers
    * AWS EC2 (not tested)
    * Azure VMs (not tested)
    * Google GCE (not tested)

Try out the commands and record under each of them which work, which does not. Make sure to not just do it from commandline but integrate it into a testing python file. If you are familiar with pytest, you can use that.