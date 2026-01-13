import warnings

# Silence expected deprecation warnings emitted when intentionally using legacy JSON configs in tests.
warnings.filterwarnings(
    "ignore",
    message=r"JSON config is deprecated; migrate to TOML",
    category=DeprecationWarning,
)
