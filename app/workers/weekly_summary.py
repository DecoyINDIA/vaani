"""Weekly ROI summary worker (F-13) — THE retention product.

Computes recovered bookings (after-hours + busy-line + previously-missed numbers),
revenue estimate, containment; sends owner WhatsApp template. Ships BEFORE any
billing code (06-engineering-plan Phase 3 item 1).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.models.base import get_db
from app.models.collections import Bookings, Conversations, Tenants
from app import audit

logger = logging.getLogger(__name__)


async def run_weekly_summaries() -> None:
    """Generate and record weekly ROI summary logs for all tenants."""
    db = get_db()
    
    # 1. Fetch all tenants
    tenants_cursor = db["tenants"].find({})
    tenants = await tenants_cursor.to_list(length=1000)
    
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start_date = now - timedelta(days=7)
    date_range_str = f"{start_date.strftime('%b %d')} - {now.strftime('%b %d')}"
    
    for tenant in tenants:
        tenant_id = str(tenant["_id"])
        owner_name = tenant.get("name", "Doctor")
        
        # Calculate Total Conversations
        convs_accessor = Conversations(tenant_id)
        convs_count = await convs_accessor.count_documents({
            "started_at": {"$gte": start_date, "$lte": now}
        })
        
        # Calculate Confirmed Bookings
        bookings_accessor = Bookings(tenant_id)
        bookings_cursor = bookings_accessor.find({
            "status": {"$in": ["confirmed", "completed"]},
            "ts": {"$gte": start_date, "$lte": now}
        })
        bookings_list = await bookings_cursor.to_list(length=1000)
        confirmed_count = len(bookings_list)
        
        # Calculate Recovered Bookings (after-hours + busy-line / voice)
        recovered_count = 0
        for booking in bookings_list:
            is_recovered = False
            booking_ts = booking.get("ts")
            
            if booking_ts:
                # Check if outside 09:00 - 18:00 business hours or Sunday (weekday 6)
                if booking_ts.weekday() == 6 or booking_ts.hour < 9 or booking_ts.hour >= 18:
                    is_recovered = True
                    
            if booking.get("source") == "voice":
                is_recovered = True
                
            if is_recovered:
                recovered_count += 1
                
        # Estimate Recovered Revenue (default ₹1,000 per booking)
        recovered_revenue = recovered_count * 1000
        revenue_str = f"Rs. {recovered_revenue}"
        
        logger.info(
            f"Weekly ROI Summary for tenant {tenant_id}: "
            f"convs={convs_count}, confirmed={confirmed_count}, "
            f"recovered={recovered_count}, revenue={revenue_str}"
        )
        
        # Log outbound template in audit
        await audit.record(
            tenant_id,
            actor="system",
            event_type="outbound_template",
            payload={
                "template": "T_WEEKLY_SUMMARY",
                "variables": [
                    owner_name,
                    date_range_str,
                    str(convs_count),
                    str(confirmed_count),
                    str(recovered_count),
                    revenue_str
                ]
            }
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting weekly summary worker scan...")
    asyncio.run(run_weekly_summaries())
    logger.info("Weekly summary worker scan completed.")


if __name__ == "__main__":
    main()
