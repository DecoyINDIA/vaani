# Authentication secret rotation

Rotating `JWT_SECRET` invalidates access, refresh, invitation, and voice-grant
signatures immediately. Perform this as a scheduled security operation; do not
reuse an old secret after compromise.

1. Pause invitation issuance and announce a dashboard sign-in interruption.
2. Generate a cryptographically random value of at least 32 bytes in the secret
   manager. Never place it in source control, shell history, tickets, or logs.
3. In the same maintenance window, mark every unrevoked `auth_sessions` record
   with `revoked_at`. This prevents a rollback to the old signing secret from
   making prior refresh sessions valid again. Record only counts and timestamps.
4. Update `JWT_SECRET` for API and worker services, then redeploy both from the
   same tested image. Do not run mixed secrets concurrently.
5. Verify unsafe/default secrets fail startup, old access/refresh/invitation and
   voice grants return 401, and a newly invited synthetic user can sign in,
   refresh once, and log out.
6. Resume invitation issuance. Retain the old secret only in the controlled
   secret-manager recovery history, then destroy it under the organization’s
   approved rotation policy after the rollback window.

If compromise is suspected, skip the announcement delay: revoke sessions,
rotate, redeploy, and require every owner/staff user to authenticate again.
