#!/usr/bin/env python3
"""RLS validation for the synsmarts fork (1d, ADR-0083). PostgreSQL only.

Run:  DJANGO_SETTINGS_MODULE=pg_test_settings python tests/rls_validation.py
(after `python manage.py migrate`). Exits non-zero on any failed assertion;
this is the CI gate for RLS read/write isolation (ADR-0083 acceptance #1/#2/#18).

Not named test_*.py on purpose: the upstream unittest suite runs on sqlite,
which cannot represent RLS. This script drives a real PostgreSQL connection and
drops to a non-BYPASSRLS role (superusers bypass RLS) to observe enforcement.

Covers: same-team visibility, cross-team invisibility, INSERT/UPDATE WITH CHECK
enforcement, child composite-FK team inheritance, and that the BYPASSRLS
maintenance roles are the only cross-team read path.
"""
import os
import sys
import uuid

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pg_test_settings")
django.setup()

from django.db import connection, transaction  # noqa: E402

APP_ROLE = "helpdesk_app_test"  # NOBYPASSRLS stand-in for the production app role
TEAM_A = uuid.uuid4()
TEAM_B = uuid.uuid4()

_failures = []


def check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        _failures.append(name)


def raises(fn):
    """True if fn() raises a database error (rolled back in its own savepoint)."""
    try:
        with transaction.atomic():
            fn()
        return False
    except Exception:
        return True


def setup_roles_and_seed():
    if connection.vendor != "postgresql":
        print(f"SKIP: engine is {connection.vendor}, not postgresql")
        sys.exit(0)
    with connection.cursor() as cur:
        cur.execute(
            f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{APP_ROLE}') "
            f"THEN CREATE ROLE {APP_ROLE} NOLOGIN NOBYPASSRLS; END IF; END $$;"
        )
        cur.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE};"
        )
        cur.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE};")
    # Seed as superuser (RLS bypassed): one ticket + one follow-up per team.
    from helpdesk.models import Queue, Ticket, FollowUp

    q, _ = Queue.objects.get_or_create(slug="rlsq", defaults={"title": "RLS Q"})
    ids = {}
    for team in (TEAM_A, TEAM_B):
        t = Ticket.objects.create(queue=q, title=f"t-{team}", team_id=team)
        FollowUp.objects.create(ticket=t, title="f", team_id=team)
        ids[team] = t.id
    return ids


def as_app(team, body):
    """Run body(cur) as the non-BYPASSRLS app role with app.current_team=team."""
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute("SET LOCAL ROLE %s" % APP_ROLE)
        if team is not None:
            cur.execute("SELECT set_config('app.current_team', %s, true)", [str(team)])
        return body(cur)


def main():
    ids = setup_roles_and_seed()
    print("RLS validation (PostgreSQL %s):" % connection.pg_version)

    # 1. same-team visibility
    def count_visible(cur):
        cur.execute("SELECT count(*) FROM helpdesk_ticket")
        return cur.fetchone()[0]

    check("1. same-team visibility", as_app(TEAM_A, count_visible) == 1)

    # 2. cross-team invisibility (team A's row invisible under team B)
    def a_invisible_under_b(cur):
        cur.execute("SELECT count(*) FROM helpdesk_ticket WHERE id = %s", [ids[TEAM_A]])
        return cur.fetchone()[0]

    check("2. cross-team invisibility", as_app(TEAM_B, a_invisible_under_b) == 0)

    # 3a. INSERT with foreign team_id rejected (WITH CHECK)
    from helpdesk.models import Queue

    qid = Queue.objects.get(slug="rlsq").id

    ticket_insert = (
        "INSERT INTO helpdesk_ticket (title, created, modified, status, priority, "
        "on_hold, secret_key, queue_id, team_id, source, is_archived) "
        "VALUES ('x', now(), now(), 1, 3, false, 'k', %s, %s, 'api', false)"
    )

    def insert_ticket_as(team_ctx, team_val):
        def _fn():
            with connection.cursor() as cur:
                cur.execute("SET LOCAL ROLE %s" % APP_ROLE)
                cur.execute("SELECT set_config('app.current_team', %s, true)", [str(team_ctx)])
                cur.execute(ticket_insert, [qid, str(team_val)])
        return _fn

    check("3a. INSERT foreign team_id rejected (WITH CHECK)",
          raises(insert_ticket_as(TEAM_A, TEAM_B)))
    check("3b. INSERT own team_id accepted",
          not raises(insert_ticket_as(TEAM_A, TEAM_A)))

    # 4. UPDATE moving a row to another team rejected (WITH CHECK)
    def update_team():
        with connection.cursor() as cur:
            cur.execute("SET LOCAL ROLE %s" % APP_ROLE)
            cur.execute("SELECT set_config('app.current_team', %s, true)", [str(TEAM_A)])
            cur.execute(
                "UPDATE helpdesk_ticket SET team_id = %s WHERE id = %s",
                [str(TEAM_B), ids[TEAM_A]],
            )

    check("4. UPDATE to foreign team_id rejected (WITH CHECK)", raises(update_team))

    # 5. child composite-FK team inheritance: follow-up team must match its ticket
    followup_insert = (
        "INSERT INTO helpdesk_followup (title, date, public, ticket_id, team_id, source) "
        "VALUES (%s, now(), false, %s, %s, 'api')"
    )

    def insert_followup(team_val):
        def _fn():
            # superuser context so RLS doesn't mask the composite-FK error
            with connection.cursor() as cur:
                cur.execute(followup_insert, ["fu", ids[TEAM_A], str(team_val)])
        return _fn

    check("5a. child team != parent team rejected (composite FK)",
          raises(insert_followup(TEAM_B)))
    check("5b. child team == parent team accepted",
          not raises(insert_followup(TEAM_A)))

    # 6. BYPASSRLS roles are the only cross-team path
    def app_no_context(cur):
        cur.execute("SET LOCAL ROLE %s" % APP_ROLE)  # no app.current_team set
        cur.execute("SELECT count(*) FROM helpdesk_ticket")
        return cur.fetchone()[0]

    check("6a. app role with no team context sees 0 rows (fail-safe)",
          as_app(None, app_no_context) == 0)

    def dsar_sees_all(cur):
        cur.execute("SET LOCAL ROLE helpdesk_dsar_role")  # BYPASSRLS
        cur.execute("SELECT count(DISTINCT team_id) FROM helpdesk_ticket")
        return cur.fetchone()[0]

    with transaction.atomic(), connection.cursor() as c:
        c.execute("SET LOCAL ROLE helpdesk_dsar_role")
        c.execute("SELECT count(DISTINCT team_id) FROM helpdesk_ticket WHERE team_id IN (%s, %s)",
                  [str(TEAM_A), str(TEAM_B)])
        teams_seen = c.fetchone()[0]
    check("6b. BYPASSRLS maintenance role sees all teams", teams_seen == 2)

    with connection.cursor() as c:
        c.execute(
            "SELECT rolname, rolbypassrls FROM pg_roles WHERE rolname IN "
            "(%s, 'helpdesk_dsar_role', 'helpdesk_admin_export_role', 'helpdesk_aggregation_role')",
            [APP_ROLE],
        )
        bypass = {r[0]: r[1] for r in c.fetchall()}
    check("6c. app role is NOT BYPASSRLS", bypass.get(APP_ROLE) is False)
    check("6d. exactly the 3 maintenance roles have BYPASSRLS",
          sum(1 for k, v in bypass.items() if v and k != APP_ROLE) == 3)

    # cleanup seeded rows + role
    from helpdesk.models import Ticket
    Ticket.objects.filter(team_id__in=[TEAM_A, TEAM_B]).delete()
    with connection.cursor() as cur:
        cur.execute("DELETE FROM helpdesk_ticket WHERE team_id IN (%s, %s)",
                    [str(TEAM_A), str(TEAM_B)])

    print()
    if _failures:
        print(f"FAILED: {len(_failures)} scenario(s): {_failures}")
        sys.exit(1)
    print("ALL RLS SCENARIOS PASS")


if __name__ == "__main__":
    main()
