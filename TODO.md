# TODO: VM Framework Enhancements

## High Priority (Correctness & Stability)
(All core stability items implemented)

## Medium Priority (Feature Parity)
 - [ ] NOT NEEDED: **Key Rotation**: Add `rotate_key` to `BaseVMProvider` and implement it for providers that support SSH key updates.
 - [ ] Pre‑flight floating IP reservation with back‑off, jitter and rollback (see TODO-openstack-fip-preflight.md)

## Low Priority (UX & Polish)
11 | - [x] **Unified CLI Output**: Standardize the return format of `list()` and `info()` methods across all providers. Implemented structured JSON parsing for `MultipassManager.info` and ensured `list()` already returns a consistent dict list.
- [ ] **Interactive VM Console**: Implement a `console` command to attach to a VM's serial console where supported (e.g., Multipass, OpenStack).
- [ ] **Enhanced Cost Templates**: Replace the `.md` cost templates with a structured JSON/YAML format that can be parsed by the `get_cost` method for real-time estimation.
- [ ] **Unified IP Abstraction**: Create a `NetworkInterface` class to handle the differences between Floating IPs, Public IPs, and Internal IPs across providers.

## Provider Compliance Suite Enhancements
- [ ] **Compliance Matrix Reporting**: Create a custom report/table showing the compliance status of every provider across all tested features.
- [ ] **Negative & Edge-Case Testing**: Add tests for invalid VM names, invalid configurations, and unauthorized API access.
- [ ] **Strict Interface Validation**: Use the `inspect` module to verify that provider method signatures match `BaseVMProvider` exactly.
- [ ] NOT NEEDED: **Configuration Granularity**: Split the centralized `all_providers.json` into individual config files per provider.

## Governance & Strategic Growth
- [ ] NOT NEEDED AT THIS TIME: **The "Compliance Gate"**: Integrate the compliance suite into CI/CD to block PRs that introduce non-compliant providers.
- [ ] **Performance SLAs**: Add timing benchmarks to ensure the `list()` and `info()` methods meet minimum speed requirements.
- [ ] **Security & Hygiene Compliance**: Add checks for credential leakage in logs and resource cleanup (no zombie resources on failure).
- [ ] NOT NEEDED: **The "Compliance Badge" in the UI**: Feed compliance results into `PROVIDER_METADATA` to show a "Verified" badge in the CLI.

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
