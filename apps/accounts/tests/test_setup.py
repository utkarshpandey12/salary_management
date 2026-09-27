import django
import pytest


@pytest.mark.django_db
class TestSetup:
    def test_django_boots(self):
        assert django.get_version().startswith("5.")

    def test_skeleton_has_no_app_models_yet(self):
        from django.apps import apps as dj_apps

        assert dj_apps.get_app_config("accounts") is not None
        assert dj_apps.get_app_config("employees") is not None
