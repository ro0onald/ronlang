"""Password hashing and server-side sessions built on Python standard primitives."""
import hashlib
import hmac
import secrets
import time
from http.cookies import SimpleCookie


def password_hash(password):
    if not isinstance(password, str) or not 8 <= len(password) <= 1024:
        raise ValueError('password must contain 8 to 1024 characters')
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return 'scrypt$' + salt.hex() + '$' + digest.hex()


def password_verify(password, encoded):
    try:
        name, salt, expected = encoded.split('$')
        if name != 'scrypt' or len(salt) != 32 or len(expected) != 64 or len(password) > 1024:
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=32)
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError, AttributeError):
        return False


class Sessions:
    """Single-process session store, expiring after a fixed lifetime."""
    def __init__(self, secure=True, ttl=3600):
        if type(secure) is not bool or not 60 <= ttl <= 86400:
            raise ValueError('invalid session configuration')
        self.secure, self.ttl, self.records = secure, ttl, {}

    def load(self, cookie):
        now = time.time()
        self.records = {k: v for k, v in self.records.items() if v['expires'] > now}
        parsed = SimpleCookie()
        try:
            parsed.load(cookie)
            token = parsed['ron_session'].value if 'ron_session' in parsed else ''
        except Exception:
            token = ''
        if token not in self.records:
            if len(self.records) >= 10000:
                raise ValueError('session capacity reached')
            token = self.create(None)
        return token, self.records[token]

    def create(self, user):
        token = secrets.token_urlsafe(32)
        self.records[token] = {'user': user, 'csrf': secrets.token_urlsafe(32),
                               'expires': time.time() + self.ttl}
        return token

    def cookie(self, token, clear=False):
        value = f'ron_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={0 if clear else self.ttl}'
        return value + ('; Secure' if self.secure else '')


def session_user(request):
    return request.get('_session', {}).get('user')


def csrf(request):
    if '_session' not in request:
        raise ValueError('enable sessions on this app first')
    return request['_session']['csrf']


def login(request, user):
    from ronlib import Response
    store = request['_app'].sessions
    store.records.pop(request['_session_token'], None)
    token = store.create(user)
    request['_session_token'], request['_session'] = token, store.records[token]
    return Response({'user': user, 'csrf': request['_session']['csrf']})


def logout(request):
    from ronlib import Response
    store = request['_app'].sessions
    store.records.pop(request['_session_token'], None)
    request['_clear_session'] = True
    return Response({'logged_out': True})
