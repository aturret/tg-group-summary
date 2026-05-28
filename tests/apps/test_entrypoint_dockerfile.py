from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_entrypoint_dockerfile_syncs_entrypoint_workspace_package():
    dockerfile = (PROJECT_ROOT / "apps/entrypoint/Dockerfile").read_text()

    assert "uv sync --frozen --no-dev --package tg-group-summary-entrypoint" in dockerfile
