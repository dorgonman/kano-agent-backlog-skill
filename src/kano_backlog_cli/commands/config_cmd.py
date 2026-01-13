from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import typer
import tomli_w

from ..util import ensure_core_on_path

app = typer.Typer(help="Configuration inspection and validation")


def _validate_required_fields(cfg: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    project = cfg.get("project")
    if not isinstance(project, dict):
        errors.append("[project] must be a table with name and prefix")
    else:
        name = project.get("name")
        prefix = project.get("prefix")
        if not isinstance(name, str) or not name.strip():
            errors.append("[project].name is required and must be a non-empty string")
        if not isinstance(prefix, str) or not prefix.strip():
            errors.append("[project].prefix is required and must be a non-empty string")

    process = cfg.get("process")
    if isinstance(process, dict):
        if process.get("profile") and process.get("path"):
            errors.append("[process] cannot set both profile and path")

    return errors


_SECRET_SUFFIXES = ("_token", "_password", "_key")


def _walk_for_secrets(prefix: str, value: Any, errors: list[str]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str) and k.lower().endswith(_SECRET_SUFFIXES):
                if isinstance(v, str) and v.startswith("env:"):
                    continue
                errors.append(f"Secret-like field must use env: reference: {prefix}{k}")
            _walk_for_secrets(f"{prefix}{k}.", v, errors)
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            _walk_for_secrets(f"{prefix}[{idx}].", item, errors)


def _validate_secrets(cfg: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _walk_for_secrets("", cfg, errors)
    return errors


def _strip_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for k, v in value.items():
            cleaned_v = _strip_nulls(v)
            if cleaned_v is not None:
                cleaned[k] = cleaned_v
        return cleaned
    if isinstance(value, list):
        cleaned_list = []
        for item in value:
            cleaned_item = _strip_nulls(item)
            if cleaned_item is not None:
                cleaned_list.append(cleaned_item)
        return cleaned_list
    return value


def _next_backup_path(json_path: Path) -> Path:
    base = json_path.with_suffix(json_path.suffix + ".bak")
    candidate = base
    counter = 1
    while candidate.exists():
        candidate = base.with_suffix(base.suffix + f".{counter}")
        counter += 1
    return candidate


@app.command("show")
def config_show(
    path: Path = typer.Option(Path("."), "--path", help="Resource path to resolve config from"),
    product: str | None = typer.Option(None, "--product", help="Product name (optional)"),
    sandbox: str | None = typer.Option(None, "--sandbox", help="Sandbox name (optional)"),
    agent: str | None = typer.Option(None, "--agent", help="Agent name for topic lookup"),
    topic: str | None = typer.Option(None, "--topic", help="Explicit topic name"),
    workset_item_id: str | None = typer.Option(None, "--workset", help="Workset item id"),
):
    """Print effective merged config as JSON (includes compiled backend URIs)."""
    ensure_core_on_path()
    from kano_backlog_core.config import ConfigLoader

    ctx, effective = ConfigLoader.load_effective_config(
        path,
        product=product,
        sandbox=sandbox,
        agent=agent,
        topic=topic,
        workset_item_id=workset_item_id,
    )

    typer.echo(
        json.dumps(
            {"context": ctx.model_dump(), "config": effective},
            indent=2,
            default=str,
        )
    )


@app.command("validate")
def config_validate(
    path: Path = typer.Option(Path("."), "--path", help="Resource path to resolve config from"),
    product: str | None = typer.Option(None, "--product", help="Product name (optional)"),
    sandbox: str | None = typer.Option(None, "--sandbox", help="Sandbox name (optional)"),
    agent: str | None = typer.Option(None, "--agent", help="Agent name for topic lookup"),
    topic: str | None = typer.Option(None, "--topic", help="Explicit topic name"),
    workset_item_id: str | None = typer.Option(None, "--workset", help="Workset item id"),
):
    """Validate layered config; exit 0 if ok, 1 otherwise."""
    ensure_core_on_path()
    from kano_backlog_core.config import ConfigLoader
    from kano_backlog_core.errors import ConfigError

    try:
        _, effective = ConfigLoader.load_effective_config(
            path,
            product=product,
            sandbox=sandbox,
            agent=agent,
            topic=topic,
            workset_item_id=workset_item_id,
        )
    except ConfigError as e:
        typer.echo(f"ConfigError: {e}")
        raise typer.Exit(1)

    errors: list[str] = []
    errors.extend(_validate_required_fields(effective))
    errors.extend(_validate_secrets(effective))

    if errors:
        typer.echo("Validation failed:")
        for err in errors:
            typer.echo(f"- {err}")
        raise typer.Exit(1)

    typer.echo("Config is valid")


@app.command("migrate-json")
def config_migrate_json(
    path: Path = typer.Option(Path("."), "--path", help="Resource path to resolve config from"),
    product: str | None = typer.Option(None, "--product", help="Product name (optional)"),
    sandbox: str | None = typer.Option(None, "--sandbox", help="Sandbox name (optional)"),
    agent: str | None = typer.Option(None, "--agent", help="Agent name for topic lookup"),
    topic: str | None = typer.Option(None, "--topic", help="Explicit topic name"),
    workset_item_id: str | None = typer.Option(None, "--workset", help="Workset item id"),
    write: bool = typer.Option(False, "--write", help="Apply migration (default: dry-run)"),
):
    """Convert JSON config files to TOML with backups (dry-run by default)."""
    ensure_core_on_path()
    from kano_backlog_core.config import ConfigLoader
    from kano_backlog_core.errors import ConfigError

    try:
        ctx = ConfigLoader.from_path(
            path,
            product=product,
            sandbox=sandbox,
            agent=agent,
            topic=topic,
        )
    except ConfigError as e:
        typer.echo(f"ConfigError: {e}")
        raise typer.Exit(1)

    topic_name = (topic or "").strip() or (ConfigLoader.get_active_topic(ctx.backlog_root, agent or "") or "")

    targets: list[tuple[str, Path, Path]] = [
        ("defaults", ctx.backlog_root / "_shared" / "defaults.json", ctx.backlog_root / "_shared" / "defaults.toml"),
        ("product", ctx.product_root / "_config" / "config.json", ctx.product_root / "_config" / "config.toml"),
    ]
    if topic_name:
        targets.append(
            (
                f"topic:{topic_name}",
                ConfigLoader.get_topic_path(ctx.backlog_root, topic_name) / "config.json",
                ConfigLoader.get_topic_path(ctx.backlog_root, topic_name) / "config.toml",
            )
        )
    if workset_item_id:
        targets.append(
            (
                f"workset:{workset_item_id}",
                ConfigLoader.get_workset_path(ctx.backlog_root, workset_item_id) / "config.json",
                ConfigLoader.get_workset_path(ctx.backlog_root, workset_item_id) / "config.toml",
            )
        )

    plans: list[dict[str, Any]] = []
    had_error = False

    for label, json_path, toml_path in targets:
        if not json_path.exists():
            continue
        if toml_path.exists():
            plans.append({
                "label": label,
                "json": str(json_path),
                "toml": str(toml_path),
                "status": "skipped-toml-exists",
            })
            continue

        try:
            data = ConfigLoader._read_json_optional(json_path)
        except ConfigError as e:
            had_error = True
            plans.append({
                "label": label,
                "json": str(json_path),
                "toml": str(toml_path),
                "status": "error",
                "error": str(e),
            })
            continue

        cleaned = _strip_nulls(data)
        plan: dict[str, Any] = {
            "label": label,
            "json": str(json_path),
            "toml": str(toml_path),
            "status": "dry-run" if not write else "pending",
        }

        if write:
            backup_path = _next_backup_path(json_path)
            shutil.copy2(json_path, backup_path)
            toml_path.parent.mkdir(parents=True, exist_ok=True)
            toml_text = tomli_w.dumps(cleaned)
            toml_path.write_text(toml_text, encoding="utf-8")
            plan["status"] = "written"
            plan["backup"] = str(backup_path)

        plans.append(plan)

    if not plans:
        typer.echo("No JSON config files found to migrate.")
        return

    typer.echo(
        json.dumps(
            {
                "applied": write,
                "plans": plans,
                "rollback": "Restore from the backup paths if needed.",
            },
            indent=2,
        )
    )

    if had_error:
        raise typer.Exit(1)
