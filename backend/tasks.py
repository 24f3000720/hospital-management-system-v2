from calendar import monthrange
from csv import writer
from datetime import datetime, timedelta
from pathlib import Path

from flask import current_app

from celery_app import celery
from extensions import db
from mail import ensure_runtime_dir, send_mail_message
from models import Appointment, ExportJob, User
from pdf_report import write_simple_pdf


def _export_dir():
    return ensure_runtime_dir(current_app.config.get('EXPORTS_DIR', 'instance/exports'))


def _report_dir():
    return ensure_runtime_dir(current_app.config.get('REPORTS_DIR', 'instance/reports'))


def _month_window(reference_date=None):
    reference_date = reference_date or datetime.now().date()
    first_day_this_month = reference_date.replace(day=1)
    last_day_previous_month = first_day_this_month - timedelta(days=1)
    first_day_previous_month = last_day_previous_month.replace(day=1)
    return first_day_previous_month, last_day_previous_month


def resolve_report_window(report_month=None, report_year=None):
    if report_month and report_year:
        start_date = datetime(int(report_year), int(report_month), 1).date()
        _, last_day = monthrange(int(report_year), int(report_month))
        return start_date, start_date.replace(day=last_day)

    return _month_window()


def send_daily_reminder_for_appointment(appointment):
    subject = f'Reminder: Hospital visit at {appointment.appointment_date.strftime("%I:%M %p")}'
    html_body = f"""
    <html>
      <body>
        <h2>Appointment Reminder</h2>
        <p>Dear {appointment.patient.name},</p>
        <p>This is a reminder for your scheduled hospital appointment.</p>
        <ul>
          <li>Doctor: {appointment.doctor.name}</li>
          <li>Specialization: {appointment.doctor.specialization or 'N/A'}</li>
          <li>Date: {appointment.appointment_date.strftime("%B %d, %Y")}</li>
          <li>Time: {appointment.appointment_date.strftime("%I:%M %p")}</li>
        </ul>
        <p>Please arrive on time for your visit.</p>
      </body>
    </html>
    """
    text_body = (
        f'Appointment reminder for {appointment.patient.name}: '
        f'{appointment.doctor.name} on {appointment.appointment_date.strftime("%B %d, %Y at %I:%M %p")}.'
    )

    return send_mail_message(
        subject=subject,
        recipients=[appointment.patient.email],
        html_body=html_body,
        text_body=text_body,
        category='daily-reminder',
    )


def send_monthly_report_for_doctor(doctor, start_date, end_date):
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    monthly_appointments = Appointment.query.filter(
        Appointment.f_doctor_uid == doctor.uid,
        Appointment.appointment_date >= start_dt,
        Appointment.appointment_date <= end_dt,
    ).order_by(Appointment.appointment_date).all()

    rows = ''.join(
        f"""
        <tr>
          <td>{appointment.patient.name if appointment.patient else 'N/A'}</td>
          <td>{appointment.appointment_date.strftime("%Y-%m-%d")}</td>
          <td>{appointment.status}</td>
          <td>{appointment.diagnosis or 'N/A'}</td>
          <td>{appointment.prescription or 'N/A'}</td>
        </tr>
        """
        for appointment in monthly_appointments
    ) or '<tr><td colspan="5">No appointments for this month.</td></tr>'

    html_body = f"""
    <html>
      <body>
        <h2>Monthly Activity Report</h2>
        <p>Doctor: {doctor.name}</p>
        <p>Reporting window: {start_date.strftime("%B %Y")}</p>
        <table border="1" cellspacing="0" cellpadding="8">
          <thead>
            <tr>
              <th>Patient</th>
              <th>Date</th>
              <th>Status</th>
              <th>Diagnosis</th>
              <th>Prescription</th>
            </tr>
          </thead>
          <tbody>
            {rows}
          </tbody>
        </table>
      </body>
    </html>
    """
    text_body = (
        f'Monthly report for {doctor.name} covering {start_date.strftime("%B %Y")} '
        f'with {len(monthly_appointments)} appointments.'
    )

    report_lines = [
        f'Doctor: {doctor.name}',
        f'Email: {doctor.email}',
        f'Reporting window: {start_date.strftime("%B %Y")}',
        f'Total appointments: {len(monthly_appointments)}',
        '',
    ]

    if monthly_appointments:
        for index, appointment in enumerate(monthly_appointments, start=1):
            report_lines.extend([
                f'{index}. Patient: {appointment.patient.name if appointment.patient else "N/A"}',
                f'   Date: {appointment.appointment_date.strftime("%Y-%m-%d %I:%M %p")}',
                f'   Status: {appointment.status}',
                f'   Diagnosis: {appointment.diagnosis or "N/A"}',
                f'   Prescription: {appointment.prescription or "N/A"}',
                '',
            ])
    else:
        report_lines.append('No appointments were recorded for this doctor during the reporting period.')

    report_file_name = f'doctor_report_{doctor.uid}_{start_date.strftime("%Y_%m")}.pdf'
    report_path = _report_dir() / report_file_name
    write_simple_pdf(
        report_path,
        f'Monthly Activity Report - {start_date.strftime("%B %Y")}',
        report_lines,
    )

    delivery = send_mail_message(
        subject=f'Monthly Activity Report - {start_date.strftime("%B %Y")}',
        recipients=[doctor.email],
        html_body=html_body,
        text_body=text_body,
        category='monthly-report',
        attachment_path=report_path,
    )

    return {
        'doctor_uid': doctor.uid,
        'doctor_email': doctor.email,
        'appointment_count': len(monthly_appointments),
        'delivery': delivery,
        'report_path': str(report_path),
    }


def send_export_ready_email(export_job):
    patient = export_job.patient
    return send_mail_message(
        subject='Your treatment export is ready',
        recipients=[patient.email],
        html_body=f"""
        <html>
          <body>
            <h2>Treatment Export Ready</h2>
            <p>Dear {patient.name}, your treatment history export has been generated successfully.</p>
            <p>File: {export_job.file_name}</p>
          </body>
        </html>
        """,
        text_body='Your treatment history export has been generated successfully.',
        category='patient-export',
        attachment_path=export_job.file_path,
    )


@celery.task(name='hospital.debug_ping')
def debug_ping():
    return {'status': 'ok', 'message': 'Celery worker is connected'}


@celery.task(name='hospital.daily_patient_reminders')
def daily_patient_reminders(patient_uid=None):
    today = datetime.now().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())

    appointments_query = Appointment.query.filter(
        Appointment.status == 'scheduled',
        Appointment.appointment_date >= start_of_day,
        Appointment.appointment_date <= end_of_day,
    )

    if patient_uid is not None:
        appointments_query = appointments_query.filter(Appointment.f_patient_uid == patient_uid)

    appointments = appointments_query.order_by(Appointment.appointment_date).all()

    reminder_count = 0
    deliveries = []

    for appointment in appointments:
        if not appointment.patient or not appointment.doctor:
            continue

        deliveries.append(send_daily_reminder_for_appointment(appointment))
        reminder_count += 1

    return {
        'status': 'completed',
        'date': today.isoformat(),
        'reminders_sent': reminder_count,
        'deliveries': deliveries,
    }


@celery.task(name='hospital.monthly_doctor_activity_reports')
def monthly_doctor_activity_reports(report_month=None, report_year=None, doctor_uid=None):
    start_date, end_date = resolve_report_window(report_month, report_year)

    doctors_query = User.query.filter_by(f_rid=3, blacklisted=False)
    if doctor_uid is not None:
        doctors_query = doctors_query.filter_by(uid=doctor_uid)
    doctors = doctors_query.all()
    deliveries = []

    for doctor in doctors:
        deliveries.append(send_monthly_report_for_doctor(doctor, start_date, end_date))

    return {
        'status': 'completed',
        'month': start_date.month,
        'year': start_date.year,
        'reports_sent': len(deliveries),
        'deliveries': deliveries,
    }


@celery.task(name='hospital.export_patient_treatment_csv')
def export_patient_treatment_csv(export_job_id):
    export_job = ExportJob.query.get(export_job_id)
    if not export_job:
        return {'status': 'failed', 'message': 'Export job not found'}

    export_job.status = 'running'
    db.session.commit()

    patient = export_job.patient
    exports_dir = _export_dir()
    file_name = f'treatment_history_{patient.uid}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    file_path = exports_dir / file_name

    try:
        appointments = Appointment.query.filter(
            Appointment.f_patient_uid == patient.uid,
            Appointment.status == 'completed',
        ).order_by(Appointment.appointment_date.desc()).all()

        with file_path.open('w', newline='', encoding='utf-8') as csv_file:
            csv_writer = writer(csv_file)
            csv_writer.writerow([
                'user_id',
                'username',
                'consulting_doctor',
                'doctor_specialization',
                'appointment_date',
                'appointment_time',
                'diagnosis',
                'treatment_given',
                'doctor_notes',
                'next_visit_suggested',
            ])

            for appointment in appointments:
                csv_writer.writerow([
                    patient.uid,
                    patient.name,
                    appointment.doctor.name if appointment.doctor else 'N/A',
                    appointment.doctor.specialization if appointment.doctor else 'N/A',
                    appointment.appointment_date.strftime('%Y-%m-%d'),
                    appointment.appointment_date.strftime('%I:%M %p'),
                    appointment.diagnosis or '',
                    appointment.prescription or '',
                    appointment.doctor_notes or '',
                    '',
                ])

        export_job.status = 'completed'
        export_job.file_name = file_name
        export_job.file_path = str(file_path)
        export_job.message = 'Treatment history export is ready for download.'
        export_job.completed_at = datetime.now()
        db.session.commit()

        send_export_ready_email(export_job)

        return {
            'status': 'completed',
            'export_job_id': export_job.id,
            'file_name': file_name,
            'file_path': str(file_path),
        }
    except Exception as exc:
        export_job.status = 'failed'
        export_job.error_message = str(exc)
        export_job.completed_at = datetime.now()
        db.session.commit()
        raise
