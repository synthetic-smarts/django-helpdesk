from django.apps import AppConfig


class HelpdeskConfig(AppConfig):
    name = "helpdesk"
    verbose_name = "Helpdesk"
    # for Django 3.2 support:
    # see:
    # https://docs.djangoproject.com/en/3.2/ref/applications/#django.apps.AppConfig.default_auto_field
    default_auto_field = "django.db.models.AutoField"

    def ready(self):
        from . import webhooks  # noqa: F401

        # Register the `length` lookup on TextField for body-length
        # CheckConstraints. Assert no other installed app registered a different
        # `length` lookup first — the second registration silently wins and the
        # constraints would misbehave (spec-helpdesk §Length lookup).
        from django.db.models import TextField
        from django.db.models.functions import Length

        existing = TextField.get_lookups().get("length")
        assert existing in (None, Length), (
            "TextField 'length' lookup already registered by another app "
            f"({existing!r}) — body-length CheckConstraints may misbehave"
        )
        TextField.register_lookup(Length)
