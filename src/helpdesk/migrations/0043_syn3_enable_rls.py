# synsmarts fork customization (v2.3.0-syn3): PostgreSQL Row-Level Security.
#
# The isolation-enforcement layer for the 9 tenant-owned models (ADR-0083).
# PostgreSQL-only (sqlite cannot represent RLS) — run with pg_test_settings.
#
#   1. Composite (parent_id, team_id) -> parent(id, team_id) foreign keys make
#      it structurally impossible for a child row to be attributed to a
#      different team than its parent. FK existence checks bypass RLS, so the
#      single-column Django FK alone would let a child reference another team's
#      parent; the composite FK closes that. Requires a UNIQUE(id, team_id) on
#      each parent as the FK target.
#   2. ENABLE + FORCE ROW LEVEL SECURITY + a team_isolation policy on each of the
#      9 tables. current_setting('app.current_team', true) returns NULL when the
#      GUC is unset (fail-safe: all rows blocked). FORCE so the table owner is
#      also subject; superusers and BYPASSRLS roles still bypass by design.
#   3. Three BYPASSRLS maintenance roles (DSAR export, admin export, aggregation)
#      — the ONLY sanctioned cross-team read path. Role EXISTENCE + attributes are
#      owned by CNPG spec.managed.roles on the django-db cluster (single owner per
#      ADR-0083 erratum 2026-06-23); this migration only GRANTs to them and assumes
#      they pre-exist — CNPG creates them in prod, the CI helpdesk PG migration gate
#      pre-creates them in tests. (The app role is NOCREATEROLE, so a CREATE ROLE
#      here never worked in prod anyway — it only ever no-op'd against CNPG-made
#      roles or failed.) Slice 2 extends the DSAR / admin GRANTs to the wrapper-
#      owned subscription + unrouted tables, which do not exist yet; this migration
#      grants only on fork-owned tables.
#   4. helpdesk_aggregate_v: cross-team aggregates grouped by team_id for billing.
#      The aggregation role gets SELECT on the VIEW only, never on helpdesk_ticket.
from django.db import migrations

TENANT_TABLES = [
    "helpdesk_ticket", "helpdesk_followup", "helpdesk_ticketchange",
    "helpdesk_followupattachment", "helpdesk_ticketcc",
    "helpdesk_ticketcustomfieldvalue", "helpdesk_ticketdependency",
    "helpdesk_checklist", "helpdesk_checklisttask",
]

# parent tables that are composite-FK targets -> need UNIQUE(id, team_id)
FK_PARENTS = ["helpdesk_ticket", "helpdesk_followup", "helpdesk_checklist"]

# (child_table, child_fk_column, parent_table, constraint_name)
COMPOSITE_FKS = [
    ("helpdesk_followup", "ticket_id", "helpdesk_ticket", "helpdesk_followup_team_fk"),
    ("helpdesk_ticketchange", "followup_id", "helpdesk_followup", "helpdesk_ticketchange_team_fk"),
    ("helpdesk_followupattachment", "followup_id", "helpdesk_followup", "helpdesk_fuattach_team_fk"),
    ("helpdesk_ticketcc", "ticket_id", "helpdesk_ticket", "helpdesk_ticketcc_team_fk"),
    ("helpdesk_ticketcustomfieldvalue", "ticket_id", "helpdesk_ticket", "helpdesk_tcfv_team_fk"),
    ("helpdesk_ticketdependency", "ticket_id", "helpdesk_ticket", "helpdesk_ticketdep_team_fk"),
    ("helpdesk_ticketdependency", "depends_on_id", "helpdesk_ticket", "helpdesk_ticketdep_dependson_team_fk"),
    ("helpdesk_checklist", "ticket_id", "helpdesk_ticket", "helpdesk_checklist_team_fk"),
    ("helpdesk_checklisttask", "checklist_id", "helpdesk_checklist", "helpdesk_checklisttask_team_fk"),
]

# DSAR + admin export read the ticket conversation across teams (fork tables only)
EXPORT_GRANT_TABLES = (
    "helpdesk_ticket, helpdesk_followup, helpdesk_followupattachment, "
    "helpdesk_ticketchange, helpdesk_ticketcc, helpdesk_queue"
)


forward = []
for p in FK_PARENTS:
    forward.append(f"ALTER TABLE {p} ADD CONSTRAINT {p}_id_team_uniq UNIQUE (id, team_id);")
for child, col, parent, cname in COMPOSITE_FKS:
    forward.append(
        f"ALTER TABLE {child} ADD CONSTRAINT {cname} "
        f"FOREIGN KEY ({col}, team_id) REFERENCES {parent} (id, team_id);"
    )
for t in TENANT_TABLES:
    forward.append(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;")
    forward.append(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY;")
    # NULLIF(...,'') so a pooled connection whose SET LOCAL app.current_team has
    # reverted to '' (PgBouncer reuse — the spec's own caveat) yields NULL and
    # blocks all rows (fail-safe), instead of erroring on ''::uuid (fail-open).
    forward.append(
        f"CREATE POLICY team_isolation ON {t} FOR ALL "
        f"USING (team_id = NULLIF(current_setting('app.current_team', true), '')::uuid) "
        f"WITH CHECK (team_id = NULLIF(current_setting('app.current_team', true), '')::uuid);"
    )
# Roles are CNPG-owned (see header note 3); GRANT only — they pre-exist.
forward.append(f"GRANT SELECT ON {EXPORT_GRANT_TABLES} TO helpdesk_dsar_role;")
forward.append(f"GRANT SELECT ON {EXPORT_GRANT_TABLES} TO helpdesk_admin_export_role;")
forward.append(
    "CREATE VIEW helpdesk_aggregate_v AS "
    "SELECT team_id, DATE(created) AS created_date, "
    "CASE WHEN status IN (1, 2, 3) THEN 'active' "
    "WHEN status IN (4, 5) THEN 'closed' END AS status_bucket, "
    "COUNT(*) AS count, "
    "COALESCE(SUM(LENGTH(description)::bigint), 0) AS total_bytes "
    "FROM helpdesk_ticket "
    "GROUP BY team_id, DATE(created), status_bucket;"
)
forward.append("GRANT SELECT ON helpdesk_aggregate_v TO helpdesk_aggregation_role;")

reverse = ["DROP VIEW IF EXISTS helpdesk_aggregate_v;"]
for t in TENANT_TABLES:
    reverse.append(f"DROP POLICY IF EXISTS team_isolation ON {t};")
    reverse.append(f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;")
    reverse.append(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;")
for child, col, parent, cname in COMPOSITE_FKS:
    reverse.append(f"ALTER TABLE {child} DROP CONSTRAINT IF EXISTS {cname};")
for p in FK_PARENTS:
    reverse.append(f"ALTER TABLE {p} DROP CONSTRAINT IF EXISTS {p}_id_team_uniq;")
# Roles are CNPG-owned (header note 3) — reverse REVOKEs the grants this migration
# made but does NOT drop the roles. Guarded: the role may be absent in a teardown
# context. helpdesk_aggregation_role's only grant was on helpdesk_aggregate_v,
# already cascade-dropped by the DROP VIEW above — no explicit REVOKE needed.
for r in ("helpdesk_dsar_role", "helpdesk_admin_export_role"):
    reverse.append(
        f"DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{r}') "
        f"THEN EXECUTE 'REVOKE SELECT ON {EXPORT_GRANT_TABLES} FROM {r}'; END IF; END $$;"
    )


def apply_rls(apps, schema_editor):
    # PostgreSQL-only: RLS, roles, and the composite-FK invariant have no sqlite
    # equivalent. The upstream unit suite runs on sqlite and does not exercise
    # RLS; it is validated on PostgreSQL by tests/rls_validation.py.
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("\n".join(forward))


def reverse_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("\n".join(reverse))


class Migration(migrations.Migration):

    dependencies = [
        ("helpdesk", "0042_syn2_add_platform_extension_fields"),
    ]

    operations = [
        migrations.RunPython(apply_rls, reverse_rls),
    ]
