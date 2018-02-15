from django.apps import AppConfig


class CoveredDataConfig(AppConfig):
    name = 'covered_data'

    def ready(self):
        """
        Overridden to include custom signals
        """
        import covered_data.signals  # noqa
