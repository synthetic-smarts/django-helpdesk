"""Least-recently-emitted close retry ordering (ADR-0274 D2)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("helpdesk", "0048_syn8_add_ticket_artifacts_purged_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="agent_close_reemitted_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
