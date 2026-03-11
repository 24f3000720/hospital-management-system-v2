from extensions import db


class Role(db.Model):
    rid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role_name = db.Column(db.String, unique=True, nullable=False)
    description = db.Column(db.String, nullable=True)


class Department(db.Model):
    did = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, unique=True, nullable=False)


class User(db.Model):
    uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, unique=True, nullable=False)
    password = db.Column(db.String, nullable=False)
    profile_image_data = db.Column(db.Text, nullable=True)
    specialization = db.Column(db.String, nullable=True)
    experience_years = db.Column(db.Integer, default=0, nullable=True)
    blacklisted = db.Column(db.Boolean, default=False)
    f_rid = db.Column(db.Integer, db.ForeignKey(Role.rid), nullable=False)
    f_did = db.Column(db.Integer, db.ForeignKey(Department.did), nullable=True)
    roles = db.relationship(Role, backref='users', lazy=True)
    department = db.relationship('Department', backref='doctors')


class Appointment(db.Model):
    aid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    f_patient_uid = db.Column(db.Integer, db.ForeignKey('user.uid'), nullable=False)
    f_doctor_uid = db.Column(db.Integer, db.ForeignKey('user.uid'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String, default='scheduled')
    completed_at = db.Column(db.DateTime, nullable=True)
    diagnosis = db.Column(db.Text, nullable=True)
    prescription = db.Column(db.Text, nullable=True)
    doctor_notes = db.Column(db.Text, nullable=True)

    patient = db.relationship('User', foreign_keys=[f_patient_uid], backref='patient_appointments')
    doctor = db.relationship('User', foreign_keys=[f_doctor_uid])


class DoctorAvailability(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    doctor_uid = db.Column(db.Integer, db.ForeignKey('user.uid'), nullable=False)
    slot_str = db.Column(db.String(16), nullable=False)
    available = db.Column(db.Boolean, default=True)


class ExportJob(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_uid = db.Column(db.Integer, db.ForeignKey('user.uid'), nullable=False)
    export_type = db.Column(db.String(50), nullable=False, default='treatment_history_csv')
    status = db.Column(db.String(20), nullable=False, default='queued')
    celery_task_id = db.Column(db.String(100), nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    message = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    completed_at = db.Column(db.DateTime, nullable=True)

    patient = db.relationship('User', backref='export_jobs')


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_uid = db.Column(db.Integer, db.ForeignKey('user.uid'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.aid'), nullable=False, unique=True)
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(10), nullable=False, default='INR')
    card_holder = db.Column(db.String(120), nullable=False)
    card_last4 = db.Column(db.String(4), nullable=False)
    payment_status = db.Column(db.String(20), nullable=False, default='paid')
    payment_reference = db.Column(db.String(40), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    paid_at = db.Column(db.DateTime, nullable=True)

    patient = db.relationship('User', backref='payments')
    appointment = db.relationship('Appointment', backref=db.backref('payment', uselist=False))
