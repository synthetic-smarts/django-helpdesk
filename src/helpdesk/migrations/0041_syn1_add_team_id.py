# synsmarts fork customization (v2.3.0-syn1): add team_id RLS isolation key.
#
# Adds team_id (UUIDField, db_index, non-nullable) — the account boundary
# (Team per ADR-0105/0124) and the PostgreSQL RLS isolation key — to the
# tenant-owned ticket data tree ONLY. Per the ADR-0083 re-scope (2026-06-21),
# team_id/RLS applies to the 9 models that hold customer ticket data, NOT to
# django-helpdesk's staff/system-owned config (Queue, EmailTemplate, KB,
# CustomField definitions, PreSetReply, EscalationExclusion, IgnoreEmail,
# SavedSearch, UserSettings, ChecklistTemplate). RLS policies land in 1d.
# preserve_default=False populates any pre-existing rows during the add but
# keeps the model field default-free. Reversible (rollback drops the column).
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("helpdesk", "0040_remove_kbitem_team"),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='team_id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='followup',
            name='team_id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='ticketchange',
            name='team_id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='followupattachment',
            name='team_id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='ticketcc',
            name='team_id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='ticketcustomfieldvalue',
            name='team_id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='ticketdependency',
            name='team_id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='checklist',
            name='team_id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='checklisttask',
            name='team_id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4),
            preserve_default=False,
        ),
    ]
