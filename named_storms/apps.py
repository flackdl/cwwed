from django.apps import AppConfig


class NamedStormsConfig(AppConfig):
    name = 'named_storms'

    def ready(self):
        """
        Overridden to include custom signals and to
        load modules which are only dynamically imported which prevents django's autoreload mechanism from working (dev)
        """
        import named_storms.signals  # noqa
        import named_storms.data.processors  # noqa
        import named_storms.data.factory  # noqa
        import cwwed.storage_backends  # noqa
