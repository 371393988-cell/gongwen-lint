"""Explainable, local linting for Chinese official documents."""

from .lint import Finding, lint_text

__all__ = ["Finding", "lint_text"]
__version__ = "0.1.1"
