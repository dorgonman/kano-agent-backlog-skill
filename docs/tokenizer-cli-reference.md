# Tokenizer Adapters CLI Reference

**Complete command-line interface reference for tokenizer adapters**

This document provides comprehensive reference for all tokenizer CLI commands, options, and usage patterns.

## Table of Contents

- [Command Overview](#command-overview)
- [Global Options](#global-options)
- [Core Commands](#core-commands)
- [Configuration Commands](#configuration-commands)
- [Diagnostic Commands](#diagnostic-commands)
- [Performance Commands](#performance-commands)
- [Utility Commands](#utility-commands)
- [Usage Patterns](#usage-patterns)
- [Output Formats](#output-formats)

## Command Overview

All tokenizer commands are accessed through the `kano tokenizer` subcommand:

```bash
kano tokenizer <command> [options]
```

### Command Categories

| Category | Commands | Purpose |
|----------|----------|---------|
| **Core** | `status`, `test`, `compare` | Basic functionality and testing |
| **Configuration** | `config`, `validate`, `create-example`, `migrate` | Configuration management |
| **Diagnostic** | `diagnose`, `health`, `dependencies`, `adapter-status` | System diagnostics |
| **Performance** | `benchmark` | Performance testing and optimization |
| **Utility** | `env`, `install-guide`, `list-models`, `recommend` | Helper utilities |

## Global Options

These options are available for most commands:

### `--config PATH`
Specify configuration file path.

```bash
kano tokenizer test --config /path/to/config.toml
kano tokenizer validate --config my_config.toml
```

### `--help`
Show command help.

```bash
kano tokenizer --help
kano tokenizer test --help
```

## Core Commands

### `kano tokenizer status`

Show comprehensive system status including configuration, adapters, dependencies, and health.

**Syntax:**
```bash
kano tokenizer status [OPTIONS]
```

**Options:**
- `--config PATH` - Configuration file path
- `--verbose` - Show detailed information
- `--format FORMAT` - Output format (`markdown`, `json`)

**Examples:**
```bash
# Basic status
kano tokenizer status

# Detailed status
kano tokenizer status --verbose

# JSON output for scripting
kano tokenizer status --format json

# With custom configuration
kano tokenizer status --config production_config.toml --verbose
```

**Sample Output:**
```markdown
# Tokenizer System Status

**Overall Health:** ✅ HEALTHY
**Python Version:** 3.11.0 ✅

## Configuration
- **Adapter:** auto
- **Model:** text-embedding-3-small
- **Max Tokens:** auto
- **Fallback Chain:** tiktoken → huggingface → heuristic

## Adapter Status
### ✅ HEURISTIC
- **Status:** Available
- **Dependencies:** Ready

### ✅ TIKTOKEN
- **Status:** Available
- **Dependencies:** Ready

### ❌ HUGGINGFACE
- **Status:** Not available
- **Error:** No module named 'transformers'
```

### `kano tokenizer test`

Test tokenizer adapters with sample text.

**Syntax:**
```bash
kano tokenizer test [OPTIONS]
```

**Options:**
- `--config PATH` - Configuration file path
- `--text TEXT` - Text to tokenize (default: sample text)
- `--adapter NAME` - Specific adapter to test
- `--model NAME` - Model name to use

**Examples:**
```bash
# Test with default settings
kano tokenizer test

# Test with custom text
kano tokenizer test --text "Your custom text here"

# Test specific adapter
kano tokenizer test --adapter tiktoken --model gpt-4

# Test with configuration file
kano tokenizer test --config my_config.toml

# Test with environment override
KANO_TOKENIZER_ADAPTER=heuristic kano tokenizer test
```

**Sample Output:**
```
Testing tokenizers with text: 'This is a test sentence for tokenizer adapter testing.'
Text length: 58 characters

✓ HEURISTIC Adapter:
  Token count: 14
  Method: heuristic
  Tokenizer ID: heuristic:text-embedding-3-small:chars_4.0
  Is exact: False
  Max tokens: 8192

✓ TIKTOKEN Adapter:
  Token count: 12
  Method: tiktoken
  Tokenizer ID: tiktoken:text-embedding-3-small:cl100k_base
  Is exact: True
  Max tokens: 8192

Primary adapter resolution (auto):
  Resolved to: tiktoken
  Token count: 12
  Is exact: True
```

### `kano tokenizer compare`

Compare tokenization results across different adapters.

**Syntax:**
```bash
kano tokenizer compare TEXT [OPTIONS]
```

**Arguments:**
- `TEXT` - Text to tokenize and compare (required)

**Options:**
- `--adapters LIST` - Comma-separated adapter names (default: all available)
- `--model NAME` - Model name to use
- `--show-tokens` - Show actual token breakdown (when supported)

**Examples:**
```bash
# Compare all available adapters
kano tokenizer compare "Sample text to compare"

# Compare specific adapters
kano tokenizer compare "Sample text" --adapters tiktoken,heuristic

# Compare with specific model
kano tokenizer compare "Sample text" --model gpt-4

# Show token breakdown
kano tokenizer compare "Sample text" --show-tokens
```

**Sample Output:**
```markdown
# Tokenizer Comparison
**Text:** Sample text to compare across different tokenizers
**Length:** 52 characters
**Model:** text-embedding-3-small

## Results
| Adapter | Token Count | Exact | Method | Max Tokens | Status |
|---------|-------------|-------|--------|------------|--------|
| heuristic | 13 | ❌ | heuristic | 8192 | ✅ |
| tiktoken | 11 | ✅ | tiktoken | 8192 | ✅ |
| huggingface | N/A | N/A | N/A | N/A | ❌ |

## Analysis
- **Token Count Range:** 11 - 13
- **Variance:** 2 tokens (18.2%)
- **Exact Adapters:** tiktoken

## Recommendations
- For maximum accuracy, use: **tiktoken**
- For OpenAI models, **tiktoken** is recommended
```

## Configuration Commands

### `kano tokenizer config`

Show current configuration with environment overrides applied.

**Syntax:**
```bash
kano tokenizer config [OPTIONS]
```

**Options:**
- `--config PATH` - Configuration file path
- `--format FORMAT` - Output format (`json`, `toml`, `yaml`)

**Examples:**
```bash
# Show configuration in JSON
kano tokenizer config --format json

# Show configuration from specific file
kano tokenizer config --config my_config.toml

# Show configuration in TOML format
kano tokenizer config --format toml
```

**Sample Output (JSON):**
```json
{
  "adapter": "auto",
  "model": "text-embedding-3-small",
  "max_tokens": null,
  "fallback_chain": ["tiktoken", "huggingface", "heuristic"],
  "options": {},
  "heuristic": {
    "chars_per_token": 4.0
  },
  "tiktoken": {},
  "huggingface": {
    "use_fast": true,
    "trust_remote_code": false
  }
}
```

### `kano tokenizer validate`

Validate tokenizer configuration.

**Syntax:**
```bash
kano tokenizer validate [OPTIONS]
```

**Options:**
- `--config PATH` - Configuration file path

**Examples:**
```bash
# Validate default configuration
kano tokenizer validate

# Validate specific configuration file
kano tokenizer validate --config my_config.toml
```

**Sample Output:**
```
✓ Configuration is valid
  Adapter: auto
  Model: text-embedding-3-small
  Max tokens: auto
  Fallback chain: tiktoken → huggingface → heuristic
```

### `kano tokenizer create-example`

Create an example tokenizer configuration file.

**Syntax:**
```bash
kano tokenizer create-example [OPTIONS]
```

**Options:**
- `--output PATH` - Output file path (default: `tokenizer_config.toml`)
- `--force` - Overwrite existing file

**Examples:**
```bash
# Create example configuration
kano tokenizer create-example

# Create with custom name
kano tokenizer create-example --output my_config.toml

# Overwrite existing file
kano tokenizer create-example --output existing_config.toml --force
```

**Sample Output:**
```
✓ Created example tokenizer configuration: tokenizer_config.toml

Edit the file to customize your tokenizer settings.
Use 'kano tokenizer validate --config <path>' to validate your changes.
```

### `kano tokenizer migrate`

Migrate configuration from old format to new TOML format.

**Syntax:**
```bash
kano tokenizer migrate INPUT_PATH [OPTIONS]
```

**Arguments:**
- `INPUT_PATH` - Input configuration file (JSON or TOML)

**Options:**
- `--output PATH` - Output TOML file path (default: input path with `.toml` extension)
- `--force` - Overwrite existing output file

**Examples:**
```bash
# Migrate JSON to TOML
kano tokenizer migrate old_config.json

# Migrate with custom output path
kano tokenizer migrate old_config.json --output new_config.toml

# Force overwrite
kano tokenizer migrate old_config.json --output existing.toml --force
```

**Sample Output:**
```
✓ Migrated configuration from old_config.json to old_config.toml

Validate the migrated configuration with:
  kano tokenizer validate --config old_config.toml
```

## Diagnostic Commands

### `kano tokenizer diagnose`

Run comprehensive tokenizer diagnostics.

**Syntax:**
```bash
kano tokenizer diagnose [OPTIONS]
```

**Options:**
- `--config PATH` - Configuration file path
- `--model NAME` - Specific model to diagnose
- `--verbose` - Show detailed diagnostic information

**Examples:**
```bash
# Basic diagnostics
kano tokenizer diagnose

# Diagnose specific model
kano tokenizer diagnose --model gpt-4

# Verbose diagnostics
kano tokenizer diagnose --verbose

# Diagnose with custom configuration
kano tokenizer diagnose --config my_config.toml --verbose
```

### `kano tokenizer health`

Check health of a specific tokenizer adapter.

**Syntax:**
```bash
kano tokenizer health ADAPTER [OPTIONS]
```

**Arguments:**
- `ADAPTER` - Adapter name (`heuristic`, `tiktoken`, `huggingface`)

**Options:**
- `--model NAME` - Model name to test with (default: `test-model`)

**Examples:**
```bash
# Check tiktoken health
kano tokenizer health tiktoken

# Check with specific model
kano tokenizer health huggingface --model bert-base-uncased

# Check all adapters
for adapter in heuristic tiktoken huggingface; do
    echo "Checking $adapter:"
    kano tokenizer health $adapter
    echo
done
```

**Sample Output:**
```
✅ TIKTOKEN adapter is healthy
   Token count: 12
   Method: tiktoken
   Is exact: True
   Tokenizer ID: tiktoken:test-model:cl100k_base
   Max tokens: 8192
```

### `kano tokenizer dependencies`

Check status of tokenizer dependencies.

**Syntax:**
```bash
kano tokenizer dependencies [OPTIONS]
```

**Options:**
- `--verbose` - Show detailed dependency information
- `--refresh` - Force refresh of dependency cache

**Examples:**
```bash
# Basic dependency check
kano tokenizer dependencies

# Detailed dependency information
kano tokenizer dependencies --verbose

# Force refresh cache
kano tokenizer dependencies --refresh
```

**Sample Output:**
```
✅ Overall Health: HEALTHY
🐍 Python Version: 3.11.0 ✅

📦 Dependencies:
  ✅ tiktoken
      Version: 0.5.1
  ❌ transformers
      Error: No module named 'transformers'
      Installation:
        pip install transformers
        conda install transformers -c conda-forge

💡 Recommendations:
  • Install transformers for HuggingFace model support
  • Consider using tiktoken for OpenAI models

❌ Missing Dependencies: transformers
   Use 'kano tokenizer install-guide' for installation instructions
```

### `kano tokenizer adapter-status`

Show status of tokenizer adapters including dependency checks.

**Syntax:**
```bash
kano tokenizer adapter-status [OPTIONS]
```

**Options:**
- `--adapter NAME` - Show status for specific adapter only

**Examples:**
```bash
# Show all adapter status
kano tokenizer adapter-status

# Show specific adapter status
kano tokenizer adapter-status --adapter tiktoken
```

**Sample Output:**
```
🔧 Tokenizer Adapter Status:

  ✅ HEURISTIC
      Status: Available
      Dependencies: Ready

  ✅ TIKTOKEN
      Status: Available
      Dependencies: Ready

  ❌ HUGGINGFACE
      Status: Not available
      Error: No module named 'transformers'
      Missing deps: transformers

📊 Overall Health: DEGRADED
❌ Missing: transformers
```

## Performance Commands

### `kano tokenizer benchmark`

Benchmark tokenizer adapter performance and accuracy.

**Syntax:**
```bash
kano tokenizer benchmark [OPTIONS]
```

**Options:**
- `--text TEXT` - Text for benchmarking (default: sample text)
- `--iterations N` - Number of test iterations (default: 10)
- `--adapters LIST` - Comma-separated adapter names (default: all available)
- `--model NAME` - Model name to use (default: `text-embedding-3-small`)
- `--format FORMAT` - Output format (`markdown`, `json`, `csv`)

**Examples:**
```bash
# Basic benchmark
kano tokenizer benchmark

# Benchmark with custom text
kano tokenizer benchmark --text "$(cat large_document.txt)"

# Benchmark specific adapters
kano tokenizer benchmark --adapters tiktoken,heuristic --iterations 50

# JSON output for analysis
kano tokenizer benchmark --format json > benchmark_results.json

# CSV output for spreadsheet analysis
kano tokenizer benchmark --format csv > benchmark_results.csv
```

**Sample Output (Markdown):**
```markdown
# Tokenizer Adapter Benchmark Results

## Performance Summary
| Adapter | Avg Time (ms) | Tokens | Exact | Consistent | Status |
|---------|---------------|--------|-------|------------|--------|
| heuristic | 0.12 | 14 | ❌ | ✅ | ✅ |
| tiktoken | 2.45 | 12 | ✅ | ✅ | ✅ |

## Detailed Results
### HEURISTIC
- **Average Time:** 0.12 ms
- **Time Range:** 0.10 - 0.15 ms
- **Token Count:** 14
- **Exact Count:** No
- **Consistent:** Yes
- **Method:** heuristic
- **Tokenizer ID:** heuristic:text-embedding-3-small:chars_4.0

### TIKTOKEN
- **Average Time:** 2.45 ms
- **Time Range:** 2.20 - 2.80 ms
- **Token Count:** 12
- **Exact Count:** Yes
- **Consistent:** Yes
- **Method:** tiktoken
- **Tokenizer ID:** tiktoken:text-embedding-3-small:cl100k_base

## Performance Ranking
**By Speed (fastest first):**
1. heuristic (0.12 ms)
2. tiktoken (2.45 ms)

**By Accuracy (most accurate first):**
1. tiktoken (exact, consistent)
2. heuristic (consistent)
```

## Utility Commands

### `kano tokenizer env`

Show available environment variables for tokenizer configuration.

**Syntax:**
```bash
kano tokenizer env
```

**Sample Output:**
```
Tokenizer Configuration Environment Variables:

  KANO_TOKENIZER_ADAPTER
    Description: Override adapter selection (auto, heuristic, tiktoken, huggingface)
    Current value: not set

  KANO_TOKENIZER_MODEL
    Description: Override model name
    Current value: not set

  KANO_TOKENIZER_MAX_TOKENS
    Description: Override max tokens (integer)
    Current value: not set

  KANO_TOKENIZER_HEURISTIC_CHARS_PER_TOKEN
    Description: Override chars per token ratio (float)
    Current value: not set

  KANO_TOKENIZER_TIKTOKEN_ENCODING
    Description: Override TikToken encoding
    Current value: not set

  KANO_TOKENIZER_HUGGINGFACE_USE_FAST
    Description: Override use_fast setting (true/false)
    Current value: not set

  KANO_TOKENIZER_HUGGINGFACE_TRUST_REMOTE_CODE
    Description: Override trust_remote_code (true/false)
    Current value: not set

Example usage:
  export KANO_TOKENIZER_ADAPTER=heuristic
  export KANO_TOKENIZER_HEURISTIC_CHARS_PER_TOKEN=3.5
  kano tokenizer test
```

### `kano tokenizer install-guide`

Show installation guide for missing dependencies.

**Syntax:**
```bash
kano tokenizer install-guide
```

**Sample Output:**
```
# Tokenizer Dependencies Installation Guide

## Missing Dependencies
Based on your system check, the following dependencies are missing:

### transformers (for HuggingFace adapter)
**Installation Options:**
```bash
# Using pip (recommended)
pip install transformers

# Using conda
conda install transformers -c conda-forge

# With specific version
pip install "transformers>=4.21.0"
```

**Verification:**
```bash
python -c "import transformers; print('Transformers version:', transformers.__version__)"
kano tokenizer health huggingface
```

## Optional Dependencies

### sentence-transformers (for sentence embedding models)
```bash
pip install sentence-transformers
```

### torch (for GPU acceleration)
```bash
# CPU-only version
pip install torch --index-url https://download.pytorch.org/whl/cpu

# GPU version (CUDA 11.8)
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

## Verification Commands
After installation, verify your setup:
```bash
kano tokenizer dependencies
kano tokenizer status
kano tokenizer test
```
```

### `kano tokenizer list-models`

List supported models and their token limits.

**Syntax:**
```bash
kano tokenizer list-models [OPTIONS]
```

**Options:**
- `--adapter NAME` - Show models for specific adapter only
- `--format FORMAT` - Output format (`markdown`, `json`, `csv`)

**Examples:**
```bash
# List all supported models
kano tokenizer list-models

# List OpenAI models only
kano tokenizer list-models --adapter tiktoken

# List HuggingFace models only
kano tokenizer list-models --adapter huggingface

# JSON output for scripting
kano tokenizer list-models --format json
```

**Sample Output:**
```markdown
# Supported Models

**Total Models:** 45

## OpenAI Models (15 models)

| Model | Max Tokens | Encoding | Recommended Adapter |
|-------|------------|----------|-------------------|
| gpt-4 | 8192 | cl100k_base | tiktoken |
| gpt-4-turbo | 128000 | cl100k_base | tiktoken |
| gpt-3.5-turbo | 4096 | cl100k_base | tiktoken |
| text-embedding-3-small | 8192 | cl100k_base | tiktoken |
| text-embedding-3-large | 8192 | cl100k_base | tiktoken |

## HuggingFace Models (25 models)

| Model | Max Tokens | Encoding | Recommended Adapter |
|-------|------------|----------|-------------------|
| bert-base-uncased | 512 | N/A | huggingface |
| sentence-transformers/all-MiniLM-L6-v2 | 512 | N/A | huggingface |
| sentence-transformers/all-mpnet-base-v2 | 512 | N/A | huggingface |

## Usage Notes
- **Max Tokens:** Maximum context length for the model
- **Encoding:** TikToken encoding used (for OpenAI models)
- **Recommended Adapter:** Best adapter for accurate tokenization

### Examples
```bash
# Use with embedding command
kano embedding build --tokenizer-model text-embedding-3-small

# Test tokenization
kano tokenizer test --model bert-base-uncased --adapter huggingface
```
```

### `kano tokenizer recommend`

Get adapter recommendation for a specific model and requirements.

**Syntax:**
```bash
kano tokenizer recommend MODEL [OPTIONS]
```

**Arguments:**
- `MODEL` - Model name to get recommendation for

**Options:**
- `--requirements` - Requirements as key=value pairs (e.g., `accuracy=high,speed=medium`)

**Examples:**
```bash
# Get recommendation for OpenAI model
kano tokenizer recommend gpt-4

# Get recommendation for HuggingFace model
kano tokenizer recommend bert-base-uncased

# Get recommendation with requirements
kano tokenizer recommend gpt-4 --requirements "accuracy=high,speed=medium"
```

**Sample Output:**
```markdown
# Adapter Recommendation for 'gpt-4'

**Recommended Adapter:** tiktoken

## Reasoning
- Model appears to be an OpenAI model
- TikToken provides exact tokenization for OpenAI models

## Available Alternatives
- ✅ **heuristic**
  - Fast approximation, good for development
- ❌ **huggingface**
  - Not available: No module named 'transformers'

## Usage Example
```bash
# Use recommended adapter in embedding command
kano embedding build --tokenizer-adapter tiktoken --tokenizer-model gpt-4

# Test the adapter
kano tokenizer test --text 'Sample text' --adapter tiktoken --model gpt-4
```
```

## Usage Patterns

### Basic Testing Workflow

```bash
# 1. Check system status
kano tokenizer status

# 2. Test basic functionality
kano tokenizer test

# 3. Compare adapters
kano tokenizer compare "Your sample text"

# 4. Validate configuration
kano tokenizer validate
```

### Configuration Workflow

```bash
# 1. Create example configuration
kano tokenizer create-example --output my_config.toml

# 2. Edit configuration file
# (edit my_config.toml)

# 3. Validate configuration
kano tokenizer validate --config my_config.toml

# 4. Test configuration
kano tokenizer test --config my_config.toml

# 5. Benchmark performance
kano tokenizer benchmark --config my_config.toml
```

### Troubleshooting Workflow

```bash
# 1. Check overall health
kano tokenizer status --verbose

# 2. Check dependencies
kano tokenizer dependencies --verbose

# 3. Check adapter health
kano tokenizer health tiktoken
kano tokenizer health huggingface
kano tokenizer health heuristic

# 4. Run diagnostics
kano tokenizer diagnose --verbose

# 5. Get installation guide
kano tokenizer install-guide
```

### Performance Analysis Workflow

```bash
# 1. Benchmark current setup
kano tokenizer benchmark --format json > baseline.json

# 2. Test with different configurations
export KANO_TOKENIZER_ADAPTER=heuristic
kano tokenizer benchmark --format json > heuristic.json

export KANO_TOKENIZER_ADAPTER=tiktoken
kano tokenizer benchmark --format json > tiktoken.json

# 3. Compare results
# (analyze JSON files)

# 4. Choose optimal configuration
```

### Production Deployment Workflow

```bash
# 1. Create production configuration
kano tokenizer create-example --output production_config.toml
# (edit production_config.toml)

# 2. Validate configuration
kano tokenizer validate --config production_config.toml

# 3. Test with production-like data
kano tokenizer test --config production_config.toml --text "$(cat sample_production_data.txt)"

# 4. Benchmark performance
kano tokenizer benchmark --config production_config.toml --iterations 50

# 5. Check system health
kano tokenizer status --config production_config.toml --verbose

# 6. Deploy configuration
cp production_config.toml /etc/kano/tokenizer.toml
```

## Output Formats

### JSON Format

Most commands support `--format json` for machine-readable output:

```bash
kano tokenizer status --format json
kano tokenizer benchmark --format json
kano tokenizer config --format json
```

**Example JSON Output:**
```json
{
  "overall_health": "healthy",
  "python_version": "3.11.0",
  "python_compatible": true,
  "configuration": {
    "adapter": "auto",
    "model": "text-embedding-3-small",
    "max_tokens": null,
    "fallback_chain": ["tiktoken", "huggingface", "heuristic"]
  },
  "adapters": {
    "heuristic": {
      "available": true,
      "error": null
    },
    "tiktoken": {
      "available": true,
      "error": null
    },
    "huggingface": {
      "available": false,
      "error": "No module named 'transformers'"
    }
  }
}
```

### CSV Format

Benchmark and list commands support CSV output:

```bash
kano tokenizer benchmark --format csv
kano tokenizer list-models --format csv
```

### TOML/YAML Formats

Configuration commands support multiple formats:

```bash
kano tokenizer config --format toml
kano tokenizer config --format yaml
```

---

This CLI reference provides comprehensive documentation for all tokenizer adapter commands. Use `kano tokenizer <command> --help` for detailed help on any specific command.