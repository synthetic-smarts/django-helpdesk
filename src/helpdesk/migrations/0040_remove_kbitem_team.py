# synsmarts fork customization: remove django-helpdesk "teams mode" (pinax-teams).
#
# Drops the kbitem.team FK added by 0028_kbitem_team. The platform isolates by
# team_id (PostgreSQL RLS, ADR-0083), not by KBItem-team assignment routing; the
# pinax-teams feature and its runtime code were removed in the same commit.
# History (0028) is left intact and replays on a fresh DB; this migration drops
# the column forward. Fresh fork, no prior data.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("helpdesk", "0039_alter_ticketchange_field"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="kbitem",
            name="team",
        ),
    ]
