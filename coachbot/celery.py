from celery import Celery
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coachbot.settings")

app = Celery("coachbot")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
