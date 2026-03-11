from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from redis import Redis


db = SQLAlchemy()
migrate = Migrate()
redis_client = None


def init_redis(app):
    global redis_client

    try:
        client = Redis.from_url(app.config['REDIS_URL'], decode_responses=True)
        client.ping()
        redis_client = client
        app.logger.info('Redis connected successfully')
    except Exception as exc:
        redis_client = None
        app.logger.warning(f'Redis unavailable, caching disabled: {exc}')

    return redis_client
