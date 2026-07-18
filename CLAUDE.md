# CLAUDE.md

Coding rules source: `D:\GIT\BenjaminKobjolke\claude-code\coding-rules`

---

# AI Workflow Rules (always apply)

These rules define the end-to-end workflow an AI agent must follow when planning and
implementing changes. Each step is an existing skill referenced by its slash name; run the
skill rather than reimplementing its behavior.

## Feature / Change Workflow

After a plan is proposed and the user approves it, follow this chain. The DRY
gate is a precondition for implementing — not just an earlier step.

```
plan approved
  → /plan:dry            check approved plan for DRY/consolidation BEFORE code
  → /plan:dry-checked    reload + review the DRY-adjusted plan
  → /convention:check    scan for existing patterns/components to reuse
  ─────────────────────  DRY GATE — must be cleared to proceed
  → restate Definition-of-Done aloud
  → implement
  → /dry:check           post-implementation DRY audit (template below)
  → /verify:after-change run tests + code analysis
```

### DRY gate (precondition for implementing)

Do not write a single line until ALL are true. Restate this gate aloud at the
moment you start implementing — if you cannot, the gate is not cleared:

- [ ] `/plan:dry` ran and the plan was adjusted for any duplication found.
- [ ] `/plan:dry-checked` reloaded and confirmed the adjusted plan.
- [ ] `/convention:check` found the existing utilities/patterns to reuse.

The gate survives the `implement` step: if mid-implementation you add a new
helper, type, or pattern the gate would have caught, stop and re-clear it
before continuing.

### Definition of Done — restate aloud before implementing

Before the first edit, state in chat what "done" means for THIS change:

- [ ] Scope: <one line — what changes, what does not>
- [ ] Reuse: <existing function/component this builds on, with path>
- [ ] DRY gate cleared (above)
- [ ] `/dry:check` clean
- [ ] `/verify:after-change` green (tests + analysis)

### Post-implementation DRY audit — paste-in template

Run `/dry:check`, then paste and fill:

```
DRY audit — <change name>
Changed files:     <list>
Duplication found: <none | describe>
Consolidated into: <shared fn/module + path | n/a>
Convention reused: <name + path>
Verdict:           <clean | needs rework>
```

## Bug-Fix Workflow

Bug fixes use a shorter variant (no plan-DRY phase):

```
bugs:fix
  → /verify:after-change
```

---

# Common Rules (all languages)

## Keep CLAUDE.md in Sync

Keep this file's rules current with the coding-rules source folder. Compare and update to
keep rules current and deduplicated.

## Use Objects for Related Values

When multiple related values must be passed between classes or methods, bundle them into a
dedicated object (DTO/Settings/Config) instead of passing many parameters.

## No Bag-of-Keys Returns at Module Boundaries

Public methods on managers/repositories/services that return data across a module boundary
must return a typed object (DTO, value object, domain model) — never a raw dict indexed by
string keys. Raw dicts silently swallow shape bugs.

- Lists vs single must be obvious from type and name: `get_thing() -> Thing | None` vs
  `get_things() -> list[Thing]`. Never overload one return to mean both.
- Distinguish absent from empty: `None` = not found; empty collection = found, but nothing.
- JSON-decoded blobs crossing a boundary get wrapped in a value object too.
- Internal/private helpers may stay dicts.

## Reuse Existing Models Before Inventing New Shapes

Before designing a new return type or DTO, search the codebase for an existing domain class
that already owns the same data. Use it rather than inventing a parallel shape.

## Tests Pin the Shape Before the Refactor

When converting a bag-of-keys return to a typed object, write a characterization test first
that locks current behavior, run it green against unrefactored code, then refactor. The same
test must remain green afterward.

## Test-Driven Development for Features and Bug Fixes

1. Write tests first
2. Run the tests and confirm they fail
3. Implement the change or fix
4. Run the tests again and confirm they pass

## Integration Tests

Include integration tests in addition to unit tests.

## Test Runner Scripts

Provide in `tools/`:

- `tools/run_tests.bat` — runs unit tests
- `tools/run_integration_tests.bat` — runs integration tests

## Prefer Type-Safe Values

Use strong, explicit types (typed DTOs, enums, typed settings) instead of loosely/stringly
typed values, so mistakes are caught early.

## String Constants

Centralize string constants in a dedicated module/class. No raw strings scattered across the
codebase.

## Reusable Tooling

Before building project-specific infrastructure scripts (audits, codemods, build helpers,
lint checks), check the language's `*_setup_files/` folder under the coding-rules repo for an
existing equivalent. If none: build it here, prove it, copy it into
`python_setup_files/tools/`, document it in `PYTHON_RULES.md`.

## README.md is Mandatory

Root `README.md` with: project name/description, installation, usage examples, dependencies.

## Don't Repeat Yourself (DRY)

Extract repeated logic into reusable functions/modules; use constants for repeated values.

## Derive, Don't Duplicate — One Value Owns the Derivation

When one value strictly determines another, pass only the determinant and derive the rest —
never thread both side-by-side through call sites. The richer type owns the relationship via
a cheap, pure, exhaustive mapping (enum + exhaustive match), so illegal combinations are
unconstructable. Don't force a derivation when values are genuinely independent.

## Keep It Simple (KISS)

Simplest solution that works. YAGNI: no interface with one implementation, no factory for one
product, no config for a value that never changes. Boring over clever. Deletion over addition.

## Confirm Dependency Versions

Before adding any new package, confirm the version with the user. Do not assume.

## Error Handling & Logging Strategy

Centralized error handler, not scattered ad-hoc try/except. Structured logging (never
`print`), levels debug/info/warning/error, context in messages (module, operation, IDs).

## Centralized Logger — Single Off Switch

Route all logging through one logger class: **`AppLogger`** in `app_logger.py`. Never call
`print()` or `logging.getLogger(...)` directly in feature code. Built-in logging calls appear
in exactly one file — the logger implementation. One config flag toggles/levels/redirects all
logging without touching call sites.

## Input Validation at Boundaries

Validate at system boundaries (user input, files, external responses). Never trust external
data. Fail fast with clear errors.

## Maximum File Length — 300 Lines

Split files over 300 lines. Group extractions by domain. Exceptions: generated files, config
files, test files with many similar cases.

## Naming Conventions

- Files: `snake_case`
- Classes: `PascalCase`
- Functions/methods/variables: `snake_case` (Python)
- Constants: `UPPER_SNAKE_CASE`

## Comments Explain Why, Not What

Comment intent, workarounds, non-local constraints — not restatements of code. Document each
module/class purpose at its top. Delete stale comments.

## Security Baseline

- Never commit secrets (`.env`, API keys, credentials)
- Escape output; parameterized queries only
- Validate/sanitize all user input at boundaries
- Keep dependencies updated

## No Hardcoded Environment Values

No filesystem paths, hostnames, IPs, ports, or base URLs in code. Read them from the central
config, with a committed `.example` template documenting every key. This is about
portability, not secrecy — a non-secret hostname still belongs in config.

## No God Classes

One responsibility per class. Warning signs: >5 public methods, >4 constructor dependencies,
methods spanning unrelated domains. Split by responsibility. A short class can still be a god
class.

## Self-Describing Classes

When behavior depends on which fields a class has (search, serialization, display,
validation), the class declares those fields via a contract — never hardcode field lists in
consumers. Python: Protocol with e.g. `get_searchable_fields()`, or dataclass `field`
metadata read via `fields(obj)`.

## Inject Collaborators, Don't Fold Dependencies In

Prefer injected collaborator objects over mixins/multiple inheritance that merge all the
helper's dependencies into the host. Never instantiate a service inside a method — pass
collaborators through the constructor so they appear in the contract and can be substituted
in tests. Collapse many one-line config getters into a single config value object.

---

# Python Rules (uv)

## pyproject.toml is the Single Source of Truth

- Python version pinned (e.g. `>=3.11,<3.13`)
- Dependencies via `uv add ...`
- `uv.lock` committed
- Tooling config lives in `pyproject.toml`

## Formatting + Linting + Type Checking

```bash
uv add --dev ruff mypy
```

- Ruff handles lint + formatting (replaces black/isort/flake8)
- MyPy for typing
- CI/checks run: `ruff check`, `ruff format --check`, `mypy`

## Type Hints on Public APIs

All public functions/classes/methods: typed parameters + return types. Use `Sequence`,
`Mapping`, `Protocol`, `TypedDict`, `Literal` where helpful. Avoid `Any` except at I/O or
third-party boundaries.

## Centralized Environment-Driven Settings

No magic values in code. One settings module with env overrides; everything reads from it,
never scattered `os.getenv()` calls:

```py
@dataclass(frozen=True)
class Settings:
    env: str = os.getenv("APP_ENV", "dev")
    debug: bool = os.getenv("DEBUG", "0") == "1"
```

## Tests: Mandatory, Fast, Isolated

pytest (`uv add --dev pytest`). Unit tests for core logic, no network in unit tests, tmp
dirs/fixtures only — no reliance on machine state.

## Use `spec=` with MagicMock

`MagicMock()` without `spec` accepts any attribute, even typos. Always
`MagicMock(spec=RealClass)`. If the real class has a method, mock the method
(`mock.get_body.return_value = ...`), not a fake attribute. Properties via `PropertyMock`.

## Structured Logging

`structlog` or `logging` with JSON formatters — never `print()`. All logging through
**`AppLogger`** (`app_logger.py`); see the common Centralized Logger rule.

## Async Patterns

Use `asyncio` for I/O-bound tasks. No blocking calls (`time.sleep`, sync HTTP) inside async
contexts.

## Validation

Use Pydantic for data validation at boundaries; let it handle type coercion and error
reporting.

## Required Batch Files

- `start.bat` — root, starts the application
- `tools/run_tests.bat` — runs the test suite
