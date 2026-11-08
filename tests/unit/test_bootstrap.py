"""Bootstrap and environment tests for PyNGINX."""

import pynginx


def test_package_import():
    """Verify package imports correctly and version is defined."""
    assert pynginx.__version__ == "0.1.0"
