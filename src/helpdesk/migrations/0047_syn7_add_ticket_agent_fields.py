# synsmarts fork customization (v2.3.0-syn13): ticket agent channel and session generation.
#
# Ticket.agent_channel_id binds the private ADR-0274 Slack channel; null means
# unbound or archived. Ticket.agent_session_generation rejects stale session
# writes after the ticket's attachment/session purge.
#
# Plain AddField is safe: a nullable char and an integer default of zero
# introduce no unique values and require no data backfill.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("helpdesk", "0046_syn6_index_attachment_file"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="agent_channel_id",
            field=models.CharField(max_length=32, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="ticket",
            name="agent_session_generation",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
