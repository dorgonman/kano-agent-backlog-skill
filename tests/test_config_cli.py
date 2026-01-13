import json
from pathlib import Path

from typer.testing import CliRunner

from kano_backlog_cli.cli import app

runner = CliRunner()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _scaffold_backlog(tmp_path: Path) -> Path:
    backlog_root = tmp_path / "_kano" / "backlog"
    shared = backlog_root / "_shared"
    product_root = backlog_root / "products" / "demo"
    product_cfg_dir = product_root / "_config"

    _write(
        shared / "defaults.toml",
        """
[defaults]
default_product = "demo"
""",
    )

    _write(
        product_cfg_dir / "config.toml",
        """
[project]
name = "demo"
prefix = "KABSD"

[log]
verbosity = "debug"

[process]
profile = "builtin/azure-boards-agile"

[backends.jira]
type = "jira"
host = "example.atlassian.net"
project = "DEMO"
""",
    )

    return product_root


def test_config_show_outputs_effective_config(tmp_path: Path):
    product_root = _scaffold_backlog(tmp_path)
    result = runner.invoke(app, ["config", "show", "--path", str(product_root)])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["config"]["backends"]["jira"]["uri"] == "jira://example.atlassian.net/DEMO"
    assert data["context"]["product_name"] == "demo"


def test_config_validate_success(tmp_path: Path):
    product_root = _scaffold_backlog(tmp_path)
    result = runner.invoke(app, ["config", "validate", "--path", str(product_root)])
    assert result.exit_code == 0, result.output
    assert "Config is valid" in result.output


def test_config_validate_fails_on_project_prefix(tmp_path: Path):
    backlog_root = tmp_path / "_kano" / "backlog"
    shared = backlog_root / "_shared"
    _write(
        shared / "defaults.toml",
        """
[defaults]
default_product = "demo"
""",
    )
    product_root = backlog_root / "products" / "demo" / "_config"
    _write(
        product_root / "config.toml",
        """
[project]
name = "demo"
# prefix missing
""",
    )
    result = runner.invoke(app, ["config", "validate", "--path", str(product_root.parent)])
    assert result.exit_code == 1
    assert "[project].prefix" in result.output


def test_config_validate_rejects_secret_literal(tmp_path: Path):
    backlog_root = tmp_path / "_kano" / "backlog"
    shared = backlog_root / "_shared"
    _write(
        shared / "defaults.toml",
        """
[defaults]
default_product = "demo"
""",
    )
    product_root = backlog_root / "products" / "demo" / "_config"
    _write(
        product_root / "config.toml",
        """
[project]
name = "demo"
prefix = "KABSD"

[analysis.llm]
api_key = "secret-token"
""",
    )
    result = runner.invoke(app, ["config", "validate", "--path", str(product_root.parent)])
    assert result.exit_code == 1
    assert "env:" in result.output


def test_config_validate_allows_env_secret(tmp_path: Path):
    backlog_root = tmp_path / "_kano" / "backlog"
    shared = backlog_root / "_shared"
    _write(
        shared / "defaults.toml",
        """
[defaults]
default_product = "demo"
""",
    )
    product_root = backlog_root / "products" / "demo" / "_config"
    _write(
        product_root / "config.toml",
        """
[project]
name = "demo"
prefix = "KABSD"

[analysis.llm]
api_key = "env:OPENAI_API_KEY"
""",
    )
    result = runner.invoke(app, ["config", "validate", "--path", str(product_root.parent)])
    assert result.exit_code == 0, result.output
