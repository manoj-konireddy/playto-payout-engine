import os
from datetime import timedelta

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'process-payouts-every-5-seconds': {
        'task': 'payouts.tasks.process_payouts',
        'schedule': timedelta(seconds=5),
    }
}
