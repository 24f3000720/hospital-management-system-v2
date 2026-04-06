import json

from flask import current_app

from extensions import redis_client


def build_cache_key(prefix, suffix='default'):
    namespace = current_app.config.get('CACHE_KEY_PREFIX', 'hospital_management')
    return f'{namespace}:{prefix}:{suffix or "default"}'


def get_cached_json(key):
    if redis_client is None:
        return None

    try:
        cached_value = redis_client.get(key)
        if cached_value is None:
            return None
        return json.loads(cached_value)
    except Exception:
        return None


def set_cached_json(key, payload, timeout=None):
    if redis_client is None:
        return

    ttl = timeout or current_app.config.get('CACHE_DEFAULT_TIMEOUT', 300)

    try:
        redis_client.setex(key, ttl, json.dumps(payload))
    except Exception:
        return


def invalidate_cache_prefixes(*prefixes):
    if redis_client is None:
        return

    namespace = current_app.config.get('CACHE_KEY_PREFIX', 'hospital_management')

    try:
        for prefix in prefixes:
            pattern = f'{namespace}:{prefix}:*'
            keys = list(redis_client.scan_iter(match=pattern))
            if keys:
                redis_client.delete(*keys)
    except Exception:
        return
