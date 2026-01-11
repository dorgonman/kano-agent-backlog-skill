from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import re

from kano_backlog_core.config import ConfigLoader
import frontmatter


@dataclass
class UidViolation:
    path: Path
    uid: str
    reason: str


@dataclass
class UidValidationResult:
    product: str
    checked: int
    violations: List[UidViolation]


def validate_uids(product: str | None = None, backlog_root: Path | None = None) -> List[UidValidationResult]:
    """Validate that all items use UUIDv7 UIDs.

    Returns a list of per-product results with violations (empty list if all clean).
    """

    # Resolve target products
    product_roots: list[Path] = []
    if backlog_root:
        backlog_root = Path(backlog_root).resolve()
        if product:
            product_roots.append(backlog_root / "products" / product)
        else:
            products_dir = backlog_root / "products"
            if products_dir.exists():
                product_roots.extend([p for p in products_dir.iterdir() if p.is_dir()])
    else:
        # Resolve from current workspace; product optional
        if product:
            ctx = ConfigLoader.from_path(Path.cwd(), product=product)
            product_roots.append(ctx.product_root)
        else:
            ctx = ConfigLoader.from_path(Path.cwd())
            products_dir = ctx.backlog_root / "products"
            if products_dir.exists():
                product_roots.extend([p for p in products_dir.iterdir() if p.is_dir()])

    v7_pattern = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    results: list[UidValidationResult] = []

    for root in product_roots:
        violations: list[UidViolation] = []
        checked = 0
        for item_path in (root / "items").rglob("*.md"):
            name = item_path.name.lower()
            if name.startswith("readme") or name.endswith(".index.md"):
                continue
            try:
                post = frontmatter.loads(item_path.read_text(encoding="utf-8"))
            except Exception as exc:  # pragma: no cover - defensive
                violations.append(UidViolation(item_path, "<unreadable>", f"Failed to parse frontmatter: {exc}"))
                continue
            checked += 1
            uid = str(post.get("uid", "")).lower()
            if not uid:
                violations.append(UidViolation(item_path, "<missing>", "Missing uid"))
                continue
            if not v7_pattern.match(uid):
                violations.append(UidViolation(item_path, uid, "UID is not UUIDv7"))
        results.append(UidValidationResult(product=root.name, checked=checked, violations=violations))

    return results
