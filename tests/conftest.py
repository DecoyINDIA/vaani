"""Tests explicitly opt in to local mock adapters before app imports."""

from __future__ import annotations

import os

os.environ.setdefault("USE_MOCK_ADAPTERS", "true")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-at-least-32-bytes")
