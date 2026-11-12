---
type: "Verification Map"
title: "Booking evidence and test selection"
description: "Map change categories to exact regression checks and distinguish mock proof from pending acceptance."
status: "draft"
generated: {"by": "codex/booking-impact-map", "at": "2026-11-09T11:38:56.821259+00:00"}
source_commit: "d83fc7a1b9e98799b60910daeb5ffa4d80b3bf67"
source_paths: ["tests/test_booking_transitions.py", "tests/test_booking_journey.py", "tests/test_generated_objectid_boundaries.py", "tests/test_tenant_isolation.py", "tests/integration/test_booking_transactions.py", "tests/test_owner_route_authorization.py", "tests/test_phase3.py", "docs/production-remediation-plan.md"]
source_hashes: {"tests/test_booking_transitions.py": "5f5ec60999adfbdd18762b6e607aecae8e3569abd4d4946d29f7fbe2fc2d5b10", "tests/test_booking_journey.py": "9b55cb56f5b2b6558856fcef08cda797f32a99a59a13f58e3644f7e39689cc32", "tests/test_generated_objectid_boundaries.py": "20ffd2d35af52ed926ae84b191ee5e687fadac6f14b8f4cb6f015e8f73ad69eb", "tests/test_tenant_isolation.py": "6415d6f89e3c1e42be11a0ddc1b8dc60dc53387818ce19feee42970b9dc27d24", "tests/integration/test_booking_transactions.py": "783d723075f27157fda4b4dda582ea491158ec2ef411de59c3a31226095b42d4", "tests/test_owner_route_authorization.py": "000581b748de21e6eb36545b2a624efc651b04dfeace751aecb1728f77a57d3a", "tests/test_phase3.py": "4be9207377566036c02e4779d415ba2715056d9ceb0d1f5110b2959258a552e4", "docs/production-remediation-plan.md": "4b5827eea80bda1458e34fa497a99f1bf3296a8d6bb4a7f66ba876ebeffe6573"}
sources: [{"id": "s1", "resource": "file:///D:/XOLVER/Vaani/tests/test_booking_transitions.py", "title": "tests/test_booking_transitions.py"}, {"id": "s2", "resource": "file:///D:/XOLVER/Vaani/tests/test_booking_journey.py", "title": "tests/test_booking_journey.py"}, {"id": "s3", "resource": "file:///D:/XOLVER/Vaani/tests/test_generated_objectid_boundaries.py", "title": "tests/test_generated_objectid_boundaries.py"}, {"id": "s4", "resource": "file:///D:/XOLVER/Vaani/tests/test_tenant_isolation.py", "title": "tests/test_tenant_isolation.py"}, {"id": "s5", "resource": "file:///D:/XOLVER/Vaani/tests/integration/test_booking_transactions.py", "title": "tests/integration/test_booking_transactions.py"}, {"id": "s6", "resource": "file:///D:/XOLVER/Vaani/tests/test_owner_route_authorization.py", "title": "tests/test_owner_route_authorization.py"}, {"id": "s7", "resource": "file:///D:/XOLVER/Vaani/tests/test_phase3.py", "title": "tests/test_phase3.py"}, {"id": "s8", "resource": "file:///D:/XOLVER/Vaani/docs/production-remediation-plan.md", "title": "docs/production-remediation-plan.md"}]
---
# Recorded execution — 9 November 2026
Ran selected existing tests against this local working tree with USE_MOCK_ADAPTERS=true, APP_ENV=dev, and no integration MongoDB URI. Application code was not changed for this knowledge-map task.

- Booking transitions, booking journey, generated-ObjectId boundaries, tenant isolation, and integration booking module: **13 passed, 4 skipped**.
- Owner route authorization module and test_waitlist_cancellation_and_backfill: **8 passed**.
- Total selected checks: **21 passed, 4 skipped**. A Starlette TestClient/httpx deprecation warning appeared in each invocation.
- Three skips are real replica-set tests without VAANI_INTEGRATION_MONGODB_URI. The fourth is the explicit placeholder test_cross_tenant_routes_denied; actual cross-tenant assertions exist in the generated-ID and authorization modules.

This is fresh offline evidence for these selections. It does not rerun the historical CI evidence or demonstrate live-provider behavior. No release finding is closed by this task.[^s4][^s5][^s8]

# Select by change
| If changing... | Existing checks to run | What remains outside that proof |
|---|---|---|
| Hold/confirm and request retry | test_booking_transitions.py::test_create_is_owned_and_idempotent | changed-payload retry, explicit expiry matrix, real concurrent write semantics |
| Cancel ownership and release | test_booking_transitions.py::test_cancel_rejects_another_patient_and_never_reopens_rebooked_slot | generated-contact collision matrix and each entry point's error mapping |
| Move slot references | test_booking_transitions.py::test_move_transfers_slot_ownership_together | replay to same target, same-slot move, denied-patient target-hold behavior |
| API string/ObjectId round trip | test_generated_objectid_boundaries.py::test_booking_generated_objectid_lifecycle | full generated-ID interactive worker journey and every collision boundary |
| Legacy IDs | test_generated_objectid_boundaries.py::test_legacy_string_ids_continue_to_work | mixed historical references and real migration inventory |
| Ambiguous collision policy | test_generated_objectid_boundaries.py::test_ambiguous_id_collision_fails_controlled | existing case exercises conversation GET/takeover, not booking POST/slot/contact collisions |
| Interactive confirmation and recovery | test_booking_journey.py (all three tests) | uses legacy-named slots; add generated slot/contact fixture variant |
| Reply retry keys | test_booking_journey.py::test_confirmation_send_retry_reuses_the_same_operation_key | actual provider acknowledgment loss and ambiguous-send reconciliation |
| Authorization and tenant boundaries | test_owner_route_authorization.py, generated-ID lifecycle cross-clinic checks | provider ingress/caller proof and full staging deployment topology |
| Payment references | test_generated_objectid_boundaries.py::test_payment_and_razorpay_reconciliation_with_generated_objectids | real Razorpay sandbox and same-hex candidate ambiguity |
| Reminder pairing | test_generated_objectid_boundaries.py::test_reminders_scan_pairs_generated_objectids | ambiguous contact/slot cases and real template delivery |
| Waitlist side effects | test_phase3.py::test_waitlist_cancellation_and_backfill | generated-reference fulfillment, provider send, concurrent waitlist offers |
| Transaction/race/rollback | tests/integration/test_booking_transactions.py (three tests) | **not run in this task**; requires a designated disposable replica-set test database |

The test functions and assertions, rather than module docstrings, define the scope of the proof.[^s1][^s2][^s3][^s5][^s6][^s7]

# Reproduce the offline selections
Run from the Vaani repository with development mock adapters explicitly selected:

```powershell
$env:USE_MOCK_ADAPTERS = 'true'
$env:APP_ENV = 'dev'
$env:VAANI_INTEGRATION_MONGODB_URI = ''
.venv\Scripts\python.exe -m pytest tests/test_booking_transitions.py tests/test_booking_journey.py tests/test_generated_objectid_boundaries.py tests/test_tenant_isolation.py tests/integration/test_booking_transactions.py -q
.venv\Scripts\python.exe -m pytest tests/test_owner_route_authorization.py tests/test_phase3.py::test_waitlist_cancellation_and_backfill -q
python ops/knowledge.py check
```

The real integration fixture deletes integration-prefixed tenant fixtures and creates indexes. Run it only against the designated disposable test replica set; its three skipped cases remain pending in this task.[^s5]

# Ordered follow-up for the next booking implementation
1. Add failing regressions for booking POST ambiguity, missing/cross-tenant contact policy, and request_id reused with changed input; decide the intended compatibility contract before editing the engine.
2. Add generated-ID patient-picker and waitlist-fulfillment variants, plus cross-patient move and same-target retry cases.
3. If altering candidate lookups, cover same-hex collisions in reminder and payment consumers before applying a shared policy.
4. Run designated real replica-set race/rollback/generated-ID lifecycle checks, then collect staging/provider evidence required by the remediation ledger.

These are proposed follow-up checks, not tests added or behavior repaired by this documentation task. Link changes through [booking impact](booking-impact.md) and [identifier contracts](identifier-contracts.md). Release acceptance remains in [release evidence](release-evidence.md).

# Sources
[^s1]: [tests/test_booking_transitions.py](file:///D:/XOLVER/Vaani/tests/test_booking_transitions.py)
[^s2]: [tests/test_booking_journey.py](file:///D:/XOLVER/Vaani/tests/test_booking_journey.py)
[^s3]: [tests/test_generated_objectid_boundaries.py](file:///D:/XOLVER/Vaani/tests/test_generated_objectid_boundaries.py)
[^s4]: [tests/test_tenant_isolation.py](file:///D:/XOLVER/Vaani/tests/test_tenant_isolation.py)
[^s5]: [tests/integration/test_booking_transactions.py](file:///D:/XOLVER/Vaani/tests/integration/test_booking_transactions.py)
[^s6]: [tests/test_owner_route_authorization.py](file:///D:/XOLVER/Vaani/tests/test_owner_route_authorization.py)
[^s7]: [tests/test_phase3.py](file:///D:/XOLVER/Vaani/tests/test_phase3.py)
[^s8]: [docs/production-remediation-plan.md](file:///D:/XOLVER/Vaani/docs/production-remediation-plan.md)
