---
type: "Invariant"
title: "Tenant and identifier boundaries"
description: "Explicit clinic context and MongoDB identifiers constrain data access."
status: "draft"
generated: {"by": "codex/booking-impact-map", "at": "2026-11-09T11:38:56.821259+00:00"}
source_commit: "804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4"
source_paths: ["app/models/base.py", "app/models/collections.py", "tests/test_tenant_isolation.py", "tests/test_generated_objectid_boundaries.py"]
source_hashes: {"app/models/base.py": "f2141ff668fa8c6ea338b5ce667c7cb5e4c0129b6ce5c796565c387064483f10", "app/models/collections.py": "e18443ad6693cff6445447e5a6a0cbc38cb177818a1ebfbdae2926cf69bce8b1", "tests/test_tenant_isolation.py": "6415d6f89e3c1e42be11a0ddc1b8dc60dc53387818ce19feee42970b9dc27d24", "tests/test_generated_objectid_boundaries.py": "20ffd2d35af52ed926ae84b191ee5e687fadac6f14b8f4cb6f015e8f73ad69eb"}
sources: [{"id": "s1", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/models/base.py", "title": "app/models/base.py"}, {"id": "s2", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/models/collections.py", "title": "app/models/collections.py"}, {"id": "s3", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_tenant_isolation.py", "title": "tests/test_tenant_isolation.py"}, {"id": "s4", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_generated_objectid_boundaries.py", "title": "tests/test_generated_objectid_boundaries.py"}]
source_snapshot: "Reviewed local working tree on 2026-11-09; immutable citation URLs refer to the committed baseline, while fingerprints include the local changes noted below."
---
# Implemented boundary
TenantScoped requires a non-empty tenant ID. Its scoped query overwrites any caller-supplied tenant_id with the accessor's tenant ID. MongoDB ID candidates support legacy string and generated ObjectId representations; serialization converts ObjectIds at output boundaries.[^s1]

# Important exception
The Tenants accessor has explicit platform-level lookup and scan methods. Review those methods separately; do not infer that every method in the models package is automatically tenant-filtered.[^s2]

# Change impact
[Booking](booking.md), [retrieval](retrieval.md), [handoff](handoff.md), and [delivery](delivery.md) depend on tenant context. Relationships in this graph never replace authorization filters.

# Verify
Review cross-clinic and generated-ID regressions for every affected API/tool path. Broader identifier acceptance remains tracked in [release evidence](release-evidence.md).

# Source references
[^s1]: [app/models/base.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/models/base.py)
[^s2]: [app/models/collections.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/models/collections.py)
[^s3]: [tests/test_tenant_isolation.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_tenant_isolation.py)
[^s4]: [tests/test_generated_objectid_boundaries.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_generated_objectid_boundaries.py)

# Working-tree reconciliation
The current working tree also adds Tenants.update_settings, matching the tenant document by _id. Review that platform-level method along with the lookup and scan exceptions.

# Booking-specific identifier map
See [identifier contracts](identifier-contracts.md) for representation and caller differences, [booking impact](booking-impact.md) for mutation paths, and [booking evidence](booking-evidence.md) for coverage limits.
