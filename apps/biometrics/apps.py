from django.apps import AppConfig
class BiometricsConfig(AppConfig):
    name = "apps.biometrics"
    def ready(self):
        from . import signals  # noqa
