# synsmarts fork changelog

This is the internalized synsmarts fork of django-helpdesk (ADR-0083). Entries
record the synsmarts customizations layered on the upstream baseline; upstream's
own history is in the git log. Tag scheme: `vX.Y.Z-synN` (X.Y.Z = upstream
baseline at fork-cut, only bumped on a deliberate rebase; synN increments per
synsmarts patch).

## Invariant: the SES-inbound entry point

**`helpdesk.email.create_object_from_email_message` is the invariant entry point
for inbound email → Ticket/FollowUp creation.** It MUST NOT be removed even if
upstream's POP3/IMAP polling helpers (`pop3_sync`, `imap_sync`, `imap_oauth_sync`,
`process_queue`) are pruned in a future rebase cleanup. The function may evolve
(parameter additions, internal refactors) but its identity and its role as the
single Ticket/FollowUp-creating choke point are preserved.

It is **fail-closed on team attribution**: `team_id` is keyword-required and the
function raises if it is missing/empty. The fork trusts ONLY the explicit
`team_id` it is handed by the caller (the Slice 8 SES consumer, after its own
routing/validation) — never the sender address, never an ambient ContextVar,
never RLS. Missing/ambiguous attribution must route to `UnroutedEmail` upstream,
never create a tenant row here.

## v2.3.0-syn5 — email entry-point team-scoping + POP3/IMAP fail-closed (1f)

- `create_object_from_email_message`: added keyword-required `team_id` + optional
  `tenant_id`, with an explicit no-team guard. Ticket gets `team_id`+`tenant_id`;
  FollowUp gets `team_id`. In-Reply-To and ticket-id lookups filter explicitly by
  `team_id` (same-team threading only — no cross-team merge). `extract_email_metadata`
  threads `team_id`/`tenant_id` through.
- Child propagation: `subscribe_to_ticket_updates` (TicketCC) and
  `process_attachments` (FollowUpAttachment) now set `team_id = parent.team_id`
  (the child-inherits-parent invariant, DB-enforced by the 1d composite FK).
- POP3/IMAP polling is fail-closed: the polling path reaches the entry point with
  no team and raises, creating no tenant row. The `runqueue`/`get_email` command
  is never invoked from any synsmarts entry point (SES→S3 is the only inbound).

## v2.3.0-syn4 — team-scoped managers + `upstream_objects` escape hatch (1e)
## v2.3.0-syn3 — PostgreSQL Row-Level Security + composite-FK inheritance + roles (1d)
## v2.3.0-syn2 — platform extension fields + per-account dedup indexes (1c)
## v2.3.0-syn1 — team_id RLS isolation key on the tenant-owned ticket tree (1b); pinax-teams removed
## v2.3.0-syn0 — fork-cut baseline (upstream 2.3.0, no changes)
