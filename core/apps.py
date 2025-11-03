# apps/core/apps.py  (or apps/academics/apps.py)
import os
from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        """
        Avoid double-start in autoreloader and avoid running during management commands
        like 'makemigrations', 'migrate', 'collectstatic', etc.
        """
        from django.conf import settings

        # Only start in runserver / gunicorn main process
        is_runserver = os.environ.get("RUN_MAIN") == "true" or os.environ.get("WERKZEUG_RUN_MAIN") == "true"
        # If you prefer, also guard by settings.DEBUG or a custom flag
        if not is_runserver:
            return

        # Start the scheduler
        try:
            from apps.academics.scheduler import start_scheduler
            start_scheduler()
        except Exception as e:
            # Don't crash Django if scheduler init fails
            print("[Scheduler init skipped]", e)
