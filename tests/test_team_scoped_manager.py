"""1e: the tenant-scoped default manager + explicit upstream_objects escape hatch.

App-layer behavior only (no RLS needed) — runs on the sqlite upstream suite.
RLS enforcement is covered separately by tests/rls_validation.py on PostgreSQL.
"""
import uuid

from django.test import TestCase

from helpdesk.managers import current_team_id
from helpdesk.models import Queue, Ticket


class TeamScopedManagerTests(TestCase):
    def setUp(self):
        self.q = Queue.objects.create(slug="tsm", title="TSM")
        self.team_a = uuid.uuid4()
        self.team_b = uuid.uuid4()
        # explicit team_id so the post_init shim preserves it (does not assign fresh)
        Ticket.objects.create(queue=self.q, title="a", team_id=self.team_a)
        Ticket.objects.create(queue=self.q, title="b", team_id=self.team_b)

    def tearDown(self):
        current_team_id.set(None)

    def test_passthrough_when_no_context(self):
        # pass-through is NOT a safety property — RLS is the real boundary on
        # Postgres; here it only keeps un-contexted queries from breaking.
        current_team_id.set(None)
        self.assertEqual(Ticket.objects.count(), 2)

    def test_scoped_when_context_set(self):
        token = current_team_id.set(self.team_a)
        try:
            self.assertEqual(Ticket.objects.count(), 1)
            self.assertEqual(Ticket.objects.get().team_id, self.team_a)
        finally:
            current_team_id.reset(token)

    def test_upstream_objects_is_unscoped_escape_hatch(self):
        current_team_id.set(self.team_a)
        self.assertEqual(Ticket.upstream_objects.count(), 2)

    def test_base_manager_is_unscoped(self):
        # related-object / internal fetches use _base_manager (= upstream_objects)
        current_team_id.set(self.team_a)
        self.assertEqual(Ticket._base_manager.count(), 2)

    def test_default_manager_is_scoped(self):
        # the safe path is the default: _default_manager scopes when context is set
        current_team_id.set(self.team_b)
        self.assertEqual(Ticket._default_manager.count(), 1)
