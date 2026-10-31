from django.apps import AppConfig


class ConferencesConfig(AppConfig):
    name = 'conferences'

    def ready(self):
        # Windows may otherwise serve ES modules as text/plain, which browsers reject.
        import mimetypes
        mimetypes.add_type("application/javascript", ".mjs", strict=True)
