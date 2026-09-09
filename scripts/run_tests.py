#!/usr/bin/env python3
"""Automated test runner executing all unit and integration tests."""

import sys
import unittest
from pathlib import Path

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))


def run_all_tests() -> int:
    """Discovers and runs all tests in the tests/ directory."""
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(
        start_dir=str(WORKSPACE_ROOT / "tests"),
        pattern="test_*.py",
        top_level_dir=str(WORKSPACE_ROOT),
    )

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
