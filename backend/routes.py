import re
from datetime import datetime, timedelta, time as timetype
from pathlib import Path

from flask import flash, jsonify, redirect, render_template, request, send_file, send_from_directory, session
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import aliased

from cache import build_cache_key, get_cached_json, invalidate_cache_prefixes, set_cached_json
from extensions import db
from mail import send_mail_message
from models import Appointment, Department, DoctorAvailability, ExportJob, Payment, User


EMAIL_REGEX = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
CARD_NUMBER_REGEX = re.compile(r'^\d{12,19}$')
EXPIRY_REGEX = re.compile(r'^(0[1-9]|1[0-2])/\d{2}$')
CVV_REGEX = re.compile(r'^\d{3,4}$')
FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent / 'frontend' / 'dist'
MAX_PROFILE_IMAGE_DATA_LENGTH = 1_500_000


def check_login():
    return 'email' in session


def get_current_user():
    if check_login():
        return User.query.filter_by(email=session['email']).first()
    return None


def get_user_role():
    return session.get('f_rid')


def get_or_create_department(dept_name):
    dept = Department.query.filter(Department.name.ilike(dept_name.strip())).first()
    if not dept:
        dept = Department(name=dept_name.strip())
        db.session.add(dept)
        db.session.commit()
    return dept


def get_filtered_doctors(search_query):
    query = User.query.filter_by(f_rid=3, blacklisted=False)

    if search_query:
        query = query.join(Department, User.f_did == Department.did, isouter=True)
        query = query.filter(or_(
            cast(User.uid, String).ilike(f'%{search_query}%'),
            User.name.ilike(f'%{search_query}%'),
            User.email.ilike(f'%{search_query}%'),
            User.specialization.ilike(f'%{search_query}%'),
            Department.name.ilike(f'%{search_query}%')
        ))

    return query.all()


def get_filtered_patients(search_query):
    query = User.query.filter_by(f_rid=2, blacklisted=False)

    if search_query:
        query = query.filter(or_(
            cast(User.uid, String).ilike(f'%{search_query}%'),
            User.name.ilike(f'%{search_query}%'),
            User.email.ilike(f'%{search_query}%')
        ))

    return query.all()


def get_filtered_appointments(search_query, appointment_tab):
    PatientUser = aliased(User)
    DoctorUser = aliased(User)

    query = db.session.query(Appointment)\
        .join(PatientUser, Appointment.f_patient_uid == PatientUser.uid)\
        .join(DoctorUser, Appointment.f_doctor_uid == DoctorUser.uid)

    if appointment_tab == 'upcoming':
        query = query.filter(
            Appointment.appointment_date >= datetime.now(),
            Appointment.status == 'scheduled'
        )
    else:
        query = query.filter(or_(
            Appointment.appointment_date < datetime.now(),
            Appointment.status != 'scheduled'
        ))

    if search_query:
        query = query.filter(or_(
            cast(PatientUser.uid, String).ilike(f'%{search_query}%'),
            PatientUser.name.ilike(f'%{search_query}%'),
            PatientUser.email.ilike(f'%{search_query}%'),
            cast(DoctorUser.uid, String).ilike(f'%{search_query}%'),
            DoctorUser.name.ilike(f'%{search_query}%'),
            DoctorUser.email.ilike(f'%{search_query}%'),
            DoctorUser.specialization.ilike(f'%{search_query}%')
        ))

    return query.order_by(Appointment.appointment_date).all()


def get_latest_completed_export_job(patient_uid):
    return ExportJob.query.filter_by(patient_uid=patient_uid, status='completed')\
        .order_by(ExportJob.completed_at.desc(), ExportJob.id.desc()).first()


def check_doctor_unavailability(doctor_uid, slot_str):
    return DoctorAvailability.query.filter(
        DoctorAvailability.doctor_uid == doctor_uid,
        DoctorAvailability.slot_str == slot_str,
        DoctorAvailability.available == False
    ).first() is not None


def check_patient_booking_conflict(patient_uid, slot_datetime):
    return Appointment.query.filter(
        Appointment.f_patient_uid == patient_uid,
        Appointment.status == 'scheduled',
        Appointment.appointment_date == slot_datetime
    ).first() is not None


def generate_booking_slots(doctor, patient, now, booked_slots):
    slot_sections = {}

    time_slots = [
        (9, 0, "9AM", "11AM"),
        (12, 0, "12PM", "2PM"),
        (15, 0, "3PM", "5PM"),
        (18, 0, "6PM", "8PM"),
    ]

    for day_offset in range(8):
        current_date = now.date() + timedelta(days=day_offset)

        if day_offset == 0:
            date_label = "Today"
        elif day_offset == 1:
            date_label = "Tomorrow"
        else:
            date_label = current_date.strftime("%B %d, %Y")

        day_slots = []
        for hour, minute, start_label, end_label in time_slots:
            slot_start = datetime.combine(current_date, timetype(hour, minute))
            slot_str = slot_start.strftime('%Y-%m-%dT%H:%M')

            is_past = (day_offset == 0 and now > slot_start)
            is_booked = slot_str in booked_slots
            is_unavailable = check_doctor_unavailability(doctor.uid, slot_str)
            is_patient_booked = check_patient_booking_conflict(patient.uid, slot_start)

            disabled = is_past or is_booked or is_unavailable or is_patient_booked

            day_slots.append({
                'slot_str': slot_str,
                'start': start_label,
                'end': end_label,
                'disabled': disabled
            })

        slot_sections[date_label] = day_slots

    return slot_sections


def parse_request_data():
    return request.get_json(silent=True) or request.form


def error_response(message, status_code=400):
    return jsonify({'success': False, 'message': message}), status_code


def success_response(message, data=None, status_code=200):
    payload = {'success': True, 'message': message}
    if data is not None:
        payload['data'] = data
    return jsonify(payload), status_code


def get_or_set_cache(prefix, suffix, builder, timeout=None):
    cache_key = build_cache_key(prefix, suffix)
    cached_payload = get_cached_json(cache_key)
    if cached_payload is not None:
        return cached_payload

    payload = builder()
    set_cached_json(cache_key, payload, timeout=timeout)
    return payload


def invalidate_shared_caches():
    invalidate_cache_prefixes(
        'departments',
        'doctors',
        'admin_stats',
        'admin_analytics',
        'admin_doctors',
        'admin_patients',
        'admin_appointments',
    )


def validate_email_value(email, required=True):
    email = (email or '').strip()
    if required and not email:
        return None, 'Email is required'
    if email and not EMAIL_REGEX.match(email):
        return None, 'Enter a valid email address'
    return email, None


def validate_name_value(name, field_name='Name', required=True):
    name = (name or '').strip()
    if required and not name:
        return None, f'{field_name} is required'
    if name and len(name) < 2:
        return None, f'{field_name} must be at least 2 characters long'
    if len(name) > 120:
        return None, f'{field_name} must be shorter than 120 characters'
    return name, None


def validate_password_value(password, required=False):
    password = password or ''
    if required and not password:
        return None, 'Password is required'
    if password and len(password) < 6:
        return None, 'Password must be at least 6 characters long'
    return password, None


def validate_optional_text(value, field_name, min_length=2, max_length=120):
    value = (value or '').strip()
    if not value:
        return '', None
    if len(value) < min_length:
        return None, f'{field_name} must be at least {min_length} characters long'
    if len(value) > max_length:
        return None, f'{field_name} must be shorter than {max_length} characters'
    return value, None


def validate_non_negative_int(value, field_name='Value'):
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return None, f'{field_name} must be a number'
    if parsed < 0:
        return None, f'{field_name} cannot be negative'
    return parsed, None


def validate_appointment_datetime(appointment_datetime):
    if appointment_datetime < datetime.now():
        return 'Appointment must be scheduled for a future time'
    return None


def validate_slot_string(slot_str):
    slot_str = (slot_str or '').strip()
    if not slot_str:
        return None, 'slot_str is required'
    try:
        datetime.fromisoformat(slot_str)
    except ValueError:
        return None, 'slot_str must be a valid ISO datetime'
    return slot_str, None


def validate_profile_image_data(profile_image_data):
    if profile_image_data is None:
        return None, None

    profile_image_data = profile_image_data.strip()
    if not profile_image_data:
        return '', None

    if not profile_image_data.startswith('data:image/'):
        return None, 'Profile image must be a valid image file'

    if len(profile_image_data) > MAX_PROFILE_IMAGE_DATA_LENGTH:
        return None, 'Profile image is too large. Please use a smaller image.'

    return profile_image_data, None


def get_frontend_index_path():
    index_path = FRONTEND_DIST_DIR / 'index.html'
    return index_path if index_path.exists() else None


def serve_frontend_index():
    index_path = get_frontend_index_path()
    if index_path:
        response = send_file(index_path)
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return None


def require_login_api():
    user = get_current_user()
    if not user:
        return None, error_response('Authentication required', 401)
    return user, None


def require_role_api(*allowed_roles):
    user, error = require_login_api()
    if error:
        return None, error
    if user.f_rid not in allowed_roles:
        return None, error_response('Access denied', 403)
    return user, None


def serialize_department(department):
    if not department:
        return None

    return {
        'did': department.did,
        'name': department.name,
        'description': getattr(department, 'description', None),
        'doctors_registered': len(getattr(department, 'doctors', []))
    }


def serialize_user(user):
    return {
        'uid': user.uid,
        'name': user.name,
        'email': user.email,
        'profile_image_data': user.profile_image_data,
        'specialization': user.specialization,
        'experience_years': user.experience_years,
        'blacklisted': user.blacklisted,
        'role_id': user.f_rid,
        'department': serialize_department(user.department)
    }


def serialize_appointment(appt):
    return {
        'aid': appt.aid,
        'patient_id': appt.f_patient_uid,
        'doctor_id': appt.f_doctor_uid,
        'date': appt.appointment_date.strftime('%Y-%m-%d'),
        'time': appt.appointment_date.strftime('%H:%M'),
        'appointment_datetime': appt.appointment_date.isoformat(),
        'completed_at': appt.completed_at.isoformat() if getattr(appt, 'completed_at', None) else None,
        'status': appt.status,
        'diagnosis': appt.diagnosis,
        'prescription': appt.prescription,
        'doctor_notes': appt.doctor_notes,
        'patient': {
            'uid': appt.patient.uid,
            'name': appt.patient.name,
            'email': appt.patient.email
        } if appt.patient else None,
        'doctor': {
            'uid': appt.doctor.uid,
            'name': appt.doctor.name,
            'email': appt.doctor.email,
            'specialization': appt.doctor.specialization
        } if appt.doctor else None
    }


def serialize_availability(availability):
    return {
        'id': availability.id,
        'doctor_uid': availability.doctor_uid,
        'slot_str': availability.slot_str,
        'available': availability.available
    }


def serialize_export_job(export_job):
    return {
        'id': export_job.id,
        'patient_uid': export_job.patient_uid,
        'export_type': export_job.export_type,
        'status': export_job.status,
        'celery_task_id': export_job.celery_task_id,
        'file_name': export_job.file_name,
        'message': export_job.message,
        'error_message': export_job.error_message,
        'created_at': export_job.created_at.isoformat() if export_job.created_at else None,
        'completed_at': export_job.completed_at.isoformat() if export_job.completed_at else None,
    }


def serialize_payment(payment):
    if not payment:
        return None

    return {
        'id': payment.id,
        'patient_uid': payment.patient_uid,
        'appointment_id': payment.appointment_id,
        'amount': payment.amount,
        'currency': payment.currency,
        'card_holder': payment.card_holder,
        'card_last4': payment.card_last4,
        'payment_status': payment.payment_status,
        'payment_reference': payment.payment_reference,
        'created_at': payment.created_at.isoformat() if payment.created_at else None,
        'paid_at': payment.paid_at.isoformat() if payment.paid_at else None,
    }


def calculate_dummy_payment_amount(appointment):
    specialization = (appointment.doctor.specialization or '').lower() if appointment.doctor else ''

    if 'surgery' in specialization:
        return 1200
    if 'cardio' in specialization:
        return 900
    if 'ent' in specialization:
        return 700
    return 600


def parse_appointment_datetime(data):
    appointment_datetime = data.get('appointment_datetime')
    if appointment_datetime:
        return datetime.fromisoformat(appointment_datetime)

    appointment_date = data.get('date')
    appointment_time = data.get('time')
    if appointment_date and appointment_time:
        return datetime.fromisoformat(f'{appointment_date}T{appointment_time}')

    raise ValueError('Missing appointment date/time')


def doctor_is_available_for_slot(doctor_uid, appointment_datetime):
    slot_str = appointment_datetime.strftime('%Y-%m-%dT%H:%M')

    unavailable = DoctorAvailability.query.filter_by(
        doctor_uid=doctor_uid,
        slot_str=slot_str,
        available=False
    ).first()
    if unavailable:
        return False

    booked = Appointment.query.filter_by(
        f_doctor_uid=doctor_uid,
        appointment_date=appointment_datetime,
        status='scheduled'
    ).first()
    return booked is None


def patient_has_conflict(patient_uid, appointment_datetime, exclude_appointment_id=None):
    query = Appointment.query.filter_by(
        f_patient_uid=patient_uid,
        appointment_date=appointment_datetime,
        status='scheduled'
    )

    if exclude_appointment_id is not None:
        query = query.filter(Appointment.aid != exclude_appointment_id)

    return query.first() is not None


def filter_doctors_for_api(search_query='', specialization='', department_name='', available_on=''):
    query = User.query.filter_by(f_rid=3, blacklisted=False)

    if search_query or department_name:
        query = query.join(Department, User.f_did == Department.did, isouter=True)

    if search_query:
        query = query.filter(or_(
            cast(User.uid, String).ilike(f'%{search_query}%'),
            User.name.ilike(f'%{search_query}%'),
            User.email.ilike(f'%{search_query}%'),
            User.specialization.ilike(f'%{search_query}%'),
            Department.name.ilike(f'%{search_query}%')
        ))

    if specialization:
        query = query.filter(User.specialization.ilike(f'%{specialization}%'))

    if department_name:
        query = query.filter(Department.name.ilike(f'%{department_name}%'))

    doctors = query.all()

    if available_on:
        try:
            slot_datetime = datetime.fromisoformat(available_on)
        except ValueError:
            return None, 'Invalid availability datetime'

        doctors = [
            doctor for doctor in doctors
            if doctor_is_available_for_slot(doctor.uid, slot_datetime)
        ]

    return doctors, None
def register_routes(app):
    @app.route('/api/health', methods=['GET'])
    def health_check_api():
        return success_response('API is working', {'status': 'ok'})

    @app.route('/api/auth/register', methods=['POST'])
    def api_register():
        data = parse_request_data()

        name, error_message = validate_name_value(data.get('name'), 'Name')
        if error_message:
            return error_response(error_message)

        email, error_message = validate_email_value(data.get('email'))
        if error_message:
            return error_response(error_message)

        password, error_message = validate_password_value(data.get('password', ''), required=True)
        if error_message:
            return error_response(error_message)

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return error_response('User already exists', 409)

        new_user = User(
            name=name,
            email=email,
            password=password,
            f_rid=2
        )
        db.session.add(new_user)
        db.session.commit()
        invalidate_shared_caches()

        return success_response('Patient registered successfully', {'user': serialize_user(new_user)}, 201)

    @app.route('/api/auth/login', methods=['POST'])
    def api_login():
        data = parse_request_data()

        email, error_message = validate_email_value(data.get('email'))
        if error_message:
            return error_response(error_message)

        password, error_message = validate_password_value(data.get('password', ''), required=True)
        if error_message:
            return error_response(error_message)

        user = User.query.filter_by(email=email, blacklisted=False).first()
        if not user or user.password != password:
            return error_response('Invalid credentials', 401)

        session['email'] = user.email
        session['f_rid'] = user.f_rid

        return success_response('Login successful', {'user': serialize_user(user)})

    @app.route('/api/auth/logout', methods=['POST'])
    def api_logout():
        session.clear()
        return success_response('Logout successful')

    @app.route('/api/auth/me', methods=['GET'])
    def api_me():
        user, error = require_login_api()
        if error:
            return error
        return success_response('Current user fetched successfully', {'user': serialize_user(user)})

    @app.route('/api/departments', methods=['GET'])
    def api_departments():
        data = get_or_set_cache(
            'departments',
            'all',
            lambda: {
                'departments': [
                    serialize_department(department)
                    for department in Department.query.order_by(Department.name).all()
                ]
            },
            timeout=app.config.get('CACHE_DEPARTMENTS_TIMEOUT')
        )
        return success_response(
            'Departments fetched successfully',
            data
        )

    @app.route('/api/doctors', methods=['GET'])
    def api_doctors():
        search_query = request.args.get('search', '').strip()
        specialization = request.args.get('specialization', '').strip()
        department_name = request.args.get('department', '').strip()
        available_on = request.args.get('available_on', '').strip()

        def build_doctors_payload():
            doctors, error = filter_doctors_for_api(search_query, specialization, department_name, available_on)
            if error:
                raise ValueError(error)

            return {'doctors': [serialize_user(doctor) for doctor in doctors]}

        cache_suffix = f'search={search_query}|specialization={specialization}|department={department_name}|available_on={available_on}'

        try:
            data = get_or_set_cache(
                'doctors',
                cache_suffix,
                build_doctors_payload,
                timeout=app.config.get('CACHE_DOCTORS_TIMEOUT')
            )
        except ValueError as exc:
            return error_response(str(exc))

        return success_response(
            'Doctors fetched successfully',
            data
        )

    @app.route('/api/doctors/<int:uid>', methods=['GET'])
    def api_doctor_detail(uid):
        doctor = User.query.filter_by(uid=uid, f_rid=3, blacklisted=False).first()
        if not doctor:
            return error_response('Doctor not found', 404)

        return success_response('Doctor fetched successfully', {'doctor': serialize_user(doctor)})

    @app.route('/api/doctors/<int:uid>/availability', methods=['GET'])
    def api_doctor_availability(uid):
        doctor = User.query.filter_by(uid=uid, f_rid=3, blacklisted=False).first()
        if not doctor:
            return error_response('Doctor not found', 404)

        availabilities = DoctorAvailability.query.filter_by(doctor_uid=uid).order_by(DoctorAvailability.slot_str).all()
        return success_response(
            'Doctor availability fetched successfully',
            {'doctor_uid': uid, 'availability': [serialize_availability(item) for item in availabilities]}
        )

    @app.route('/api/patient/profile', methods=['GET', 'PUT'])
    def api_patient_profile():
        patient, error = require_role_api(2)
        if error:
            return error

        if request.method == 'GET':
            return success_response('Patient profile fetched successfully', {'patient': serialize_user(patient)})

        data = parse_request_data()
        new_name, error_message = validate_name_value(data.get('name', patient.name), 'Name')
        if error_message:
            return error_response(error_message)

        new_email, error_message = validate_email_value(data.get('email', patient.email))
        if error_message:
            return error_response(error_message)

        new_password, error_message = validate_password_value(data.get('password'), required=False)
        if error_message:
            return error_response(error_message)
        profile_image_data, error_message = validate_profile_image_data(data.get('profile_image_data'))
        if error_message:
            return error_response(error_message)

        if new_email != patient.email and User.query.filter_by(email=new_email).first():
            return error_response('Email already exists', 409)

        patient.name = new_name
        patient.email = new_email
        if new_password:
            patient.password = new_password
        if profile_image_data is not None:
            patient.profile_image_data = profile_image_data or None

        db.session.commit()
        session['email'] = patient.email
        invalidate_cache_prefixes('admin_patients', 'admin_analytics')

        return success_response('Patient profile updated successfully', {'patient': serialize_user(patient)})

    @app.route('/api/patient/appointments', methods=['GET', 'POST'])
    def api_patient_appointments():
        patient, error = require_role_api(2)
        if error:
            return error

        if request.method == 'GET':
            appointments = Appointment.query.filter_by(f_patient_uid=patient.uid)\
                .order_by(Appointment.appointment_date.desc()).all()
            return success_response(
                'Patient appointments fetched successfully',
                {'appointments': [serialize_appointment(appt) for appt in appointments]}
            )

        data = parse_request_data()
        doctor_id = data.get('doctor_id')
        if not doctor_id:
            return error_response('doctor_id is required')

        doctor = User.query.filter_by(uid=doctor_id, f_rid=3, blacklisted=False).first()
        if not doctor:
            return error_response('Doctor not found', 404)

        try:
            appointment_datetime = parse_appointment_datetime(data)
        except ValueError as exc:
            return error_response(str(exc))

        appointment_error = validate_appointment_datetime(appointment_datetime)
        if appointment_error:
            return error_response(appointment_error)

        if patient_has_conflict(patient.uid, appointment_datetime):
            return error_response('Patient already has an appointment at this time', 409)

        if not doctor_is_available_for_slot(doctor.uid, appointment_datetime):
            return error_response('Doctor is not available at this time', 409)

        appointment = Appointment(
            f_patient_uid=patient.uid,
            f_doctor_uid=doctor.uid,
            appointment_date=appointment_datetime,
            status='scheduled'
        )
        db.session.add(appointment)
        db.session.commit()
        invalidate_cache_prefixes('admin_stats', 'admin_appointments', 'admin_analytics', 'doctors')

        return success_response('Appointment booked successfully', {'appointment': serialize_appointment(appointment)}, 201)

    @app.route('/api/patient/appointments/<int:aid>/reschedule', methods=['PUT'])
    def api_patient_reschedule_appointment(aid):
        patient, error = require_role_api(2)
        if error:
            return error

        appointment = Appointment.query.get_or_404(aid)
        if appointment.f_patient_uid != patient.uid:
            return error_response('Unauthorized', 403)

        if appointment.status != 'scheduled':
            return error_response('Only scheduled appointments can be rescheduled', 400)

        data = parse_request_data()
        try:
            new_datetime = parse_appointment_datetime(data)
        except ValueError as exc:
            return error_response(str(exc))

        appointment_error = validate_appointment_datetime(new_datetime)
        if appointment_error:
            return error_response(appointment_error)

        if patient_has_conflict(patient.uid, new_datetime, exclude_appointment_id=appointment.aid):
            return error_response('Patient already has an appointment at this time', 409)

        if not doctor_is_available_for_slot(appointment.f_doctor_uid, new_datetime):
            return error_response('Doctor is not available at this time', 409)

        appointment.appointment_date = new_datetime
        db.session.commit()
        invalidate_cache_prefixes('admin_appointments', 'admin_analytics', 'doctors')

        return success_response('Appointment rescheduled successfully', {'appointment': serialize_appointment(appointment)})

    @app.route('/api/patient/appointments/<int:aid>/cancel', methods=['POST'])
    def api_patient_cancel_appointment(aid):
        patient, error = require_role_api(2)
        if error:
            return error

        appointment = Appointment.query.get_or_404(aid)
        if appointment.f_patient_uid != patient.uid:
            return error_response('Unauthorized', 403)

        appointment.status = 'cancelled'
        appointment.completed_at = None
        db.session.commit()
        invalidate_cache_prefixes('admin_stats', 'admin_appointments', 'admin_analytics', 'doctors')

        return success_response('Appointment cancelled successfully', {'appointment': serialize_appointment(appointment)})

    @app.route('/api/patient/doctors/<int:uid>/slots', methods=['GET'])
    def api_patient_doctor_slots(uid):
        patient, error = require_role_api(2)
        if error:
            return error

        doctor = User.query.filter_by(uid=uid, f_rid=3, blacklisted=False).first()
        if not doctor:
            return error_response('Doctor not found', 404)

        now = datetime.now()
        booked_appointments = Appointment.query.filter(
            Appointment.f_doctor_uid == doctor.uid,
            Appointment.status == 'scheduled',
            Appointment.appointment_date >= now
        ).all()
        booked_slots = [appt.appointment_date.strftime('%Y-%m-%dT%H:%M') for appt in booked_appointments]
        slot_sections = generate_booking_slots(doctor, patient, now, booked_slots)

        return success_response(
            'Doctor booking slots fetched successfully',
            {
                'doctor': serialize_user(doctor),
                'slot_sections': slot_sections
            }
        )

    @app.route('/api/patient/exports', methods=['GET'])
    def api_patient_exports():
        patient, error = require_role_api(2)
        if error:
            return error

        export_jobs = ExportJob.query.filter_by(patient_uid=patient.uid)\
            .order_by(ExportJob.created_at.desc()).all()

        return success_response(
            'Patient exports fetched successfully',
            {'exports': [serialize_export_job(export_job) for export_job in export_jobs]}
        )

    @app.route('/api/patient/exports/treatments', methods=['POST'])
    def api_patient_treatment_export():
        patient, error = require_role_api(2)
        if error:
            return error

        export_job = ExportJob(
            patient_uid=patient.uid,
            export_type='treatment_history_csv',
            status='queued',
            message='Treatment history export has been queued.',
        )
        db.session.add(export_job)
        db.session.commit()

        from tasks import export_patient_treatment_csv

        task = export_patient_treatment_csv.delay(export_job.id)
        export_job.celery_task_id = task.id
        db.session.commit()

        return success_response(
            'Treatment export started successfully',
            {'export': serialize_export_job(export_job)},
            202
        )

    @app.route('/api/patient/exports/<int:export_id>/download', methods=['GET'])
    def api_patient_export_download(export_id):
        patient, error = require_role_api(2)
        if error:
            return error

        export_job = ExportJob.query.get_or_404(export_id)
        if export_job.patient_uid != patient.uid:
            return error_response('Unauthorized', 403)

        if export_job.status != 'completed' or not export_job.file_path:
            return error_response('Export is not ready for download yet', 400)

        return send_file(export_job.file_path, as_attachment=True, download_name=export_job.file_name)

    @app.route('/api/patient/jobs/daily-reminder/send-now', methods=['POST'])
    def api_patient_send_daily_reminder_now():
        patient, error = require_role_api(2)
        if error:
            return error

        today = datetime.now().date()
        appointment = Appointment.query.filter(
            Appointment.f_patient_uid == patient.uid,
            Appointment.status == 'scheduled',
            Appointment.appointment_date >= datetime.combine(today, datetime.min.time()),
            Appointment.appointment_date <= datetime.combine(today, datetime.max.time()),
        ).order_by(Appointment.appointment_date).first()

        if not appointment:
            return error_response('No same-day scheduled appointment is available for a reminder right now', 400)

        from tasks import send_daily_reminder_for_appointment

        delivery = send_daily_reminder_for_appointment(appointment)
        return success_response(
            'Reminder email sent successfully',
            {'appointment': serialize_appointment(appointment), 'delivery': delivery}
        )

    @app.route('/api/patient/jobs/export-alert/send-now', methods=['POST'])
    def api_patient_send_export_alert_now():
        patient, error = require_role_api(2)
        if error:
            return error

        export_job = get_latest_completed_export_job(patient.uid)
        if not export_job or not export_job.file_path:
            return error_response('No completed treatment document is available to email right now', 400)

        from tasks import send_export_ready_email

        delivery = send_export_ready_email(export_job)
        return success_response(
            'Treatment document email sent successfully',
            {'export': serialize_export_job(export_job), 'delivery': delivery}
        )

    @app.route('/api/patient/payments', methods=['GET', 'POST'])
    def api_patient_payments():
        patient, error = require_role_api(2)
        if error:
            return error

        if request.method == 'GET':
            completed_appointments = Appointment.query.filter(
                Appointment.f_patient_uid == patient.uid,
                Appointment.status == 'completed',
            ).order_by(Appointment.completed_at.desc(), Appointment.appointment_date.desc()).all()

            payment_items = []
            for appointment in completed_appointments:
                payment_items.append({
                    'appointment': serialize_appointment(appointment),
                    'payment': serialize_payment(appointment.payment),
                    'amount_due': calculate_dummy_payment_amount(appointment),
                })

            return success_response(
                'Patient payments fetched successfully',
                {'payments': payment_items}
            )

        data = parse_request_data()
        appointment_id = data.get('appointment_id')
        if not appointment_id:
            return error_response('appointment_id is required')

        try:
            appointment_id = int(appointment_id)
        except (TypeError, ValueError):
            return error_response('appointment_id must be a valid number')

        appointment = Appointment.query.get_or_404(appointment_id)
        if appointment.f_patient_uid != patient.uid:
            return error_response('Unauthorized', 403)

        if appointment.status != 'completed':
            return error_response('Payment is only available for completed treatments', 400)

        if appointment.payment:
            return error_response('Payment has already been recorded for this appointment', 409)

        card_holder, error_message = validate_name_value(data.get('card_holder'), 'Card holder')
        if error_message:
            return error_response(error_message)

        card_number = re.sub(r'\D+', '', str(data.get('card_number', '')).strip())
        if not CARD_NUMBER_REGEX.match(card_number):
            return error_response('Card number must contain 12 to 19 digits')

        expiry = str(data.get('expiry', '')).strip()
        if not EXPIRY_REGEX.match(expiry):
            return error_response('Expiry must be in MM/YY format')

        cvv = str(data.get('cvv', '')).strip()
        if not CVV_REGEX.match(cvv):
            return error_response('CVV must contain 3 or 4 digits')

        amount = calculate_dummy_payment_amount(appointment)
        payment_reference = f'PAY-{appointment.aid}-{datetime.now().strftime("%Y%m%d%H%M%S")}'

        payment = Payment(
            patient_uid=patient.uid,
            appointment_id=appointment.aid,
            amount=amount,
            currency='INR',
            card_holder=card_holder,
            card_last4=card_number[-4:],
            payment_status='paid',
            payment_reference=payment_reference,
            paid_at=datetime.now(),
        )
        db.session.add(payment)
        db.session.commit()

        try:
            send_mail_message(
                subject='Dummy payment receipt',
                recipients=[patient.email],
                html_body=f"""
                <html>
                  <body>
                    <h2>Dummy Payment Receipt</h2>
                    <p>Dear {patient.name},</p>
                    <p>Your dummy payment has been recorded successfully for the completed treatment.</p>
                    <ul>
                      <li>Doctor: {appointment.doctor.name if appointment.doctor else 'N/A'}</li>
                      <li>Amount: INR {amount}</li>
                      <li>Reference: {payment_reference}</li>
                      <li>Card ending: {card_number[-4:]}</li>
                    </ul>
                  </body>
                </html>
                """,
                text_body=f'Dummy payment recorded. Reference: {payment_reference}. Amount: INR {amount}.',
                category='payment-receipt',
            )
        except Exception:
            pass

        return success_response(
            'Dummy payment recorded successfully',
            {
                'payment': serialize_payment(payment),
                'appointment': serialize_appointment(appointment),
            },
            201,
        )

    @app.route('/api/doctor/profile', methods=['GET', 'PUT'])
    def api_doctor_profile():
        doctor, error = require_role_api(3)
        if error:
            return error

        if request.method == 'GET':
            return success_response('Doctor profile fetched successfully', {'doctor': serialize_user(doctor)})

        data = parse_request_data()
        new_name, error_message = validate_name_value(data.get('name', doctor.name), 'Name')
        if error_message:
            return error_response(error_message)

        new_email, error_message = validate_email_value(data.get('email', doctor.email))
        if error_message:
            return error_response(error_message)

        new_password, error_message = validate_password_value(data.get('password'), required=False)
        if error_message:
            return error_response(error_message)
        profile_image_data, error_message = validate_profile_image_data(data.get('profile_image_data'))
        if error_message:
            return error_response(error_message)

        specialization, error_message = validate_optional_text(
            data.get('specialization', doctor.specialization),
            'Specialization',
        )
        if error_message:
            return error_response(error_message)

        experience_years, error_message = validate_non_negative_int(
            data.get('experience_years', doctor.experience_years or 0),
            'Experience',
        )
        if error_message:
            return error_response(error_message)

        if new_email != doctor.email and User.query.filter_by(email=new_email).first():
            return error_response('Email already exists', 409)

        doctor.name = new_name
        doctor.email = new_email
        doctor.specialization = specialization or doctor.specialization
        doctor.experience_years = experience_years
        if profile_image_data is not None:
            doctor.profile_image_data = profile_image_data or None

        dept_name = data.get('department') or data.get('dept')
        if dept_name:
            dept_name, error_message = validate_optional_text(dept_name, 'Department')
            if error_message:
                return error_response(error_message)
            dept = get_or_create_department(dept_name)
            doctor.f_did = dept.did

        if new_password:
            doctor.password = new_password

        db.session.commit()
        session['email'] = doctor.email
        invalidate_shared_caches()

        return success_response('Doctor profile updated successfully', {'doctor': serialize_user(doctor)})

    @app.route('/api/doctor/appointments', methods=['GET'])
    def api_doctor_appointments():
        doctor, error = require_role_api(3)
        if error:
            return error

        status = request.args.get('status', '').strip()
        query = Appointment.query.filter_by(f_doctor_uid=doctor.uid)
        if status:
            query = query.filter_by(status=status)

        appointments = query.order_by(Appointment.appointment_date.desc()).all()
        return success_response(
            'Doctor appointments fetched successfully',
            {'appointments': [serialize_appointment(appt) for appt in appointments]}
        )

    @app.route('/api/doctor/appointments/<int:aid>/complete', methods=['PUT'])
    def api_doctor_complete_appointment(aid):
        doctor, error = require_role_api(3)
        if error:
            return error

        appointment = Appointment.query.get_or_404(aid)
        if appointment.f_doctor_uid != doctor.uid:
            return error_response('Unauthorized', 403)

        data = parse_request_data()
        diagnosis, error_message = validate_optional_text(data.get('diagnosis', ''), 'Diagnosis', min_length=2, max_length=500)
        if error_message:
            return error_response(error_message)
        prescription, error_message = validate_optional_text(data.get('prescription', ''), 'Prescription', min_length=2, max_length=500)
        if error_message:
            return error_response(error_message)
        doctor_notes, error_message = validate_optional_text(data.get('doctor_notes', ''), 'Doctor notes', min_length=2, max_length=500)
        if error_message:
            return error_response(error_message)

        appointment.diagnosis = diagnosis
        appointment.prescription = prescription
        appointment.doctor_notes = doctor_notes
        appointment.status = 'completed'
        appointment.completed_at = datetime.now()
        db.session.commit()
        invalidate_cache_prefixes('admin_stats', 'admin_appointments', 'admin_analytics')

        return success_response('Appointment marked as completed', {'appointment': serialize_appointment(appointment)})

    @app.route('/api/doctor/appointments/<int:aid>', methods=['PUT'])
    def api_doctor_update_appointment(aid):
        doctor, error = require_role_api(3)
        if error:
            return error

        appointment = Appointment.query.get_or_404(aid)
        if appointment.f_doctor_uid != doctor.uid:
            return error_response('Unauthorized', 403)

        data = parse_request_data()

        if 'diagnosis' in data:
            diagnosis, error_message = validate_optional_text(data.get('diagnosis', ''), 'Diagnosis', min_length=2, max_length=500)
            if error_message:
                return error_response(error_message)
            appointment.diagnosis = diagnosis
        if 'prescription' in data:
            prescription, error_message = validate_optional_text(data.get('prescription', ''), 'Prescription', min_length=2, max_length=500)
            if error_message:
                return error_response(error_message)
            appointment.prescription = prescription
        if 'doctor_notes' in data:
            doctor_notes, error_message = validate_optional_text(data.get('doctor_notes', ''), 'Doctor notes', min_length=2, max_length=500)
            if error_message:
                return error_response(error_message)
            appointment.doctor_notes = doctor_notes

        status = data.get('status')
        if status:
            if status not in ('scheduled', 'completed', 'cancelled'):
                return error_response('Invalid appointment status')
            appointment.status = status
            if status == 'completed':
                appointment.completed_at = appointment.completed_at or datetime.now()
            else:
                appointment.completed_at = None

        db.session.commit()
        invalidate_cache_prefixes('admin_stats', 'admin_appointments', 'admin_analytics')

        return success_response('Appointment updated successfully', {'appointment': serialize_appointment(appointment)})

    @app.route('/api/doctor/appointments/<int:aid>/cancel', methods=['POST'])
    def api_doctor_cancel_appointment(aid):
        doctor, error = require_role_api(3)
        if error:
            return error

        appointment = Appointment.query.get_or_404(aid)
        if appointment.f_doctor_uid != doctor.uid:
            return error_response('Unauthorized', 403)

        appointment.status = 'cancelled'
        appointment.completed_at = None
        db.session.commit()
        invalidate_cache_prefixes('admin_stats', 'admin_appointments', 'admin_analytics', 'doctors')

        return success_response('Appointment cancelled successfully', {'appointment': serialize_appointment(appointment)})

    @app.route('/api/doctor/patients/<int:patient_uid>/history', methods=['GET'])
    def api_doctor_patient_history(patient_uid):
        doctor, error = require_role_api(3)
        if error:
            return error

        patient = User.query.filter_by(uid=patient_uid, f_rid=2, blacklisted=False).first()
        if not patient:
            return error_response('Patient not found', 404)

        history = Appointment.query.filter(
            Appointment.f_patient_uid == patient_uid,
            Appointment.f_doctor_uid == doctor.uid
        ).order_by(Appointment.appointment_date.desc()).all()

        return success_response(
            'Patient history fetched successfully',
            {
                'patient': serialize_user(patient),
                'history': [serialize_appointment(appt) for appt in history]
            }
        )

    @app.route('/api/doctor/availability', methods=['GET', 'PUT'])
    def api_doctor_availability_manage():
        doctor, error = require_role_api(3)
        if error:
            return error

        if request.method == 'GET':
            availabilities = DoctorAvailability.query.filter_by(doctor_uid=doctor.uid)\
                .order_by(DoctorAvailability.slot_str).all()
            return success_response(
                'Doctor availability fetched successfully',
                {'availability': [serialize_availability(item) for item in availabilities]}
            )

        data = parse_request_data()
        slot_str, error_message = validate_slot_string(data.get('slot_str', ''))
        if error_message:
            return error_response(error_message)

        available = data.get('available', True)
        if isinstance(available, str):
            available = available.lower() in ('true', '1', 'yes', 'on')

        availability = DoctorAvailability.query.filter_by(
            doctor_uid=doctor.uid,
            slot_str=slot_str
        ).first()

        if availability:
            availability.available = available
        else:
            availability = DoctorAvailability(
                doctor_uid=doctor.uid,
                slot_str=slot_str,
                available=available
            )
            db.session.add(availability)

        db.session.commit()
        invalidate_cache_prefixes('doctors', 'admin_analytics')
        return success_response('Doctor availability updated successfully', {'availability': serialize_availability(availability)})

    @app.route('/api/doctor/jobs/monthly-report/send-now', methods=['POST'])
    def api_doctor_send_monthly_report_now():
        doctor, error = require_role_api(3)
        if error:
            return error

        from tasks import resolve_report_window, send_monthly_report_for_doctor

        start_date, end_date = resolve_report_window()
        delivery = send_monthly_report_for_doctor(doctor, start_date, end_date)
        return success_response(
            'Monthly report sent successfully',
            {'report': delivery}
        )

    @app.route('/api/admin/stats', methods=['GET'])
    def api_admin_stats():
        _, error = require_role_api(1)
        if error:
            return error

        data = get_or_set_cache(
            'admin_stats',
            'summary',
            lambda: {
                'total_doctors': User.query.filter_by(f_rid=3, blacklisted=False).count(),
                'total_patients': User.query.filter_by(f_rid=2, blacklisted=False).count(),
                'total_appointments': Appointment.query.count(),
                'scheduled_appointments': Appointment.query.filter_by(status='scheduled').count(),
                'completed_appointments': Appointment.query.filter_by(status='completed').count(),
                'cancelled_appointments': Appointment.query.filter_by(status='cancelled').count()
            },
            timeout=app.config.get('CACHE_ADMIN_TIMEOUT')
        )
        return success_response('Admin stats fetched successfully', data)

    @app.route('/api/admin/analytics', methods=['GET'])
    def api_admin_analytics():
        _, error = require_role_api(1)
        if error:
            return error

        def build_admin_analytics_payload():
            today = datetime.now().date()
            trend_labels = []
            trend_values = []

            for offset in range(7):
                current_date = today + timedelta(days=offset)
                day_start = datetime.combine(current_date, datetime.min.time())
                day_end = datetime.combine(current_date, datetime.max.time())

                if offset == 0:
                    label = 'Today'
                elif offset == 1:
                    label = 'Tomorrow'
                else:
                    label = current_date.strftime('%b %d')

                trend_labels.append(label)
                trend_values.append(
                    Appointment.query.filter(
                        Appointment.appointment_date >= day_start,
                        Appointment.appointment_date <= day_end,
                    ).count()
                )

            specialization_rows = db.session.query(
                User.specialization,
                func.count(Appointment.aid)
            ).join(
                Appointment,
                Appointment.f_doctor_uid == User.uid
            ).filter(
                User.f_rid == 3,
                User.blacklisted == False
            ).group_by(
                User.specialization
            ).order_by(
                func.count(Appointment.aid).desc()
            ).all()

            return {
                'appointment_trend': {
                    'labels': trend_labels,
                    'values': trend_values,
                },
                'specialization_demand': {
                    'labels': [specialization or 'General' for specialization, _ in specialization_rows] or ['No Data'],
                    'values': [total for _, total in specialization_rows] or [1],
                },
            }

        data = get_or_set_cache(
            'admin_analytics',
            'summary',
            build_admin_analytics_payload,
            timeout=app.config.get('CACHE_ADMIN_TIMEOUT')
        )
        return success_response('Admin analytics fetched successfully', data)

    @app.route('/api/admin/doctors', methods=['GET', 'POST'])
    def api_admin_doctors():
        _, error = require_role_api(1)
        if error:
            return error

        if request.method == 'GET':
            search_query = request.args.get('search', '').strip()
            specialization = request.args.get('specialization', '').strip()
            department_name = request.args.get('department', '').strip()

            def build_admin_doctors_payload():
                doctors, filter_error = filter_doctors_for_api(search_query, specialization, department_name, '')
                if filter_error:
                    raise ValueError(filter_error)
                return {'doctors': [serialize_user(doctor) for doctor in doctors]}

            cache_suffix = f'search={search_query}|specialization={specialization}|department={department_name}'

            try:
                data = get_or_set_cache(
                    'admin_doctors',
                    cache_suffix,
                    build_admin_doctors_payload,
                    timeout=app.config.get('CACHE_ADMIN_TIMEOUT')
                )
            except ValueError as exc:
                return error_response(str(exc))

            return success_response(
                'Doctors fetched successfully',
                data
            )

        data = parse_request_data()
        name, error_message = validate_name_value(data.get('name'), 'Name')
        if error_message:
            return error_response(error_message)
        email, error_message = validate_email_value(data.get('email'))
        if error_message:
            return error_response(error_message)
        password, error_message = validate_password_value(data.get('password', ''), required=True)
        if error_message:
            return error_response(error_message)
        specialization, error_message = validate_optional_text(data.get('specialization', ''), 'Specialization')
        if error_message or not specialization:
            return error_response(error_message or 'Specialization is required')
        dept_name, error_message = validate_optional_text(data.get('department', ''), 'Department')
        if error_message or not dept_name:
            return error_response(error_message or 'Department is required')
        experience, error_message = validate_non_negative_int(data.get('experience_years', 0), 'Experience')
        if error_message:
            return error_response(error_message)

        if User.query.filter_by(email=email).first():
            return error_response('User with this email already exists', 409)

        dept = get_or_create_department(dept_name)
        doctor = User(
            name=name,
            email=email,
            password=password,
            specialization=specialization,
            experience_years=experience,
            f_rid=3,
            f_did=dept.did
        )
        db.session.add(doctor)
        db.session.commit()
        invalidate_shared_caches()

        return success_response('Doctor created successfully', {'doctor': serialize_user(doctor)}, 201)

    @app.route('/api/admin/doctors/<int:uid>', methods=['GET', 'PUT', 'DELETE'])
    def api_admin_doctor_detail(uid):
        _, error = require_role_api(1)
        if error:
            return error

        doctor = User.query.filter_by(uid=uid, f_rid=3).first()
        if not doctor:
            return error_response('Doctor not found', 404)

        if request.method == 'GET':
            return success_response('Doctor fetched successfully', {'doctor': serialize_user(doctor)})

        if request.method == 'DELETE':
            doctor.blacklisted = True
            db.session.commit()
            invalidate_shared_caches()
            return success_response('Doctor profile deleted successfully', {'doctor': serialize_user(doctor)})

        data = parse_request_data()
        new_email, error_message = validate_email_value(data.get('email', doctor.email))
        if error_message:
            return error_response(error_message)
        if new_email != doctor.email and User.query.filter_by(email=new_email).first():
            return error_response('Email already exists', 409)

        new_name, error_message = validate_name_value(data.get('name', doctor.name), 'Name')
        if error_message:
            return error_response(error_message)
        doctor.name = new_name
        doctor.email = new_email
        specialization, error_message = validate_optional_text(
            data.get('specialization', doctor.specialization),
            'Specialization',
        )
        if error_message:
            return error_response(error_message)
        experience_years, error_message = validate_non_negative_int(
            data.get('experience_years', doctor.experience_years or 0),
            'Experience',
        )
        if error_message:
            return error_response(error_message)
        doctor.specialization = specialization or doctor.specialization
        doctor.experience_years = experience_years

        password, error_message = validate_password_value(data.get('password'), required=False)
        if error_message:
            return error_response(error_message)
        if password:
            doctor.password = password

        dept_name = data.get('department')
        if dept_name:
            dept_name, error_message = validate_optional_text(dept_name, 'Department')
            if error_message:
                return error_response(error_message)
            dept = get_or_create_department(dept_name)
            doctor.f_did = dept.did

        availability_updates = data.get('availability_slots', [])
        for item in availability_updates:
            slot_str = item.get('slot_str', '').strip()
            if not slot_str:
                continue
            available = item.get('available', True)
            availability = DoctorAvailability.query.filter_by(doctor_uid=doctor.uid, slot_str=slot_str).first()
            if availability:
                availability.available = available
            else:
                db.session.add(DoctorAvailability(
                    doctor_uid=doctor.uid,
                    slot_str=slot_str,
                    available=available
                ))

        db.session.commit()
        invalidate_shared_caches()
        return success_response('Doctor updated successfully', {'doctor': serialize_user(doctor)})

    @app.route('/api/admin/users/<int:uid>', methods=['GET', 'PUT'])
    def api_admin_user_detail(uid):
        _, error = require_role_api(1)
        if error:
            return error

        user = User.query.filter_by(uid=uid).first()
        if not user or user.f_rid not in (2, 3):
            return error_response('User not found', 404)

        if request.method == 'GET':
            if user.f_rid == 3:
                appointments = Appointment.query.filter_by(f_doctor_uid=uid)\
                    .order_by(Appointment.appointment_date.desc()).all()
            else:
                appointments = Appointment.query.filter_by(f_patient_uid=uid)\
                    .order_by(Appointment.appointment_date.desc()).all()

            return success_response(
                'User fetched successfully',
                {
                    'user': serialize_user(user),
                    'appointments': [serialize_appointment(appt) for appt in appointments]
                }
            )

        data = parse_request_data()
        new_email, error_message = validate_email_value(data.get('email', user.email))
        if error_message:
            return error_response(error_message)
        if new_email != user.email and User.query.filter_by(email=new_email).first():
            return error_response('Email already exists', 409)

        new_name, error_message = validate_name_value(data.get('name', user.name), 'Name')
        if error_message:
            return error_response(error_message)
        user.name = new_name
        user.email = new_email

        password, error_message = validate_password_value(data.get('password'), required=False)
        if error_message:
            return error_response(error_message)
        if password:
            user.password = password

        if user.f_rid == 3:
            specialization, error_message = validate_optional_text(
                data.get('specialization', user.specialization),
                'Specialization',
            )
            if error_message:
                return error_response(error_message)
            experience_years, error_message = validate_non_negative_int(
                data.get('experience_years', user.experience_years or 0),
                'Experience',
            )
            if error_message:
                return error_response(error_message)
            user.specialization = specialization or user.specialization
            user.experience_years = experience_years

            dept_name = data.get('department') or data.get('dept')
            if dept_name:
                dept_name, error_message = validate_optional_text(dept_name, 'Department')
                if error_message:
                    return error_response(error_message)
                dept = get_or_create_department(dept_name)
                user.f_did = dept.did

        db.session.commit()
        invalidate_shared_caches()

        return success_response('User updated successfully', {'user': serialize_user(user)})

    @app.route('/api/admin/users/<int:uid>/blacklist', methods=['PUT'])
    def api_admin_user_blacklist(uid):
        _, error = require_role_api(1)
        if error:
            return error

        user = User.query.filter_by(uid=uid).first()
        if not user or user.f_rid not in (2, 3):
            return error_response('User not found', 404)

        data = parse_request_data()
        blacklisted = data.get('blacklisted', True)
        if isinstance(blacklisted, str):
            blacklisted = blacklisted.lower() in ('true', '1', 'yes', 'on')

        user.blacklisted = blacklisted
        db.session.commit()
        invalidate_shared_caches()

        return success_response('User blacklist status updated successfully', {'user': serialize_user(user)})

    @app.route('/api/admin/patients', methods=['GET'])
    def api_admin_patients():
        _, error = require_role_api(1)
        if error:
            return error

        search_query = request.args.get('search', '').strip()
        data = get_or_set_cache(
            'admin_patients',
            f'search={search_query}',
            lambda: {'patients': [serialize_user(patient) for patient in get_filtered_patients(search_query)]},
            timeout=app.config.get('CACHE_ADMIN_TIMEOUT')
        )
        return success_response(
            'Patients fetched successfully',
            data
        )

    @app.route('/api/admin/appointments', methods=['GET'])
    def api_admin_appointments():
        _, error = require_role_api(1)
        if error:
            return error

        search_query = request.args.get('search', '').strip()
        appointment_tab = request.args.get('appt_tab', '').strip()

        def build_admin_appointments_payload():
            if appointment_tab in ('upcoming', 'past'):
                appointments = get_filtered_appointments(search_query, appointment_tab)
            else:
                query = Appointment.query.order_by(Appointment.appointment_date.desc())
                if search_query:
                    patient_alias = aliased(User)
                    doctor_alias = aliased(User)
                    query = db.session.query(Appointment)\
                        .join(patient_alias, Appointment.f_patient_uid == patient_alias.uid)\
                        .join(doctor_alias, Appointment.f_doctor_uid == doctor_alias.uid)\
                        .filter(or_(
                            patient_alias.name.ilike(f'%{search_query}%'),
                            doctor_alias.name.ilike(f'%{search_query}%'),
                            doctor_alias.specialization.ilike(f'%{search_query}%')
                        ))\
                        .order_by(Appointment.appointment_date.desc())
                    appointments = query.all()
                else:
                    appointments = query.all()

            return {'appointments': [serialize_appointment(appt) for appt in appointments]}

        data = get_or_set_cache(
            'admin_appointments',
            f'search={search_query}|appt_tab={appointment_tab}',
            build_admin_appointments_payload,
            timeout=app.config.get('CACHE_ADMIN_TIMEOUT')
        )

        return success_response(
            'Appointments fetched successfully',
            data
        )

    @app.route('/api/admin/appointments/<int:aid>', methods=['GET', 'PUT'])
    def api_admin_appointment_detail(aid):
        _, error = require_role_api(1)
        if error:
            return error

        appointment = Appointment.query.get_or_404(aid)

        if request.method == 'GET':
            return success_response('Appointment fetched successfully', {'appointment': serialize_appointment(appointment)})

        data = parse_request_data()
        status = data.get('status')
        if status:
            if status not in ('scheduled', 'completed', 'cancelled'):
                return error_response('Invalid appointment status')
            appointment.status = status
        if 'diagnosis' in data:
            diagnosis, error_message = validate_optional_text(data.get('diagnosis', ''), 'Diagnosis', min_length=2, max_length=500)
            if error_message:
                return error_response(error_message)
            appointment.diagnosis = diagnosis
        if 'prescription' in data:
            prescription, error_message = validate_optional_text(data.get('prescription', ''), 'Prescription', min_length=2, max_length=500)
            if error_message:
                return error_response(error_message)
            appointment.prescription = prescription
        if 'doctor_notes' in data:
            doctor_notes, error_message = validate_optional_text(data.get('doctor_notes', ''), 'Doctor notes', min_length=2, max_length=500)
            if error_message:
                return error_response(error_message)
            appointment.doctor_notes = doctor_notes

        db.session.commit()
        invalidate_cache_prefixes('admin_stats', 'admin_appointments', 'admin_analytics')
        return success_response('Appointment updated successfully', {'appointment': serialize_appointment(appointment)})

    @app.route('/api/admin/jobs/daily-reminders', methods=['POST'])
    def api_admin_trigger_daily_reminders():
        _, error = require_role_api(1)
        if error:
            return error

        from tasks import daily_patient_reminders

        task = daily_patient_reminders.delay()
        return success_response(
            'Daily reminder job triggered successfully',
            {'task_id': task.id, 'task_name': 'daily_patient_reminders'},
            202
        )

    @app.route('/api/admin/jobs/monthly-reports', methods=['POST'])
    def api_admin_trigger_monthly_reports():
        _, error = require_role_api(1)
        if error:
            return error

        data = parse_request_data()
        report_month = data.get('month')
        report_year = data.get('year')

        if report_month or report_year:
            try:
                report_month = int(report_month)
                report_year = int(report_year)
            except (TypeError, ValueError):
                return error_response('Month and year must be valid numbers')

            if report_month < 1 or report_month > 12:
                return error_response('Month must be between 1 and 12')
            if report_year < 2000 or report_year > 2100:
                return error_response('Year must be between 2000 and 2100')

        from tasks import monthly_doctor_activity_reports

        task = monthly_doctor_activity_reports.delay(report_month=report_month, report_year=report_year)
        return success_response(
            'Monthly report job triggered successfully',
            {
                'task_id': task.id,
                'task_name': 'monthly_doctor_activity_reports',
                'month': report_month,
                'year': report_year
            },
            202
        )

    @app.route('/api/admin/jobs/<task_id>', methods=['GET'])
    def api_admin_job_status(task_id):
        _, error = require_role_api(1)
        if error:
            return error

        from celery.result import AsyncResult
        from celery_app import celery

        task_result = AsyncResult(task_id, app=celery)
        response_data = {
            'task_id': task_id,
            'status': task_result.status,
            'ready': task_result.ready(),
        }

        if task_result.ready():
            if task_result.successful():
                response_data['result'] = task_result.result
            else:
                response_data['error'] = str(task_result.result)

        return success_response('Job status fetched successfully', response_data)

    @app.route('/assets/<path:filename>', methods=['GET'])
    def frontend_assets(filename):
        assets_dir = FRONTEND_DIST_DIR / 'assets'
        if assets_dir.exists():
            return send_from_directory(assets_dir, filename)
        return error_response('Frontend assets not built yet', 404)

    @app.route('/manifest.webmanifest', methods=['GET'])
    @app.route('/sw.js', methods=['GET'])
    @app.route('/icon.svg', methods=['GET'])
    def frontend_public_files():
        dist_file = FRONTEND_DIST_DIR / request.path.lstrip('/')
        if dist_file.exists():
            response = send_from_directory(FRONTEND_DIST_DIR, request.path.lstrip('/'))
            if request.path in ('/manifest.webmanifest', '/sw.js'):
                response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
            return response
        return error_response('Frontend file not built yet', 404)

    @app.route('/admin', methods=['GET'])
    @app.route('/admin/create-doctor', methods=['GET'])
    @app.route('/patient', methods=['GET'])
    @app.route('/patient/payments', methods=['GET'])
    @app.route('/doctor', methods=['GET'])
    def frontend_app_routes():
        frontend_response = serve_frontend_index()
        if frontend_response:
            return frontend_response
        return redirect('/')

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        if path.startswith('api/'):
            return jsonify({'success': False, 'message': 'API endpoint not found'}), 404
        return serve_frontend_index() or error_response('Frontend not built', 404)
