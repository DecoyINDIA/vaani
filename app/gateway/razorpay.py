"""Razorpay webhook (TRD §5.1) — Phase 3.

POST /webhooks/razorpay — payment-link + subscription/mandate events,
signature-verified against RAZORPAY_WEBHOOK_SECRET. Reconciles payments and
UPI Autopay mandate lifecycle (06-engineering-plan Phase 3, item 2/4).
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

router = APIRouter(tags=["webhooks"])


@router.post("/razorpay")
async def receive(request: Request) -> Response:
    raise NotImplementedError("razorpay webhook — 06-engineering-plan Phase 3")
