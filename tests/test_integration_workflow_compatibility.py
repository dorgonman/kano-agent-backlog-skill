import os
from pathlib import Path

from typer.testing import CliRunner

from kano_backlog_cli.cli import app

runner = CliRunner()


def _scaffold_product(tmp_path: Path, name: str, prefix: str) -> Path:
    backlog_root = tmp_path / "_kano" / "backlog"
    product_root = backlog_root / "products" / name
    items_root = product_root / "items"

    for item_type in ["epic", "feature", "userstory", "task", "bug"]:
        (items_root / item_type / "0000").mkdir(parents=True, exist_ok=True)

    for required_dir in ["decisions", "views", "_meta"]:
        (product_root / required_dir).mkdir(parents=True, exist_ok=True)

    cfg_dir = product_root / "_config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_text = f"""[product]
name = "{name}"
prefix = "{prefix}"

[views]
auto_refresh = false

[log]
verbosity = "info"
debug = false
"""
    (cfg_dir / "config.toml").write_text(cfg_text, encoding="utf-8")

    shared = backlog_root / "_shared"
    shared.mkdir(parents=True, exist_ok=True)
    (shared / "defaults.toml").write_text(f"default_product = \"{name}\"\n", encoding="utf-8")

    return product_root


def test_epic_creation_creates_index(tmp_path: Path):
    product_root = _scaffold_product(tmp_path, "integration-test-product", "IT")
    cwd_before = Path.cwd()
    os.chdir(tmp_path)

    try:
        result = runner.invoke(
            app,
            [
                "item",
                "create",
                "--type",
                "epic",
                "--title",
                "Integration Test Epic",
                "--priority",
                "P1",
                "--agent",
                "integration-agent",
                "--product",
                "integration-test-product",
                "--tags",
                "integration,testing",
            ],
        )
        assert result.exit_code == 0, result.output
        lines = [line.strip() for line in result.output.splitlines() if line.strip()]
        created_line = next(line for line in lines if line.startswith("OK: Created:"))
        epic_id = created_line.split(":", 2)[-1].strip()
        assert epic_id.startswith("IT-EPIC-")

        epic_files = [
            path for path in (product_root / "items").rglob(f"{epic_id}_*.md")
            if not path.name.endswith(".index.md")
        ]
        assert len(epic_files) == 1
        epic_file = epic_files[0]
        assert epic_file.read_text(encoding="utf-8").startswith("---")

        index_file = epic_file.with_suffix(".index.md")
        assert index_file.exists(), "Expected epic index file"
    finally:
        os.chdir(cwd_before)


def test_feature_creation_with_parent(tmp_path: Path):
    product_root = _scaffold_product(tmp_path, "integration-test-product", "IT")
    cwd_before = Path.cwd()
    os.chdir(tmp_path)

    try:
        epic_result = runner.invoke(
            app,
            [
                "item",
                "create",
                "--type",
                "epic",
                "--title",
                "Parent Epic",
                "--priority",
                "P1",
                "--agent",
                "integration-agent",
                "--product",
                "integration-test-product",
            ],
        )
        assert epic_result.exit_code == 0, epic_result.output
        epic_id_line = next(line for line in epic_result.output.splitlines() if "Created:" in line)
        epic_id = epic_id_line.split(":", 1)[-1].strip()

        feature_result = runner.invoke(
            app,
            [
                "item",
                "create",
                "--type",
                "feature",
                "--title",
                "Child Feature",
                "--priority",
                "P2",
                "--agent",
                "integration-agent",
                "--product",
                "integration-test-product",
                "--parent",
                epic_id,
            ],
        )
        assert feature_result.exit_code == 0, feature_result.output
        feature_id_line = next(line for line in feature_result.output.splitlines() if "Created:" in line)
        feature_id = feature_id_line.split(":", 2)[-1].strip()
        assert feature_id.startswith("IT-FTR-")

        feature_files = list((product_root / "items").rglob(f"{feature_id}_*.md"))
        assert feature_files, "Expected feature file created"
    finally:
        os.chdir(cwd_before)
