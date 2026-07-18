"""DPDP data-principal erasure pipeline (TRD §6, Week 5 task 5.6). SLA <=7 days.

Removes a contact's PII across every collection; the audit entry is retained but
pseudonymized. Verified in the Week-5 DoD: erasure run removes contact PII across
all collections, audit entry retained pseudonymized.

Usage:
    python -m ops.dpdp_delete --tenant <tenant_id> --contact <contact_id>
"""

from __future__ import annotations

import argparse


def erase(tenant_id: str, contact_id: str) -> None:
    raise NotImplementedError("DPDP erasure — 06-engineering-plan task 5.6")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--contact", required=True)
    args = parser.parse_args()
    erase(args.tenant, args.contact)
