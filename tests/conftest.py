import warnings

from hypothesis import settings

# Silence expected deprecation warnings emitted when intentionally using legacy JSON configs in tests.
warnings.filterwarnings(
    "ignore",
    message=r"JSON config is deprecated; migrate to TOML",
    category=DeprecationWarning,
)

# Prevent Hypothesis from writing a local example database (e.g. `.hypothesis/`) during tests.
settings.register_profile("kano-tests", database=None)
settings.load_profile("kano-tests")
