# Tenant onboarding

Production tenant onboarding accepts validated JSON. Start from
`ops/tenant-config.example.json`; the file contains credential references, not secrets.

Validate and preview without writing:

```powershell
uv run python -m ops.onboard_tenant --config .\tenant.json
```

Apply only after reviewing the preview. The confirmation value must exactly match the
configured tenant ID:

```powershell
uv run python -m ops.onboard_tenant --config .\tenant.json --apply --confirm clinic_slug
```

The apply operation upserts the declared tenant and practitioners, then expands 30 days
of slots. It is safe to rerun: unique slot constraints prevent duplicates, and omitted
practitioners, slots, and bookings are never deleted. A practitioner ID already owned by
another tenant is rejected.

Set the environment variable named by `whatsapp.access_token_env` in the deployment
secret store before enabling outbound messages. Never put the access token in the JSON.
The production deployment must also provide the normal fail-closed Vaani configuration
and must not enable `VAANI_USE_MOCKS`.

`ops/seed_tenant.py --demo` remains for isolated development and tests only. It is not a
production onboarding path.
