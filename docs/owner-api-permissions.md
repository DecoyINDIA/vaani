# Owner API permissions

All `/api` business routes require an active `owner` or `staff` membership in
the tenant carried by an access-purpose token. Collection access is scoped to
that tenant; external record IDs from another tenant return no record.

| Capability | Staff | Owner |
| --- | --- | --- |
| Conversations, messages, takeover, reply, resolve/return | Yes | Yes |
| Appointments: list, create, cancel, reschedule | Yes | Yes |
| Escalations, knowledge base, metrics, clinic settings: read | Yes | Yes |
| Knowledge base: update | Yes | Yes |
| Clinic settings: update | No | Yes |
| Audit export | No | Yes |
| Invite owner/staff memberships | No | Yes |

Removed or inactive memberships are rejected on every request. Session-bound
access tokens are rejected after logout or refresh-session revocation.
