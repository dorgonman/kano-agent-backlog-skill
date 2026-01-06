#!/usr/bin/env python3
"""Shared argument parser setup for multi-product support."""
from __future__ import annotations

import argparse


def add_product_arguments(parser: argparse.ArgumentParser) -> None:
    """Add --product and --sandbox flags to an argument parser.
    
    This helper is used by all CLI scripts to support multi-product architecture.
    
    Args:
        parser: ArgumentParser instance to update.
    """
    parser.add_argument(
        "--product",
        help="Product name (e.g., kano-agent-backlog-skill, kano-commit-convention-skill). "
             "If omitted, uses KANO_BACKLOG_PRODUCT env var or default from _shared/defaults.json.",
    )
    parser.add_argument(
        "--sandbox",
        action="store_true",
        help="Use sandbox directory for this product instead of the main product root.",
    )


def get_product_and_sandbox_flags(args: argparse.Namespace) -> tuple[str | None, bool]:
    """Extract product name and sandbox flag from parsed arguments.
    
    Args:
        args: Parsed arguments from ArgumentParser.
    
    Returns:
        Tuple of (product_name, use_sandbox).
    """
    product_name = getattr(args, "product", None)
    use_sandbox = getattr(args, "sandbox", False)
    return product_name, use_sandbox
