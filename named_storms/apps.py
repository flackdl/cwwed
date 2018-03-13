from django.apps import AppConfig


class NamedStormsConfig(AppConfig):
    name = 'named_storms'

    def ready(self):
        """
        Overridden to include custom signals
        """
        import named_storms.signals  # noqa
