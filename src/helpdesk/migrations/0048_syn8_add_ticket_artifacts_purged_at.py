"""Ticket attachment/session retention marker (ADR-0274 D7)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("helpdesk", "0047_syn7_add_ticket_agent_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="artifacts_purged_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
