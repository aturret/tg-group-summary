# tg-group-summary

Telegram group chat daily summarizer. Fetches messages from DynamoDB, generates AI summaries via Gemini or GPT, and sends them to a Telegram channel.

## Project Structure

This is a **uv workspace monorepo**.

```
tg-group-summary/
├── pyproject.toml                  # workspace root (no deps, defines members)
├── uv.lock                         # single lockfile for the whole workspace
├── packages/
│   └── tg-summary-core/            # shared library package
│       ├── pyproject.toml
│       └── src/tg_summary_core/
│           ├── config.py           # central pydantic-settings config (all env vars)
│           ├── report/
│           │   ├── gemini.py       # Google Gemini API integration
│           │   ├── gpt.py          # OpenAI GPT Responses API integration
│           │   ├── prompt.py       # prompt generation, YAML config loading
│           │   ├── report_generate.py  # service layer: orchestrates fetch → LLM → send
│           │   └── text_cat.py     # DynamoDB message → JSON serialization
│           └── utils/
│               ├── aws.py          # DynamoDB + S3 client (no AWSConfig class)
│               └── common.py       # logging, file I/O, download helpers
├── apps/
│   └── entrypoint/
│       ├── main.py                 # thin entry point — only `if __name__ == "__main__"`
│       ├── pyproject.toml          # depends on tg-summary-core via workspace
│       └── Dockerfile              # build context is repo root
├── conf/
│   └── prompt.yaml                 # optional prompt/declaration overrides
├── docker-compose.yml
├── .github/
│   ├── workflows/
│   │   ├── ci.yml              # lint + test on PRs and pushes to main
│   │   └── release.yml         # Docker build + push to GHCR on push to main
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── pull_request_template.md
├── .codecov.yml
├── .dockerignore
├── .env.example
├── .pre-commit-config.yaml
└── Makefile
```

## Development Setup

```bash
# Install all workspace packages and dependencies
uv sync --all-packages

# Run the entrypoint
uv run python apps/entrypoint/main.py
# or directly via venv
.venv/bin/python apps/entrypoint/main.py
```

Do NOT run `uv run .venv/bin/python` — that creates an ephemeral environment and breaks imports.

## Configuration

All environment variables are declared in `packages/tg-summary-core/src/tg_summary_core/config.py` as a single flat `Settings(BaseSettings)` class. The module-level `settings` singleton is imported wherever config is needed.

| Env var | Field | Default | Required |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | `telegram_bot_token` | — | Yes |
| `SUMMARY_CHAT_ID` | `summary_chat_id` | — | Yes |
| `SUMMARY_CHAT_NAME` | `summary_chat_name` | — | Yes |
| `TARGET_CHAT_ID` | `target_chat_id` | — | Yes |
| `DECLARATION` | `declaration` | `""` | No |
| `ADDITIONAL_PROMPT` | `additional_prompt` | `""` | No |
| `GOOGLE_API_KEY` | `google_api_key` | `None` | For Gemini |
| `OPENAI_API_KEY` | `openai_api_key` | `None` | For GPT |
| `OPENAI_GPT_MODEL` | `openai_gpt_model` | `gpt-5` | No |
| `SUMMARY_MODEL` | `summary_model` | `gemini-3-flash-preview` | No |
| `DEFAULT_GEMINI_MODEL` | `default_gemini_model` | `gemini-3.1-pro-preview` | No |
| `DEFAULT_GEMINI_FAST_MODEL` | `default_gemini_fast_model` | `gemini-3.1-flash-lite-preview` | No |
| `region_name` | `region_name` | `us-east-1` | No |
| `s3_bucket_name` | `s3_bucket_name` | `tg-searcher-prod` | No |
| `dynamo_table_name` | `dynamo_table_name` | `tg-searcher-prod` | No |
| `PROMPT_YAML_PATH` | `prompt_yaml_path` | `conf/prompt.yaml` | No |

`settings.target_chat_id_full` automatically prepends `-100` if not already present.

## Key Design Decisions

- **No `AWSConfig` class** — `AWSClient` reads from `settings` directly.
- **Lazy API clients** — `gemini.py` and `gpt.py` use `_get_client()` so importing the module doesn't fail when API keys aren't set.
- **`src/` layout** — the package lives in `packages/tg-summary-core/src/tg_summary_core/`. Import as `tg_summary_core`.
- **`PROMPT_YAML_PATH`** — set to `/app/conf/prompt.yaml` in the Dockerfile; the `conf/` dir is volume-mounted in docker-compose.

## Docker

Build context is always the **repo root**:

```bash
docker build -f apps/entrypoint/Dockerfile .
```

The Dockerfile copies `packages/`, `apps/entrypoint/`, `conf/`, installs deps via `uv sync --frozen --no-dev`, and runs `python apps/entrypoint/main.py`.

## CI/CD

- `.github/workflows/ci.yml` — lint (ruff) + type check (mypy) + test (pytest + Codecov) on PRs and pushes to main.
- `.github/workflows/release.yml` — builds and pushes Docker image to `ghcr.io` on push to `main`.

## Testing

**All newly added code must have unit tests.** Tests live in the `tests/` directory at the repo root.

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ -v --cov=tg_summary_core --cov-report=term-missing

# Run a specific test file
uv run pytest tests/report/test_gemini.py -v
```

- Test directory mirrors the source layout (`tests/report/`, `tests/utils/`)
- External services (AWS, Gemini, OpenAI, Telegram) are mocked — tests never make real API calls
- `moto` for AWS (DynamoDB, S3), `unittest.mock.patch` for AI clients and HTTP calls, `freezegun` for time
- The root `conftest.py` provides an autouse fixture that reloads the `settings` singleton with test env vars
- `tests/report/conftest.py` resets LLM client singletons between tests

## Development Tooling

### Quick Commands (Makefile)

```bash
make install      # Install all deps + pre-commit hooks
make lint         # Run ruff linter
make format       # Auto-format with ruff
make typecheck    # Run mypy
make test         # Run pytest
make test-cov     # Run pytest with coverage report
make check        # Full local CI: lint + format-check + typecheck + test
make pre-commit   # Run all pre-commit hooks
make docker-build # Build Docker image locally
make clean        # Remove caches and coverage files
```

### Linting & Formatting

**Ruff** configured in root `pyproject.toml` under `[tool.ruff]`. Line length: 120. Rules: E, F, I, UP, B, SIM.

### Type Checking

**Mypy** configured in root `pyproject.toml` under `[tool.mypy]`. Currently lenient (`disallow_untyped_defs = false`) — tighten gradually.

### Pre-commit

Install hooks: `make install` or `uv run pre-commit install`. Config: `.pre-commit-config.yaml`.

## Adding a New App

1. Create `apps/<name>/pyproject.toml` with `dependencies = ["tg-summary-core"]` and `tg-summary-core = { workspace = true }` source.
2. Import from `tg_summary_core.*` as needed.
3. Add tests under `tests/apps/<name>/`.
4. Update `known-first-party` in root `pyproject.toml` `[tool.ruff.lint.isort]`.
5. Run `uv sync --all-packages` to update the lockfile.
