"""Weekly ROI summary worker (F-13) — THE retention product.

Computes recovered bookings (after-hours + busy-line + previously-missed numbers),
revenue estimate, containment; sends owner WhatsApp template. Ships BEFORE any
billing code (06-engineering-plan Phase 3 item 1).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app import audit
from app.models.collections import Bookings, Conversations, Tenants

logger = logging.getLogger(__name__)


async def run_weekly_summaries() -> None:
    """Generate and record weekly ROI summary logs for all tenants."""
    # 1. Fetch all tenants
    tenants = await Tenants.all()
    
    now = datetime.now(UTC)
    
    for tenant in tenants:
        tenant_id = str(tenant["_id"])
        owner_name = tenant.get("name", "Doctor")
        timezone = ZoneInfo(str(tenant.get("timezone", "Asia/Kolkata")))
        local_now = now.astimezone(timezone)
        local_start = local_now - timedelta(days=7)
        start_date = local_start.astimezone(UTC).replace(tzinfo=None)
        end_date = now.replace(tzinfo=None)
        date_range_str = f"{local_start.strftime('%b %d')} - {local_now.strftime('%b %d')}"
        
        # Calculate Total Conversations
        convs_accessor = Conversations(tenant_id)
        convs_count = await convs_accessor.count_documents({
            "started_at": {"$gte": start_date, "$lte": end_date}
        })
        
        # Calculate Confirmed Bookings
        bookings_accessor = Bookings(tenant_id)
        bookings_cursor = bookings_accessor.find({
            "status": {"$in": ["confirmed", "completed"]},
            "ts": {"$gte": start_date, "$lte": end_date}
        })
        bookings_list = [booking async for booking in bookings_cursor]
        confirmed_count = len(bookings_list)
        
        # Calculate Recovered Bookings (after-hours + busy-line / voice)
        recovered_count = 0
        for booking in bookings_list:
            is_recovered = False
            booking_ts = booking.get("ts")
            
            if booking_ts:
                booking_local = booking_ts.replace(tzinfo=UTC).astimezone(timezone)
                # Check if outside 09:00 - 18:00 business hours or Sunday (weekday 6)
                if (
                    booking_local.weekday() == 6
                    or booking_local.hour < 9
                    or booking_local.hour >= 18
                ):
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
        
        # Fetch the clinic owner phone number
        from app.models.collections import Users
        users_accessor = Users(tenant_id)
        owner = await users_accessor.find_one({"role": "owner"})
        owner_wa_id = None
        if owner:
            owner_wa_id = owner.get("wa_id") or owner.get("phone")
        else:
            logger.warning(
                "No owner user found for tenant %s. Weekly summary template not sent.", tenant_id
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
        
        # Send actual template
        if owner_wa_id:
            from app.channels.whatsapp import send_template
            try:
                await send_template(
                    tenant_id=tenant_id,
                    wa_id=owner_wa_id,
                    template="weekly_summary_owner",
                    variables={
                        "owner_name": owner_name,
                        "date_range_str": date_range_str,
                        "convs_count": str(convs_count),
                        "confirmed_count": str(confirmed_count),
                        "recovered_count": str(recovered_count),
                        "revenue_str": revenue_str
                    },
                    operation_key=f"weekly-summary:{tenant_id}:{local_now.strftime('%G-%V')}",
                )
            except Exception as e:
                logger.error(f"Failed to send weekly summary to owner {owner_wa_id}: {e}")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting weekly summary worker scan...")
    asyncio.run(run_weekly_summaries())
    logger.info("Weekly summary worker scan completed.")


if __name__ == "__main__":
    main()
