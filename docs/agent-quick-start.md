# Agent Quick Start Guide

This guide is for AI agents helping users set up and use kano-agent-backlog-skill from a cloned repository.

## For Agents: When to Use This Guide

Use this guide when:
- User has cloned the skill repository (not installed from PyPI)
- User wants to use the skill in development mode
- User asks you to "initialize the backlog skill" or "set up kano-backlog"
- You need to help set up a local-first backlog system

## Installation: Development Mode

When working with a cloned repository, install in **editable mode** so changes to the code take effect immediately.

### Step 1: Verify Prerequisites

```bash
# Check Python version (must be 3.8+)
python --version

# Check if in a virtual environment (recommended)
which python  # Should show venv path, not system Python
```

### Step 2: Install in Editable Mode

```bash
# Navigate to the skill directory
cd skills/kano-agent-backlog-skill

# Install with dev dependencies
pip install -e ".[dev]"

# This installs:
# - The kano-backlog CLI command
# - All runtime dependencies
# - Development tools (pytest, black, isort, mypy)
```

**What `-e` (editable mode) does:**
- Creates a link to the source code instead of copying files
- Code changes take effect immediately without reinstalling
- Perfect for development and testing

### Step 3: Verify Installation

```bash
# Check CLI is available
kano-backlog --version
# Expected output: kano-backlog version 0.1.0

# Run environment check
kano-backlog doctor
# All checks should pass (✅)
```

## Initialization: Create First Backlog

After installation, initialize a backlog for the user's project.

### Step 1: Navigate to Project Root

```bash
# Go to the project root (where you want the backlog)
cd /path/to/user/project
```

### Step 2: Initialize Backlog

```bash
# Initialize with product name and agent identity
kano-backlog admin init --product <product-name> --agent <agent-id>

# Example:
kano-backlog admin init --product my-app --agent kiro
```

**What this creates:**
```
_kano/backlog/
├── products/
│   └── my-app/
│       ├── items/          # Work items organized by type
│       ├── decisions/      # Architecture Decision Records
│       ├── views/          # Generated dashboards
│       └── _meta/          # Metadata and sequences
```

### Step 3: Verify Structure

```bash
# Check that directories were created
ls -la _kano/backlog/products/my-app/

# Should see: items/, decisions/, views/, _meta/
```

## Common Agent Workflow

### Creating Work Items

**Before writing code, create a work item:**

```bash
# Create a task
kano-backlog item create \
  --type task \
  --title "Implement user authentication" \
  --product my-app \
  --agent kiro

# Output: Created task: MYAPP-TSK-0001
```

**Fill in required fields before starting work:**

```bash
# Edit the item file
code _kano/backlog/products/my-app/items/task/0000/MYAPP-TSK-0001_*.md

# Add these sections:
# - Context: Why this work is needed
# - Goal: What success looks like
# - Approach: How you'll implement it
# - Acceptance Criteria: How to verify it works
# - Risks / Dependencies: What could go wrong
```

**Move to Ready state (enforces required fields):**

```bash
kano-backlog item update-state MYAPP-TSK-0001 \
  --state Ready \
  --agent kiro \
  --product my-app
```

### State Transitions

```bash
# Start work
kano-backlog item update-state MYAPP-TSK-0001 \
  --state InProgress \
  --agent kiro \
  --product my-app

# Complete work
kano-backlog item update-state MYAPP-TSK-0001 \
  --state Done \
  --agent kiro \
  --product my-app
```

### Recording Decisions

**Create an ADR for significant decisions:**

```bash
kano-backlog admin adr create \
  --title "Use JWT for authentication" \
  --product my-app \
  --agent kiro

# Edit the ADR file to document:
# - Context: What's the situation?
# - Decision: What did you decide?
# - Consequences: What are the implications?
# - Alternatives: What else was considered?
```

## Agent Identity

Always provide explicit `--agent` flag with your identity:

**Valid agent IDs:**
- `kiro` - Amazon Kiro
- `copilot` - GitHub Copilot
- `codex` - OpenAI Codex
- `claude` - Anthropic Claude
- `cursor` - Cursor AI
- `windsurf` - Windsurf
- `opencode` - OpenCode
- `antigravity` - Google Antigravity
- `amazon-q` - Amazon Q

**Never use placeholders like:**
- ❌ `<agent-id>`
- ❌ `<AGENT_NAME>`
- ❌ `auto`

## Troubleshooting

### "kano-backlog: command not found"

**Problem:** CLI not in PATH after installation

**Solution:**
```bash
# Verify installation
pip show kano-agent-backlog-skill

# If installed but not in PATH, try:
python -m kano_backlog_cli.cli --version

# Or reinstall:
pip uninstall kano-agent-backlog-skill
pip install -e ".[dev]"
```

### "No module named 'kano_backlog_core'"

**Problem:** Package not installed or installed incorrectly

**Solution:**
```bash
# Ensure you're in the skill directory
cd skills/kano-agent-backlog-skill

# Reinstall in editable mode
pip install -e ".[dev]"
```

### "Invalid state transition"

**Problem:** Trying to skip required states (e.g., Proposed → Done)

**Solution:**
```bash
# Follow the state machine:
# Proposed → Planned → Ready → InProgress → Done

# Move through states sequentially:
kano-backlog item update-state <ID> --state Planned --agent <agent> --product <product>
kano-backlog item update-state <ID> --state Ready --agent <agent> --product <product>
kano-backlog item update-state <ID> --state InProgress --agent <agent> --product <product>
kano-backlog item update-state <ID> --state Done --agent <agent> --product <product>
```

### "Ready gate validation failed"

**Problem:** Task/Bug missing required fields

**Solution:**
```bash
# Edit the item file and fill in all required sections:
# - Context
# - Goal
# - Approach
# - Acceptance Criteria
# - Risks / Dependencies

# Then try the state transition again
```

## Quick Reference

### Installation
```bash
cd skills/kano-agent-backlog-skill
pip install -e ".[dev]"
kano-backlog --version
kano-backlog doctor
```

### Initialization
```bash
cd /path/to/project
kano-backlog admin init --product <product> --agent <agent>
```

### Common Commands
```bash
# Create item
kano-backlog item create --type task --title "<title>" --product <product> --agent <agent>

# List items
kano-backlog item list --product <product>

# Update state
kano-backlog item update-state <ID> --state <state> --agent <agent> --product <product>

# Create ADR
kano-backlog admin adr create --title "<title>" --product <product> --agent <agent>

# Check environment
kano-backlog doctor
```

## For Users: Installing from PyPI

If the user wants to install the released version instead of development mode:

```bash
# Install from PyPI (when available)
pip install kano-agent-backlog-skill

# Verify
kano-backlog --version
kano-backlog doctor
```

See [Quick Start Guide](quick-start.md) for the standard installation workflow.

## Next Steps

After setup, guide the user through:

1. **Create their first work item** - Use `item create` to track work
2. **Understand the Ready gate** - Enforce required fields before starting work
3. **Learn state transitions** - Move items through the workflow
4. **Record decisions** - Use ADRs for significant technical choices
5. **Explore views** - Generate dashboards with `view refresh`

## Additional Resources

- **[Quick Start Guide](quick-start.md)** - Standard installation and usage
- **[Installation Guide](installation.md)** - Detailed setup and troubleshooting
- **[SKILL.md](../SKILL.md)** - Complete workflow rules for agents
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - Development guidelines
- **[Configuration Guide](configuration.md)** - Advanced configuration options

---

**Remember:** Always use `pip install -e ".[dev]"` for development mode, and always provide explicit `--agent` flags for auditability.
