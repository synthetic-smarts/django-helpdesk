# import all test_*.py files in directory.
# necessary for automatic discovery in django <= 1.5
# http://stackoverflow.com/a/15780326/1382740

import unittest
import uuid

from django.db.models.signals import post_init
from django.dispatch import receiver


def suite():
    return unittest.TestLoader().discover("helpdesk.tests", pattern="test_*.py")


# --- synsmarts fork: test-only team-context shim -----------------------------
# team_id is a NOT NULL RLS isolation key (ADR-0083) on the 9 tenant-owned
# models. In production it is populated from the request's team by the wrapper
# ContextVar + SetTeamContextMiddleware + team-scoped managers, which land in
# Slice 2. Until that exists, upstream tests that create rows with no team
# bound trip the constraint — at model validation (full_clean) for the form
# paths and at the DB for the bare-save paths. This post_init receiver supplies
# a team_id at instance construction (before validation, before save, and for
# bulk_create which skips save signals), standing in for the future middleware
# write-path so the upstream suite passes without editing its ~47 call sites
# (which we re-inherit on every upstream rebase).
#
# Binding model: each Ticket-thread is its own team (a fresh UUID per root
# Ticket); every child row inherits its parent's team_id by walking the FK
# chain to its owning Ticket. This mirrors production (distinct emails/recipients
# resolve to distinct teams; a reply inherits its ticket's team), so the
# per-account dedup unique indexes (team_id, message_id) / (team_id,
# email_message_id) / (team_id, idempotency_key) only fire on genuine same-team
# duplicates — not on logically-distinct upstream-test rows that a single
# constant team would have falsely collapsed. It also satisfies 1d's composite
# (parent_id, team_id) FK, where child.team_id must equal its parent's.
#
# Test-only: the `tests` package is never imported in production. Explicit
# team_id values and values loaded from the DB are preserved; only None is
# defaulted. Slice 2 replaces this shim with the real ContextVar/manager/
# middleware.
_PARENT_FKS = ("ticket", "followup", "checklist")


def _resolve_team_id(instance, _depth=0):
    """Inherit the owning Ticket's team; a root/unparented row gets a fresh team."""
    if _depth > 8:
        return uuid.uuid4()
    field_names = {f.name for f in instance._meta.fields}
    for fk in _PARENT_FKS:
        if fk not in field_names or getattr(instance, f"{fk}_id", None) is None:
            continue
        parent = getattr(instance, fk, None)
        if parent is None:
            continue
        parent_team = getattr(parent, "team_id", None)
        if parent_team is None:
            parent_team = _resolve_team_id(parent, _depth + 1)
            parent.team_id = parent_team
        return parent_team
    return uuid.uuid4()


@receiver(post_init)
def _bind_default_team_id(sender, instance, **kwargs):
    if not any(f.name == "team_id" for f in instance._meta.fields):
        return
    if "team_id" in instance.get_deferred_fields():
        return
    if getattr(instance, "team_id", None) is None:
        instance.team_id = _resolve_team_id(instance)
