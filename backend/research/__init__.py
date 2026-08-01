"""Governed offline research infrastructure.

Importing the package applies validated additive catalog extensions exactly once.
"""

from backend.research.catalog_extensions import apply_catalog_extensions


apply_catalog_extensions()
