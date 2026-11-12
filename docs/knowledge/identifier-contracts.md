---
type: "Invariant"
title: "Booking identifier contracts"
description: "Separate ID representations, collision-safe resolution, ownership, and dependent consumers."
status: "draft"
generated: {"by": "codex/booking-impact-map", "at": "2026-11-09T11:38:56.821259+00:00"}
source_commit: "d83fc7a1b9e98799b60910daeb5ffa4d80b3bf67"
source_paths: ["app/models/base.py", "app/booking/engine.py", "app/owner_api/routes.py", "app/workers/inbound.py", "app/agent/tools/payment_link_create.py", "app/gateway/razorpay.py", "app/workers/reminders.py", "app/agent/tools/booking_cancel.py", "app/models/collections.py"]
source_hashes: {"app/models/base.py": "f2141ff668fa8c6ea338b5ce667c7cb5e4c0129b6ce5c796565c387064483f10", "app/booking/engine.py": "e61b7fbde85d748a29f2cf68c70b764eec4cae756d33ec60944a7474995d5cc3", "app/owner_api/routes.py": "a84c6640ec9d33c8bffb8612da95e63ed2fa08a28e6112fde334c107def9271c", "app/workers/inbound.py": "f705f3dedcd07ae9644eaef9f185463469ba78e3f8ead983095adb5bebb88d75", "app/agent/tools/payment_link_create.py": "378bddfac488bc1accc181bec5d9c6702b19025e62a3e584db71122e6ab7e238", "app/gateway/razorpay.py": "4e8c68b442a9be1d64246753ba9bc3123db4b7630ba81f8a860ad454021334ec", "app/workers/reminders.py": "d409960b9043f3c592ba191de501c1d54dca87baee2dbe12d391221abdc00106", "app/agent/tools/booking_cancel.py": "bca3d1e9abe41343655929b73d962268104f374afeae1efe500ac42a77fc6837", "app/models/collections.py": "e18443ad6693cff6445447e5a6a0cbc38cb177818a1ebfbdae2926cf69bce8b1"}
sources: [{"id": "s1", "resource": "file:///D:/XOLVER/Vaani/app/models/base.py", "title": "app/models/base.py"}, {"id": "s2", "resource": "file:///D:/XOLVER/Vaani/app/booking/engine.py", "title": "app/booking/engine.py"}, {"id": "s3", "resource": "file:///D:/XOLVER/Vaani/app/owner_api/routes.py", "title": "app/owner_api/routes.py"}, {"id": "s4", "resource": "file:///D:/XOLVER/Vaani/app/workers/inbound.py", "title": "app/workers/inbound.py"}, {"id": "s5", "resource": "file:///D:/XOLVER/Vaani/app/agent/tools/payment_link_create.py", "title": "app/agent/tools/payment_link_create.py"}, {"id": "s6", "resource": "file:///D:/XOLVER/Vaani/app/gateway/razorpay.py", "title": "app/gateway/razorpay.py"}, {"id": "s7", "resource": "file:///D:/XOLVER/Vaani/app/workers/reminders.py", "title": "app/workers/reminders.py"}, {"id": "s8", "resource": "file:///D:/XOLVER/Vaani/app/agent/tools/booking_cancel.py", "title": "app/agent/tools/booking_cancel.py"}, {"id": "s9", "resource": "file:///D:/XOLVER/Vaani/app/models/collections.py", "title": "app/models/collections.py"}]
---
# Representation contract
| Value | Boundary representation | Stored meaning | Change impact |
|---|---|---|---|
| tenant_id | explicit authenticated/routed clinic key | accessor query partition | never infer tenant from an entity ID or graph relationship |
| booking ID | string at HTTP/tool boundaries | new booking _id is ObjectId | booking API detail, cancel/move, payment and reminder references |
| slot/contact ID | string entering shared engine | resolves to matching stored string or ObjectId; missing contact has legacy fallback | slot availability, patient ownership and reference integrity |
| booking.slot_id, slot.booking_id | serialized as strings on output | stored resolved slot ID and generated booking ObjectId | compare stored types deliberately when updating both sides |
| request_id / operation_id | opaque string | retry key and hold owner | do not convert to ObjectId; tenant-scoped uniqueness is separate from entity identity |
| provider payment/link/message ID | opaque provider string | external correlation | keep provider namespace separate from internal booking/contact IDs |

The engine creates booking ObjectIds and preserves resolved source IDs. serialize_mongo recursively converts ObjectIds for output; its signature casts to the input type and should not be treated as a schema validator.[^s1][^s2]

# Two lookup mechanisms with different guarantees
- mongo_id_candidates(value) yields the original string plus an ObjectId candidate when syntactically valid. It does **not** validate existence, authorization, or uniqueness.
- TenantScoped.resolve_id uses a tenant-scoped lookup with up to two matches; both a string and ObjectId with the same hex value cause ValueError. No match returns None. A non-hex legacy string is supported; it is not automatically malformed input.
- TenantScoped._scoped replaces caller-supplied tenant_id with its own tenant. Authentication and patient ownership checks remain separate from ID resolution.[^s1]

# Caller matrix
| Consumer | Resolution actually used | Ownership/error behavior | Review consequence |
|---|---|---|---|
| Engine booking/slot/contact helpers | resolve_id | detects ambiguous matching entity IDs | shared change reaches every [booking caller](booking-impact.md) |
| Owner GET booking | resolve_id then scoped read | no match 404, ambiguous 409; output serialized | keep HTTP error contract and tenant non-disclosure |
| Owner PATCH booking | engine; catches ValueError | ambiguous → 409, other value errors → 422 | not the same handler as POST |
| Owner POST booking | engine without the PATCH ValueError mapping | unsuccessful return → 400; ambiguous-ID ValueError is not mapped locally | follow-up regression needed before promising controlled collision response on every route |
| Inbound patient cancel/move | candidate-based contact queries, then contact-constrained engine/wrapper calls | current patient identity comes from worker routing | inspect both lookup selection and mutation constraints |
| Payment link creation | Contacts.resolve_id + Bookings.resolve_id | checks booking/contact relationship | preserve independent payment request and provider-link namespaces |
| Razorpay reconciliation | scoped booking find_one with mongo_id_candidates | checks account/amount/reference and cancelled state | candidate lookup does not detect same-hex collisions |
| Reminder scan | candidate-based slot/contact find_one | checks slot status + linked booking ID, then opt-out | generated-ID happy-path coverage does not establish collision rejection |
| Cancellation waitlist lookup / fulfillment | candidate slot lookup, direct waitlist reference comparisons | same tenant; mixed stored types still matter | compare both actual IDs and historical reference representations |

Sources correspond to base/engine, routes, inbound worker, payment creation, webhook, reminders, cancellation wrapper, and collection definitions respectively.[^s1][^s2][^s3][^s4][^s5][^s6][^s7][^s8][^s9]

# Invariants to check with any identifier change
1. Tenant A must never resolve or mutate Tenant B's entity through either representation.
2. A string/ObjectId collision must have an explicit error policy for each affected caller, not an assumed global guarantee.
3. Booking ↔ slot references must still identify the same stored entities after create, move, cancel, and retry.
4. Patient paths must preserve contact ownership independently of clinic access; administrative paths must preserve their role policy.
5. API/tool output must serialize IDs without rewriting primary IDs in the database.
6. Migration must inventory legacy strings, ObjectId-shaped strings, and conflicting historical references before normalization.

Use [the evidence matrix](booking-evidence.md) to choose actual tests. [Tenant isolation](tenant-isolation.md) supplies the broader boundary, and [booking impact](booking-impact.md) shows callers and side effects. Do not mark R03/R17 closed from this map.

# Sources
[^s1]: [app/models/base.py](file:///D:/XOLVER/Vaani/app/models/base.py)
[^s2]: [app/booking/engine.py](file:///D:/XOLVER/Vaani/app/booking/engine.py)
[^s3]: [app/owner_api/routes.py](file:///D:/XOLVER/Vaani/app/owner_api/routes.py)
[^s4]: [app/workers/inbound.py](file:///D:/XOLVER/Vaani/app/workers/inbound.py)
[^s5]: [app/agent/tools/payment_link_create.py](file:///D:/XOLVER/Vaani/app/agent/tools/payment_link_create.py)
[^s6]: [app/gateway/razorpay.py](file:///D:/XOLVER/Vaani/app/gateway/razorpay.py)
[^s7]: [app/workers/reminders.py](file:///D:/XOLVER/Vaani/app/workers/reminders.py)
[^s8]: [app/agent/tools/booking_cancel.py](file:///D:/XOLVER/Vaani/app/agent/tools/booking_cancel.py)
[^s9]: [app/models/collections.py](file:///D:/XOLVER/Vaani/app/models/collections.py)
