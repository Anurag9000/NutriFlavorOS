"""Shared pytest configuration.

Tests construct their own authoritative persistence fixtures explicitly. Avoid
module-specific autouse monkeypatches here because they can hide stale contracts
and make isolated and aggregate runs behave differently.
"""
