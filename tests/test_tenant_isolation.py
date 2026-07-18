"""Tenant-isolation suite (06-engineering-plan §0 rule 1, Week 5 task 5.7).

Two guarantees enforced here (fleshed out as accessors land):
  1. Every model accessor REQUIRES tenant_id — constructing one without it raises.
  2. Every owner_api route is probed cross-tenant and must be denied (100%).

The accessor-requires-tenant_id contract is testable today.
"""

from __future__ import annotations

import pytest

from app.models.collections import Bookings


def test_accessor_requires_tenant_id() -> None:
    with pytest.raises(ValueError):
        Bookings("")  # empty tenant_id must be rejected — no ambient tenant context


@pytest.mark.skip(reason="cross-tenant route probes land with owner_api — task 5.7")
def test_cross_tenant_routes_denied() -> None:
    ...
