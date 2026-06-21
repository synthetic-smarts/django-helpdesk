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
# a default team_id at instance construction (before validation, before save,
# and for bulk_create which skips save signals), standing in for the future
# middleware write-path so the upstream suite passes without editing its ~47
# call sites (which we re-inherit on every upstream rebase). Test-only: the
# `tests` package is never imported in production. Explicit team_id values and
# values loaded from the DB are preserved; only None is defaulted. Slice 2
# replaces this shim with the real ContextVar/manager/middleware.
TEST_DEFAULT_TEAM_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


@receiver(post_init)
def _bind_default_team_id(sender, instance, **kwargs):
    if not any(f.name == "team_id" for f in instance._meta.fields):
        return
    if "team_id" in instance.get_deferred_fields():
        return
    if getattr(instance, "team_id", None) is None:
        instance.team_id = TEST_DEFAULT_TEAM_ID
