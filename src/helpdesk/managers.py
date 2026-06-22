"""Team-scoping managers for the fork's 9 tenant-owned models (ADR-0083, slice 1e).

`current_team_id` is the request/activity-scoped team. The wrapper's
SetTeamContextMiddleware and @with_team_context decorator (Slice 2) BIND it; the
fork only READS it here. The managers are assigned ONLY to the 9 tenant-owned
models (the ticket data tree) — never to the system/staff-owned config models,
which carry no team_id.

`TeamScopedManager.get_queryset()` adds `.filter(team_id=current_team)` WHEN a
team is bound, and passes through UNFILTERED when none is bound.

    WARNING — the unset-context pass-through is NOT a safety property by itself.
    It is acceptable ONLY because PostgreSQL Row-Level Security (migration
    0043_syn3_enable_rls) is the real enforcement boundary: on a non-BYPASSRLS
    connection with no `app.current_team` set, RLS returns ZERO rows (fail-safe),
    so an un-contexted query cannot leak cross-team data in production. On sqlite
    (the upstream unit suite) there is no RLS and pass-through returns all rows —
    that is why the upstream tests keep working, NOT a claim that bare ORM access
    is safe. Deliberate cross-team access is the explicit `upstream_objects`
    escape hatch (allow-listed, audited), never an un-contexted default query.

`objects` (the scoped manager) is the default manager — the safe path. Each model
sets `Meta.base_manager_name = "upstream_objects"` so Django internals and
related-object fetches (`ticket.followup_set`, FK validation) use the UNSCOPED
manager — otherwise a privileged cross-team fetch via `upstream_objects` followed
by a relation traversal would wrongly re-scope to the ambient team and drop rows.
"""
from contextvars import ContextVar
from uuid import UUID

from django.db import models

current_team_id: "ContextVar[UUID | None]" = ContextVar("current_team_id", default=None)


class TeamScopedManagerMixin:
    """Mix into any Manager to scope its queryset to the bound team when set."""

    def get_queryset(self):
        qs = super().get_queryset()
        team = current_team_id.get()
        if team is None:
            return qs
        return qs.filter(team_id=team)


class TeamScopedManager(TeamScopedManagerMixin, models.Manager):
    pass
