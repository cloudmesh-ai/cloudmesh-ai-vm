# Proposal: Regex-Based Hostname Identification

## Goal
Expand the VM targeting system to support wildcards and regular expressions, allowing users to identify and act upon groups of VMs based on naming patterns rather than just explicit names or numeric ranges.

## Current State
The system currently uses `Hostlist.expand()` in `resolve_vms` to handle patterns like `node[1-3]`, which expands to `node1, node2, node3`.

## Proposed Expansion

### 1. New Syntax
Introduce support for wildcard patterns in the `name` argument of VM commands.
- **Wildcards**: Use `*` for zero or more characters and `?` for a single character.
- **Regex**: Support full Python `re` syntax for advanced users.
- **Example**: `cmx vm stop "web-server-*"` matches `web-server-1`, `web-server-prod`, etc.

### 2. Technical Implementation

#### A. Pattern Detection
Modify the resolution logic to distinguish between:
1. **Range-based hostlists**: `name[start-end]` $\rightarrow$ Expanded via existing `Hostlist` logic.
2. **Pattern-based matchers**: Names containing `*`, `?`, or regex anchors $\rightarrow$ Treated as search patterns.
3. **Explicit names**: Single, exact VM names.

#### B. Dynamic Resolution Flow
When a pattern is detected, the system should:
1. **Retrieve Candidate List**: Call `provider.list()` to fetch all VMs currently existing in the active cloud.
2. **Apply Filter**:
   - Convert simple wildcards (`*` $\rightarrow$ `.*`, `?` $\rightarrow$ `.`).
   - Use `re.match()` to filter the candidate list.
3. **Validation**:
   - If matches are found, return the list of names.
   - If no matches are found, raise a `ClickException` informing the user that no VMs matched the pattern.

### 3. Example Workflow
**Command**: `cmx vm run "db-.*" "df -h"`

1. `resolve_vms` detects `db-.*` as a regex pattern.
2. `provider.list()` returns `['db-1', 'db-2', 'web-1', 'app-1']`.
3. Regex `db-.*` filters the list to `['db-1', 'db-2']`.
4. The command is executed sequentially on `db-1` and `db-2`.

## TODOs for Implementation
- [ ] Update `resolve_vms` in `src/cloudmesh/ai/command/vm/_shared/context.py` to handle regex filtering.
- [ ] Implement a helper function to convert glob-style wildcards to regex.
- [ ] Add unit tests for various patterns (exact match, range, wildcard, and regex).
- [ ] Update `docs/cli.md` and `docs/manual.md` to document the new wildcard syntax.
