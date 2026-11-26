"""Login lockout: too many wrong passwords lock the account for a while.

Uses Django's cache. The default local-memory cache works for development;
production with several worker processes needs a shared cache (database or
Redis) so the counters are shared. See docs/DECISIONS.md.
"""

from django.conf import settings
from django.core.cache import cache


def _key(username, ip):
    return f"login-fail:{(username or '').strip().lower()}:{ip or 'unknown'}"


def is_locked(username, ip):
    return cache.get(_key(username, ip), 0) >= settings.LOGIN_MAX_ATTEMPTS


def register_failure(username, ip):
    key = _key(username, ip)
    cache.add(key, 0, settings.LOGIN_LOCKOUT_SECONDS)
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, settings.LOGIN_LOCKOUT_SECONDS)
        return 1


def clear_failures(username, ip):
    cache.delete(_key(username, ip))
