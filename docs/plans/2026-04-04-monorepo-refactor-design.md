# Monorepo Refactor Design

## Context

The tg-group-summary project is a single-package Python application that fetches Telegram group messages from DynamoDB, generates AI summaries via Gemini/GPT, and sends them back to Telegram. It needs to be restructured as a uv workspace monorepo so the core logic can be shared across multiple apps while each app maintains its own entry point and Dockerfile.

## Target Structure

```
tg-group-summary/
├── pyproject.toml                    # workspace root only
├── uv.lock                           # single lockfile
├── packages/
│   └── tg-summary-core/
│       ├── pyproject.toml            # package=true, all deps
│       └── src/
│           └── tg_summary_core/
│               ├── __init__.py
│               ├── report/
│               │   ├── __init__.py
│               │   ├── gemini.py
│               │   ├── gpt.py
│               │   ├── prompt.py
│               │   └── text_cat.py
│               └── utils/
│                   ├── __init__.py
│                   ├── aws.py
│                   └── common.py
├── apps/
│   └── entrypoint/
│       ├── pyproject.toml            # depends on tg-summary-core
│       ├── main.py
│       └── Dockerfile
├── conf/
│   └── prompt.yaml
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## Key Decisions

1. **uv workspace** with `members = ["packages/*", "apps/*"]` and a single root lockfile.
2. **src layout** for the shared package (`packages/tg-summary-core/src/tg_summary_core/`).
3. **Package name**: `tg-summary-core`. Import as `tg_summary_core`.
4. **Config path**: `prompt.py` reads `PROMPT_YAML_PATH` env var, defaults to `conf/prompt.yaml`.
5. **Dockerfile** lives at `apps/entrypoint/Dockerfile`, build context is repo root.
6. **CI/CD** updated to use new Dockerfile path and repo-root build context.

## Component Details

### Root pyproject.toml
- Workspace definition only, no dependencies.
- `[tool.uv.workspace] members = ["packages/*", "apps/*"]`

### packages/tg-summary-core
- Contains all library code (report/, utils/).
- Owns all external dependencies: openai, boto3, requests, Pillow, google-genai, pyyaml.
- `package = true`, hatchling build backend.
- Imports change: `app.report.X` → `tg_summary_core.report.X`, `app.utils.X` → `tg_summary_core.utils.X`.
- `prompt.py` updated to read `os.environ.get("PROMPT_YAML_PATH", "conf/prompt.yaml")`.

### apps/entrypoint
- Thin app: only `main.py` and `pyproject.toml`.
- Single dependency: `tg-summary-core` as workspace source.
- `package = false`.
- `main.py` is the current `app/main.py` with updated imports.

### Dockerfile (apps/entrypoint/Dockerfile)
- Build context: repo root (to access packages/).
- Installs workspace deps via `uv sync` from root.
- Copies `packages/`, `apps/entrypoint/`, `conf/`.
- Sets `PROMPT_YAML_PATH=/app/conf/prompt.yaml`.
- CMD: `python apps/entrypoint/main.py`.

### docker-compose.yml
- `build.context: .`, `build.dockerfile: apps/entrypoint/Dockerfile`.
- Volume mount: `./conf/prompt.yaml:/app/conf/prompt.yaml:ro`.
- Environment variables unchanged.

### CI/CD (.github/workflows/ci.yml)
- Dockerfile path: `apps/entrypoint/Dockerfile`.
- Build context: `.` (repo root).

## What Does NOT Change
- Business logic, LLM integration, AWS queries, Telegram sending.
- Environment variable contract.
- `conf/prompt.yaml` format and content.
- Docker image runtime behavior.

## Verification
1. `uv sync` succeeds at repo root.
2. `python -c "from tg_summary_core.report.gemini import generate_gemini_response"` imports correctly.
3. `docker build -f apps/entrypoint/Dockerfile .` builds successfully.
4. Container runs and produces the same output as before.
