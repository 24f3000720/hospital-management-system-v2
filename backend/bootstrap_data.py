from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from extensions import db
from models import Department, Role, User


def create_roles():
    roles_data = [
        ("Admin", "Administrator or superuser"),
        ("Patient", "Patient user"),
        ("Doctor", "Doctor user")
    ]

    for role_name, description in roles_data:
        if not Role.query.filter_by(role_name=role_name).first():
            role = Role(role_name=role_name, description=description)
            db.session.add(role)

    db.session.commit()


def create_departments():
    dept_names = ['Cardiology Department', 'Surgery Department', 'ENT Department']

    for dept_name in dept_names:
        if not Department.query.filter_by(name=dept_name).first():
            dept = Department(name=dept_name)
            db.session.add(dept)

    db.session.commit()


def create_sample_doctors():
    doctors_data = [
        ('Cardiology Department', 'Dr. Cardio Specialist', 'doc_cardio@gmail.com', 'Cardiology', 10),
        ('Surgery Department', 'Dr. Surgery Expert', 'doc_surgery@gmail.com', 'Surgery', 15),
        ('ENT Department', 'Dr. ENT Consultant', 'doc_ent@gmail.com', 'ENT', 8)
    ]

    for dept_name, name, email, specialization, experience in doctors_data:
        dept = Department.query.filter_by(name=dept_name).first()
        if dept and not User.query.filter_by(email=email).first():
            doctor = User(
                name=name,
                email=email,
                password='pass123',
                specialization=specialization,
                experience_years=experience,
                f_rid=3,
                f_did=dept.did
            )
            db.session.add(doctor)

    db.session.commit()


def auto_admin_creation():
    admin_email = "admin@gmail.com"

    if not User.query.filter_by(email=admin_email, f_rid=1).first():
        admin = User(
            name="Admin User",
            email=admin_email,
            password="admin@123",
            f_rid=1
        )
        db.session.add(admin)
        db.session.commit()


def ensure_schema_updates():
    inspector = inspect(db.engine)

    table_names = set(inspector.get_table_names())

    if 'user' not in table_names:
        return

    user_columns = {column['name'] for column in inspector.get_columns('user')}
    appointment_columns = {column['name'] for column in inspector.get_columns('appointment')} if 'appointment' in table_names else set()

    with db.engine.begin() as connection:
        if 'profile_image_data' not in user_columns:
            try:
                connection.execute(text('ALTER TABLE user ADD COLUMN profile_image_data TEXT'))
            except OperationalError as exc:
                if 'duplicate column name' not in str(exc).lower():
                    raise
        if 'appointment' in table_names and 'completed_at' not in appointment_columns:
            try:
                connection.execute(text('ALTER TABLE appointment ADD COLUMN completed_at DATETIME'))
            except OperationalError as exc:
                if 'duplicate column name' not in str(exc).lower():
                    raise
