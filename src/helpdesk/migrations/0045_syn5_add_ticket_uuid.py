# synsmarts fork customization (v2.3.0-syn6): opaque ticket UUID.
#
# Adds Ticket.uuid — the customer-facing wire id for REST/MCP and the GitHub
# bridge label (helpdesk-ticket-{uuid}). The integer pk stays internal;
# exposing sequential ids would leak ticket volume + invite IDOR-probing
# (ADR-0083 Slice 3).
#
# Simple AddField is correct here: helpdesk_ticket is empty at every apply point
# (verified 0 rows in stage 2026-06-23; prod not yet bootstrapped; CI/dev start
# fresh) — no creation path exists until the Slice 3 API lands — so the single
# evaluated default never collides with the unique constraint, and the model's
# uuid4 default generates a distinct value per row on every future INSERT.
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("helpdesk", "0044_syn4_team_scoped_managers"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
