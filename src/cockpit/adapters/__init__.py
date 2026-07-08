"""Cockpit anti-corruption adapters.

Each module isolates a downstream project (L1/L2/I0/M0/X) from the L3 cockpit
surface.  Callers inside cockpit should import through these adapters instead of
directly depending on other workspace projects.  This keeps upstream interface
changes localized and makes the dependency graph explicit.
"""
