from celery import Celery
from celery.schedules import crontab

from app import app as flask_app


def create_celery(flask_app=None):
    celery = Celery(
        flask_app.import_name,
        broker=flask_app.config['CELERY_BROKER_URL'],
        backend=flask_app.config['CELERY_RESULT_BACKEND'],
    )
    celery.conf.update(
        task_track_started=flask_app.config.get('CELERY_TASK_TRACK_STARTED', True),
        task_time_limit=flask_app.config.get('CELERY_TASK_TIME_LIMIT', 1800),
        timezone=flask_app.config.get('APP_TIMEZONE', 'Asia/Kolkata'),
        enable_utc=False,
        beat_schedule={
            'daily-patient-reminders': {
                'task': 'hospital.daily_patient_reminders',
                'schedule': crontab(hour=8, minute=0),
            },
            'monthly-doctor-activity-reports': {
                'task': 'hospital.monthly_doctor_activity_reports',
                'schedule': crontab(hour=8, minute=30, day_of_month='1'),
            },
        },
    )

    class FlaskContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = FlaskContextTask
    return celery


celery = create_celery(flask_app)

import tasks
