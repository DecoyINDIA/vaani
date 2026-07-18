"""Onboard a tenant from a YAML sheet (06-engineering-plan Week 3 task 3.4 / Week 6 6.3).

Creates the tenant + KB entries + practitioner schedules + holiday calendar
(Odisha festival set) + location pin + landmark line. Target: each onboarding
<=1 day wall clock, seed a demo clinic in <1 min.

Usage:
    python -m ops.seed_tenant path/to/clinic.yaml
"""

from __future__ import annotations

import sys


def seed(yaml_path: str) -> None:
    raise NotImplementedError("tenant seeding — 06-engineering-plan task 3.4")


if __name__ == "__main__":
    seed(sys.argv[1])
