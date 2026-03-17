from flask import Flask

from bootstrap_data import auto_admin_creation, create_departments, create_roles, create_sample_doctors, ensure_schema_updates
from extensions import db, init_redis, migrate
from routes import register_routes


def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('config.py')
    db.init_app(app)
    migrate.init_app(app, db)
    init_redis(app)
    register_routes(app)

    with app.app_context():
        import models

        db.create_all()
        ensure_schema_updates()

    return app

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        create_roles()
        create_departments()
        create_sample_doctors()
        auto_admin_creation()
    app.run(debug=True)
