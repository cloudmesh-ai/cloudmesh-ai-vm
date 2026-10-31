# Plan to Extend **`cmx vm doctor`** with Full Configuration Validation

**Purpose** – The `cmx vm doctor` command currently performs a lightweight health‑check for the *active* provider:

* Resolves the provider.
* Checks local tool requirements.
* Calls the provider's `validate_config()` method (which only validates that the provider‑specific configuration keys are present).
* Optionally prints provider information.

The smoke test `tests/smoke/test_config.py` performs a *much* broader validation of **both** the Cloudmesh (`~/.config/cloudmesh/clouds.yaml`) and OpenStack (`~/.config/openstack/clouds.yaml`) configuration files.  It verifies:

1. File existence.
2. YAML parsability with line/column diagnostics.
3. Presence of a top‑level `username` field.
4. Required top‑level `clouds` mapping.
5. Provider‑specific mandatory keys for all Cloudmesh providers (multipass, lima, jetstream, chameleon, …).
6. Additional logical checks such as a region field for Chameleon.
7. Full OpenStack provider structure (auth sub‑maps, required keys for each cloud, Jetstream‑specific validation, etc.).

The goal of this plan is to **integrate** the extensive checks from `test_config.py` into the `cmx vm doctor` command so that a user can obtain a complete configuration health‑report with a single CLI invocation.

---

## 1. Gap Analysis
| Aspect | `cmx vm doctor` | `tests/smoke/test_config.py` |
|--------|----------------|-----------------------------|
| File existence checks | No | Yes |
| YAML parsing with detailed error location | No (only provider‑specific `validate_config`) | Yes |
| Cloudmesh top‑level `username` validation | No | Yes |
| Generic `clouds` mapping validation | No | Yes |
| Per‑provider required key validation (multipass, lima, jetstream, chameleon, …) | Only provider‑specific `validate_config` (often empty) | Yes |
| OpenStack `clouds.yaml` structural validation (auth sub‑maps, required fields) | Limited to provider‑specific `validate_config` | Yes |
| Human‑readable summary of each check | Yes (table) | No (pytest assertions) |

**Result:** The `doctor` command needs a new validation layer that mirrors the logic from `test_config.py` but produces output compatible with the existing Rich table format.

---

## 2. High‑Level Objectives
1. **Add a reusable validation library** (`cloudmesh/ai/vm/diagnostics/config_validator.py`) that implements the same checks as `tests/smoke/test_config.py` but returns structured results (PASS/FAIL/WARN + details).
2. **Extend the `doctor` CLI** (`src/cloudmesh/ai/command/vm/doctor.py`) to invoke this library and display its results as additional rows in the existing table.
3. **Expose a flag** (`--config`) to enable the extended checks (default behaviour stays lightweight for backward compatibility).
4. **Update documentation** (README, docs/cli.md, docs/readme.md) to describe the new flag and the richer output.
5. **Add unit tests** (`tests/unit/test_doctor_extended.py`) that verify the new rows appear with the correct status for both a healthy and a broken configuration.
6. **Ensure CI** runs the full test suite (`pytest -q`) and that the `doctor` command still exits with the appropriate status code (0 on full pass, non‑zero when `--strict` is supplied and any check fails).

---

## 3. Detailed Implementation Steps
### 3.1. Create Validation Helper
* **File:** `src/cloudmesh/ai/vm/diagnostics/config_validator.py`
* **Functions:**
  * `_load_yaml(path: str) -> tuple[dict | None, str | None]` – identical to the helper in `test_config.py` but returns a tuple `(data, error_msg)` instead of raising, allowing the doctor to capture and format it.
  * `validate_cloudmesh_config() -> dict[str, tuple[str, str]]` – returns a mapping of check name → `(status, details)`.  Checks: existence, parse, username, clouds mapping, per‑provider key sets (use a constant dict of required keys), chameleon region validation.
  * `validate_openstack_config() -> dict[str, tuple[str, str]]` – similar, covering existence, parse, provider‑structure (`_assert_openstack_provider_structure` logic from the smoke test).
  * `run_all_config_checks() -> dict[str, dict]` – aggregates the above, giving a nested dict `{ "Cloudmesh Config": {...}, "OpenStack Config": {...} }`.
* **Dependencies:** `os`, `yaml`, `pathlib`, `typing`.
* **Error handling:** All exceptions caught and reported as `FAIL` with a concise message; parsing errors include line/column info.

### 3.2. Extend the Doctor Command
* **Import** the new helper: `from cloudmesh.ai.vm.diagnostics.config_validator import run_all_config_checks`.
* **Add CLI flag**:
  ```python
   @click.option("--config", is_flag=True, help="Run exhaustive configuration validation (replicates smoke test).")
  ```
* **Logic flow** (inside `doctor` after provider info):
  1. If `full_config` is True, call `run_all_config_checks()`.
  2. Iterate over the resulting sections; for each sub‑check add a row:
     ```python
     rows.append(["Cloudmesh Config", _status_label(status), details])
     ```
     (and similarly for OpenStack).
  3. Increment `failures`/`warnings` counters based on the returned status.
* **Status mapping** – reuse `_status_label` for consistency.
* **Exit behavior** – keep existing `--strict` handling: if any failure (including those from the full config checks) and `strict` is set, exit with code 1.

### 3.3. Documentation Updates
 * **README.md** – Add a new subsection under *Environment Diagnostics* describing the `--config` flag and summarising the extra checks.
* **docs/cli.md** – Document the new option with usage examples.
* **docs/readme.md** – Mirror the README update for the GitHub‑Pages documentation.
* Ensure no duplicate sections (use the same wording across files and reference a single source if possible).

### 3.4. Testing Strategy
| Test | Purpose |
|------|---------|
| `tests/unit/test_doctor_extended.py` | Mock missing files / malformed YAML to assert that the doctor prints a `FAIL` row for the appropriate check. |
| `tests/unit/test_doctor_extended.py` (happy path) | Use temporary valid config files (via `tmp_path`) and ensure all rows report `PASS`. |
| `tests/unit/test_doctor_extended.py` (strict mode) | Verify that the command exits with non‑zero when any check fails and `--strict` is supplied. |
| `tests/smoke/test_config.py` | No changes – remain the source of truth for validation logic. |
 | `tests/unit/test_vm_doctor.py` | May need minor adjustments to accommodate the new optional flag (ensure existing tests still pass when `--config` is omitted). |

**Implementation notes:**
* Use `click.testing.CliRunner` (as existing doctest does) to invoke `cmx vm doctor` with the flag.
* Employ `monkeypatch` to point `CLOUDMESH_PATH` and `OPENSTACK_PATH` to temporary files.

### 3.5. CI Integration
* Update the GitHub Actions workflow (if any) to run `pytest -q` – it already does.
* Add a step that runs `cmx vm doctor --config` in a non‑strict mode to ensure the command itself does not raise unexpected exceptions.

### 3.6. Timeline (approx.)
| Day | Activity |
|-----|----------|
| 1   | Create `config_validator.py` with core functions; run unit tests locally. |
| 2   | Extend `doctor.py` – add flag, integrate validator, adjust status handling. |
| 3   | Write unit tests for the new behaviour; ensure existing doctor tests still pass. |
| 4   | Update documentation files; run `mkdocs` build locally to verify formatting. |
| 5   | Run full test suite (`pytest -q`) on both `main` and `dev2` branches, fix any regressions. |
| 6   | Review code, run lint/format checks, commit and push. |
| 7   | Open PR, request review, merge after approval. |

---

## 4. Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing `doctor` output (CI checks on output strings). | Medium – downstream scripts may parse the table. | Keep existing rows unchanged; add new rows after the original checks. |
| Heavy I/O on CI (reading large YAML files). | Low – config files are small. | Limit validation to paths defined by environment variables; fallback to empty dict if files are missing. |
| Duplicate validation logic diverging from `test_config.py`. | High – future changes could become out‑of‑sync. | Implement the helper **once** and use it both in `test_config.py` (import it) and in `doctor`. This will be a minor refactor of the test file but ensures a single source of truth. |
| New dependencies (`yaml`) not existing in the production environment. | Low – `PyYAML` is already a runtime dependency (used elsewhere). |

---

## 5. Deliverables
- `src/cloudmesh/ai/vm/diagnostics/config_validator.py` – reusable validation library.
 - Updated `src/cloudmesh/ai/command/vm/doctor.py` with `--config` flag and integrated checks.
- Updated documentation (`README.md`, `docs/cli.md`, `docs/readme.md`).
- New unit tests (`tests/unit/test_doctor_extended.py`).
- CI verification that all tests pass and the new flag works.

---

## 6. References
- **Existing doctor implementation:** `src/cloudmesh/ai/command/vm/doctor.py`
- **Current smoke test logic:** `tests/smoke/test_config.py`
- **Provider `validate_config` methods:**
  - `src/cloudmesh/ai/vm/openstack/OpenstackManager.py`
  - `src/cloudmesh/ai/vm/local/LimaManager.py`
  - `src/cloudmesh/ai/vm/oracle/OracleManager.py`
  - `src/cloudmesh/ai/vm/local/VBoxManager.py`
  - `src/cloudmesh/ai/vm/local/Wsl2Manager.py`
- **Documentation locations:** `README.md`, `docs/cli.md`, `docs/readme.md`

---

*Prepared by the Cline AI coding agent on `$(date)`.*/