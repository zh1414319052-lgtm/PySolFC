"""Haoke Android v1 signed update notifications (GPL-3.0-or-later).

Protocol adapted from Anx Reader's maintained update_manifest.dart. Ed25519
uses the pinned runtime's OpenSSL EVP API, not a new crypto implementation.
Only public trust material is stored here; this module never installs an APK.
"""

import base64
import copy
import ctypes
import ctypes.util
import hashlib
import http.client
import json
import os
import re
import ssl
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

SOFTWARE_ID = '51c7e11a1f8d6559'
PUBLIC_KEYS = {
    'haoke-updates-000ef7a45a5a58d5':
        '+8cSV1C+t+6GipgPi3a2zjZ4T3W/Z+tZDKzzO4tQXOY=',
}
IDENTITIES = {
    'org.haoke.pysolfc': (
        'stable',
        '13ea44b975c48845883d171e8f642d3c00d59fd54b2f17ca50ef05e57bcf2a69'),
    'org.lufebe16.pysolfc.qa': (
        'qa',
        'a1519f2f24b603f1cd5ab4e76ec440c5275036a8dfcc439eb1ab868f35d0ddb2'),
}
MAX_ENVELOPE = 65536
MAX_PAYLOAD = 32768
SLUG = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z')
HEX = re.compile(r'[a-f0-9]{64}\Z')


class UpdateError(Exception):
    """Safe error code; response bodies and native exceptions are not exposed."""


def require(condition, code='INVALID_MANIFEST'):
    if not condition:
        raise UpdateError(code)


def _json(data):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result)
            result[key] = value
        return result

    def constant(value):
        raise UpdateError('INVALID_JSON')

    try:
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError, TypeError):
        raise UpdateError('INVALID_JSON') from None


def _keys(value, expected):
    require(type(value) is dict and set(value) == set(expected))


def _integer(value, minimum=0):
    require(type(value) is int and minimum <= value <= 9007199254740991)
    return value


def _text(value, limit):
    require(type(value) is str and 0 < len(value) <= limit
            and not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', value))
    return value


def _date(value):
    require(type(value) is str and re.fullmatch(
        r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z', value))
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
    except ValueError:
        raise UpdateError('INVALID_TIME') from None


def _base64(value, limit, length=None):
    require(type(value) is str and len(value) <= ((limit + 2) // 3) * 4)
    try:
        result = base64.b64decode(value, validate=True)
    except ValueError:
        raise UpdateError('INVALID_BASE64') from None
    require(len(result) <= limit and (length is None or len(result) == length)
            and base64.b64encode(result).decode('ascii') == value)
    return result


def _openssl():
    if sys.platform == 'win32':
        candidates = [str(Path(sys.base_prefix) / 'DLLs' / 'libcrypto-3.dll')]
    else:
        candidates = ['libcrypto.so', ctypes.util.find_library('crypto')]
    for name in candidates:
        if not name:
            continue
        try:
            lib = ctypes.CDLL(name)
            signatures = {
                'OBJ_txt2nid': (ctypes.c_int, [ctypes.c_char_p]),
                'EVP_PKEY_new_raw_public_key': (
                    ctypes.c_void_p, [ctypes.c_int, ctypes.c_void_p,
                                     ctypes.c_char_p, ctypes.c_size_t]),
                'EVP_PKEY_free': (None, [ctypes.c_void_p]),
                'EVP_MD_CTX_new': (ctypes.c_void_p, []),
                'EVP_MD_CTX_free': (None, [ctypes.c_void_p]),
                'EVP_DigestVerifyInit': (ctypes.c_int, [ctypes.c_void_p] * 5),
                'EVP_DigestVerify': (
                    ctypes.c_int, [ctypes.c_void_p, ctypes.c_char_p,
                                   ctypes.c_size_t, ctypes.c_char_p,
                                   ctypes.c_size_t]),
            }
            for symbol, (restype, argtypes) in signatures.items():
                function = getattr(lib, symbol)
                function.restype, function.argtypes = restype, argtypes
            require(lib.OBJ_txt2nid(b'ED25519') > 0, 'CRYPTO_UNAVAILABLE')
            return lib
        except (OSError, AttributeError, UpdateError):
            continue
    raise UpdateError('CRYPTO_UNAVAILABLE')


def verify_ed25519(public, signature, payload):
    require(len(public) == 32 and len(signature) == 64, 'INVALID_SIGNATURE')
    lib = _openssl()
    key = lib.EVP_PKEY_new_raw_public_key(
        lib.OBJ_txt2nid(b'ED25519'), None, public, len(public))
    ctx = lib.EVP_MD_CTX_new()
    try:
        require(key and ctx, 'CRYPTO_UNAVAILABLE')
        # PureEdDSA requires NULL digest and the one-shot EVP call.
        require(lib.EVP_DigestVerifyInit(ctx, None, None, None, key) == 1,
                'CRYPTO_UNAVAILABLE')
        require(lib.EVP_DigestVerify(ctx, signature, len(signature), payload,
                                    len(payload)) == 1, 'INVALID_SIGNATURE')
    finally:
        if ctx:
            lib.EVP_MD_CTX_free(ctx)
        if key:
            lib.EVP_PKEY_free(key)


def android_identity():
    """Read actual installed identity; unknown signatures fail closed."""
    from jnius import autoclass
    activity = autoclass('org.kivy.android.PythonActivity').mActivity
    build = autoclass('android.os.Build')
    sdk = autoclass('android.os.Build$VERSION').SDK_INT
    package = str(activity.getPackageName())
    require(package in IDENTITIES, 'IDENTITY_MISMATCH')
    manager = activity.getPackageManager()
    info = manager.getPackageInfo(package, 0x08000000 if sdk >= 28 else 64)
    signatures = (info.signingInfo.getApkContentsSigners() if sdk >= 28
                  else info.signatures)
    require(len(signatures) == 1, 'IDENTITY_MISMATCH')
    raw = bytes((int(value) & 255) for value in signatures[0].toByteArray())
    certificate = hashlib.sha256(raw).hexdigest()
    channel, expected = IDENTITIES[package]
    require(certificate == expected, 'IDENTITY_MISMATCH')
    return dict(applicationId=package, channel=channel,
                certificateSha256=certificate, sdk=int(sdk),
                versionCode=int(info.getLongVersionCode() if sdk >= 28
                                else info.versionCode),
                versionName=str(info.versionName),
                abis=[str(value) for value in build.SUPPORTED_ABIS])


def verify_manifest(data, identity, checkpoint=None, now=None,
                    public_keys=None):
    require(type(data) is bytes and len(data) <= MAX_ENVELOPE)
    envelope = _json(data)
    _keys(envelope, ('algorithm', 'keyId', 'payload', 'signature'))
    keys = PUBLIC_KEYS if public_keys is None else public_keys
    require(envelope['algorithm'] == 'Ed25519'
            and type(envelope['keyId']) is str and envelope['keyId'] in keys,
            'UNTRUSTED_KEY')
    payload = _base64(envelope['payload'], MAX_PAYLOAD)
    verify_ed25519(_base64(keys[envelope['keyId']], 32, 32),
                   _base64(envelope['signature'], 64, 64), payload)
    p = _json(payload)
    _keys(p, ('schemaVersion', 'applicationId', 'channel', 'revision',
              'issuedAt', 'expiresAt', 'status', 'release'))
    require(type(p['schemaVersion']) is int and p['schemaVersion'] == 1)
    require(p['applicationId'] == identity['applicationId']
            and p['channel'] == identity['channel'], 'IDENTITY_MISMATCH')
    revision = _integer(p['revision'])
    issued, expires = _date(p['issuedAt']), _date(p['expiresAt'])
    now = time.time() if now is None else now
    require(issued <= now + 300 and now < expires and issued < expires
            and expires - issued <= 48 * 3600, 'INVALID_TIME')
    require(p['status'] in ('none', 'withdrawn', 'published'))
    release = p['release']
    available = False
    if p['status'] == 'published':
        require(revision > 0)
        _keys(release, ('releaseId', 'softwareId', 'versionCode', 'versionName',
                        'publishedAt', 'notes', 'pageUrl', 'apkSha256',
                        'certificateSha256', 'sizeBytes', 'minSdk', 'abis'))
        require(SLUG.fullmatch(_text(release['releaseId'], 80)))
        require(release['softwareId'] == SOFTWARE_ID, 'IDENTITY_MISMATCH')
        expected_url = ('https://haoke.org/software/%s/releases/%s' %
                        (SOFTWARE_ID, release['releaseId']))
        require(release['pageUrl'] == expected_url, 'INVALID_URL')
        _integer(release['versionCode'], 1)
        _text(release['versionName'], 80)
        require(_date(release['publishedAt']) <= issued + 300)
        _keys(release['notes'], ('zh', 'en'))
        for note in release['notes'].values():
            _text(note, 4000)
        require(type(release['apkSha256']) is str
                and HEX.fullmatch(release['apkSha256']))
        require(release['certificateSha256'] == identity['certificateSha256'],
                'IDENTITY_MISMATCH')
        _integer(release['sizeBytes'], 1)
        _integer(release['minSdk'], 21)
        abis = release['abis']
        require(type(abis) is list and 0 < len(abis) <= 4
                and all(type(abi) is str and abi in (
                    'arm64-v8a', 'armeabi-v7a', 'x86', 'x86_64') for abi in abis)
                and len(set(abis)) == len(abis))
        available = (release['versionCode'] > identity['versionCode']
                     and release['minSdk'] <= identity['sdk']
                     and bool(set(abis).intersection(identity['abis'])))
    else:
        require(release is None and (revision == 0 if p['status'] == 'none'
                                     else revision > 0))
    business = {key: value for key, value in p.items()
                if key not in ('issuedAt', 'expiresAt')}
    digest = hashlib.sha256(json.dumps(
        business, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode('utf-8')).hexdigest()
    checkpoint = checkpoint or {}
    previous = checkpoint.get('revision', 0)
    maximum = checkpoint.get('maxVersion', 0)
    _integer(previous)
    _integer(maximum)
    require(revision >= previous, 'ROLLBACK')
    if revision == previous and checkpoint.get('digest'):
        require(digest == checkpoint['digest'], 'CHANGED_REVISION')
    if release:
        require(release['versionCode'] >= maximum, 'ROLLBACK')
        maximum = max(maximum, release['versionCode'])
    return dict(available=available, release=release, expiresAt=expires,
                checkpoint=dict(revision=revision, digest=digest,
                                maxVersion=maximum))


class UpdateStore:
    def __init__(self, path):
        self.path = Path(path)
        try:
            self.state = _json(self.path.read_text(encoding='utf-8'))
            require(type(self.state) is dict
                    and self.state.get('stateVersion') == 1, 'STORAGE')
        except FileNotFoundError:
            self.state = {'stateVersion': 1}
        except (OSError, UpdateError):
            raise UpdateError('STORAGE') from None

    def save(self, state):
        temporary = self.path.with_suffix('.tmp')
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open('w', encoding='utf-8') as stream:
                json.dump(state, stream, ensure_ascii=False, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except OSError:
            raise UpdateError('STORAGE') from None
        self.state = copy.deepcopy(state)

    def update(self, **changes):
        self.save(dict(self.state, **changes))

    def should_prompt(self, manifest, manual=False, now=None):
        if not manifest['available']:
            return False
        if manual:
            return True
        decision = self.state.get('reminder', {})
        if decision.get('version') != manifest['release']['versionCode']:
            return True
        return (decision.get('choice') == 'later'
                and (time.time() if now is None else now) >=
                decision.get('until', float('inf')))

    def remember(self, version, choice, now=None):
        require(choice in ('ack', 'later', 'ignore'))
        self.update(reminder=dict(
            version=version, choice=choice,
            until=(time.time() if now is None else now) + 86400
            if choice == 'later' else 0))

    def present(self, manifest, show, guard, manual=False):
        require(guard() and manifest['expiresAt'] > time.time(), 'CANCELLED')
        if not self.should_prompt(manifest, manual):
            return False
        old = copy.deepcopy(self.state)
        self.remember(manifest['release']['versionCode'], 'ack')
        try:
            require(guard(), 'CANCELLED')
            show()
        except Exception:
            self.save(old)
            raise
        return True


class FeedRequest:
    """One bounded HTTPS request. Cancellation closes the active connection."""

    def __init__(self, identity):
        self.identity = identity
        self.cancelled = threading.Event()
        self.connection = None
        self.close_connection = None

    def cancel(self):
        self.cancelled.set()
        if self.close_connection:
            try:
                self.close_connection()
            except Exception:
                pass

    def _android(self):
        # Use Android's normal HTTPS trust store; no CA bundle/dependency change.
        from jnius import autoclass, cast
        url = ('https://www.haoke.org/api/client-updates/v1/%s/%s' %
               (self.identity['applicationId'], self.identity['channel']))
        connection = cast('javax.net.ssl.HttpsURLConnection',
                          autoclass('java.net.URL')(url).openConnection())
        self.connection = connection
        self.close_connection = connection.disconnect
        deadline = time.monotonic() + 12
        channel = None
        try:
            require(not self.cancelled.is_set(), 'CANCELLED')
            connection.setInstanceFollowRedirects(False)
            connection.setConnectTimeout(8000)
            connection.setReadTimeout(4000)
            connection.setRequestProperty('Accept', 'application/json')
            connection.setRequestProperty('Accept-Encoding', 'identity')
            connection.setRequestProperty('User-Agent', 'PySolFC-Haoke-Updates/1')
            require(connection.getResponseCode() == 200, 'NETWORK')
            encoding = connection.getHeaderField('Content-Encoding')
            require(encoding is None or str(encoding) in ('', 'identity'), 'NETWORK')
            channel = autoclass('java.nio.channels.Channels').newChannel(
                connection.getInputStream())
            buffer = autoclass('java.nio.ByteBuffer').allocate(4096)
            chunks, length = [], 0
            while True:
                remaining = deadline - time.monotonic()
                require(remaining > 0 and not self.cancelled.is_set(), 'CANCELLED')
                connection.setReadTimeout(max(1, int(min(4, remaining) * 1000)))
                count = channel.read(buffer)
                if count < 0:
                    break
                if count:
                    length += count
                    require(length <= MAX_ENVELOPE, 'TOO_LARGE')
                    values = buffer.array()
                    chunks.append(bytes((int(values[i]) & 255) for i in range(count)))
                buffer.clear()
            return b''.join(chunks)
        except UpdateError:
            raise
        except Exception:
            raise UpdateError('NETWORK') from None
        finally:
            if channel:
                try:
                    channel.close()
                except Exception:
                    pass
            connection.disconnect()

    def run(self):
        require(not self.cancelled.is_set(), 'CANCELLED')
        if hasattr(sys, 'getandroidapilevel'):
            return self._android()
        deadline = time.monotonic() + 12
        context = ssl.create_default_context()
        try:
            import certifi
        except ImportError:
            pass
        else:
            context.load_verify_locations(cafile=certifi.where())
        self.connection = connection = http.client.HTTPSConnection(
            'www.haoke.org', timeout=8, context=context)
        self.close_connection = connection.close
        try:
            require(not self.cancelled.is_set(), 'CANCELLED')
            path = '/api/client-updates/v1/%s/%s' % (
                self.identity['applicationId'], self.identity['channel'])
            connection.request('GET', path, headers={
                'Accept': 'application/json', 'Accept-Encoding': 'identity',
                'User-Agent': 'PySolFC-Haoke-Updates/1'})
            response = connection.getresponse()
            require(response.status == 200, 'NETWORK')
            require(response.getheader('Content-Encoding', 'identity')
                    in ('', 'identity'), 'NETWORK')
            chunks, length = [], 0
            while True:
                remaining = deadline - time.monotonic()
                require(remaining > 0 and not self.cancelled.is_set(),
                        'CANCELLED')
                if connection.sock:
                    connection.sock.settimeout(remaining)
                chunk = response.read(min(4096, MAX_ENVELOPE + 1 - length))
                if not chunk:
                    break
                chunks.append(chunk)
                length += len(chunk)
                require(length <= MAX_ENVELOPE, 'TOO_LARGE')
            return b''.join(chunks)
        except (OSError, http.client.HTTPException):
            raise UpdateError('NETWORK') from None
        finally:
            connection.close()
