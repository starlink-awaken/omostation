"""Cockpit system-map catalog — SRP split entry point (T6-10).

Re-exports all catalog data from focused modules:
- pages: COCKPIT_PAGES, PAGE_OPERATOR_*, CAPABILITY_TO_PAGE, PROJECT_TO_PAGE
- coverage_dims: PROJECT_DOC_FILES, PACKAGE_MANIFESTS, PROJECT_COVERAGE_DIMENSIONS, PROJECT_PORT_ALIASES
- playbooks: USAGE_PATHS, OPERATING_PLAYBOOKS
- roadmap: ROADMAP_ITEMS

This module exists for backward compatibility. New code should import from
the specific submodules directly.
"""

from __future__ import annotations

from .coverage_dims import (
    CLI_ENTRYPOINTS,
    NEXT_CONFIGS,
    PACKAGE_MANIFESTS,
    PROJECT_COVERAGE_DIMENSIONS,
    PROJECT_DOC_FILES,
    PROJECT_PORT_ALIASES,
    SERVICE_ENTRYPOINTS,
    STATIC_FRONTEND_MARKERS,
    VITE_CONFIGS,
)
from .pages import (
    CAPABILITY_TO_PAGE,
    COCKPIT_PAGES,
    PAGE_CAPABILITY_LINKS,
    PAGE_OPERATOR_ACTION_METADATA,
    PAGE_OPERATOR_ACTIONS,
    PAGE_PROJECT_LINKS,
    PROJECT_TO_PAGE,
)
from .playbooks import OPERATING_PLAYBOOKS, USAGE_PATHS
from .roadmap import ROADMAP_ITEMS

# Re-export for backward compatibility
__all__ = [
    "COCKPIT_PAGES",
    "PAGE_OPERATOR_ACTIONS",
    "PAGE_OPERATOR_ACTION_METADATA",
    "CAPABILITY_TO_PAGE",
    "PAGE_CAPABILITY_LINKS",
    "PROJECT_TO_PAGE",
    "PAGE_PROJECT_LINKS",
    "PROJECT_DOC_FILES",
    "PACKAGE_MANIFESTS",
    "VITE_CONFIGS",
    "NEXT_CONFIGS",
    "STATIC_FRONTEND_MARKERS",
    "CLI_ENTRYPOINTS",
    "SERVICE_ENTRYPOINTS",
    "PROJECT_COVERAGE_DIMENSIONS",
    "PROJECT_PORT_ALIASES",
    "USAGE_PATHS",
    "OPERATING_PLAYBOOKS",
    "ROADMAP_ITEMS",
]
