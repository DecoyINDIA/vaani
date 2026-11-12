---
type: "Workflow"
title: "Booking lifecycle"
description: "Shared hold, confirm, cancel, and move operations connect slots to bookings."
status: "draft"
generated: {"by": "codex/booking-impact-map", "at": "2026-11-09T11:38:56.821259+00:00"}
source_commit: "804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4"
source_paths: ["app/booking/engine.py", "app/agent/tools/booking_create.py", "tests/test_booking_transitions.py", "tests/integration/test_booking_transactions.py"]
source_hashes: {"app/booking/engine.py": "e61b7fbde85d748a29f2cf68c70b764eec4cae756d33ec60944a7474995d5cc3", "app/agent/tools/booking_create.py": "424446c88c7b587d0b13ae39ffbdd6f57388f8007ccd783e68924c0f5c3b5d92", "tests/test_booking_transitions.py": "5f5ec60999adfbdd18762b6e607aecae8e3569abd4d4946d29f7fbe2fc2d5b10", "tests/integration/test_booking_transactions.py": "783d723075f27157fda4b4dda582ea491158ec2ef411de59c3a31226095b42d4"}
sources: [{"id": "s1", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/booking/engine.py", "title": "app/booking/engine.py"}, {"id": "s2", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/tools/booking_create.py", "title": "app/agent/tools/booking_create.py"}, {"id": "s3", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_booking_transitions.py", "title": "tests/test_booking_transitions.py"}, {"id": "s4", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/integration/test_booking_transactions.py", "title": "tests/integration/test_booking_transactions.py"}]
---
# Implemented entry points
The booking engine exposes schedule expansion, hold_slot, confirm_booking, create_booking, cancel_booking, move_booking, and waitlist claiming. Agent booking creation delegates into this shared domain.[^s1][^s2]

# Dependencies
- Entity lookup and authorization depend on [tenant and ID boundaries](tenant-isolation.md).
- Tool results return through the [agent flow](agent-flow.md).
- Confirmations depend on [delivery](delivery.md).

# Evidence and limits
Inspect both transition regressions and the real MongoDB integration suite. Mock behavior cannot prove transaction rollback or slot concurrency guarantees. Follow [release evidence](release-evidence.md) for remaining generated-ID, staging, and broader topology coverage.

# Coverage navigation
The detailed evidence map distinguishes generated-ID API coverage from legacy-ID worker journeys and collision cases still requiring follow-up.

# Source references
[^s1]: [app/booking/engine.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/booking/engine.py)
[^s2]: [app/agent/tools/booking_create.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/tools/booking_create.py)
[^s3]: [tests/test_booking_transitions.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_booking_transitions.py)
[^s4]: [tests/integration/test_booking_transactions.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/integration/test_booking_transactions.py)

# Detailed change-impact map
Follow [booking callers and transitions](booking-impact.md), [identifier contracts](identifier-contracts.md), and [test selection with current evidence](booking-evidence.md) before changing booking behavior.
