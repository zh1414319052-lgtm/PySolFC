"""Isolated v1 signature/policy/lifecycle fixtures; never publish test releases."""

import base64
import copy
import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from pysollib.haokeupdates import (FeedRequest, IDENTITIES, SOFTWARE_ID,
                                  UpdateError, UpdateStore, verify_manifest)
from pysollib.kivy.haokeupdates import HaokeUpdates

NOW = 1795476000


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(
        timespec='milliseconds').replace('+00:00', 'Z')


class Fixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private = Ed25519PrivateKey.generate()
        public = cls.private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        cls.keys = {'fixture': base64.b64encode(public).decode()}

    def setUp(self):
        self.identity = dict(applicationId='org.haoke.pysolfc', channel='stable',
                             certificateSha256=IDENTITIES['org.haoke.pysolfc'][1],
                             versionCode=100, versionName='fixture', sdk=37,
                             abis=['arm64-v8a'])
        self.release = dict(
            releaseId='isolated-fixture', softwareId=SOFTWARE_ID,
            versionCode=200, versionName='fixture.2', publishedAt=stamp(NOW - 60),
            notes={'zh': '本地签名测试', 'en': 'Local signed fixture'},
            pageUrl='https://haoke.org/software/%s/releases/isolated-fixture' % SOFTWARE_ID,
            apkSha256='a' * 64, certificateSha256=self.identity['certificateSha256'],
            sizeBytes=1024, minSdk=21, abis=['arm64-v8a'])
        self.payload = dict(schemaVersion=1, applicationId=self.identity['applicationId'],
                            channel='stable', revision=1, issuedAt=stamp(NOW),
                            expiresAt=stamp(NOW + 3600), status='published',
                            release=copy.deepcopy(self.release))

    def envelope(self, payload=None):
        raw = json.dumps(self.payload if payload is None else payload,
                         ensure_ascii=False).encode()
        return json.dumps(dict(algorithm='Ed25519', keyId='fixture',
                               payload=base64.b64encode(raw).decode(),
                               signature=base64.b64encode(self.private.sign(raw)).decode())).encode()

    def verify(self, payload=None, checkpoint=None, identity=None):
        return verify_manifest(self.envelope(payload), identity or self.identity,
                               checkpoint, now=NOW, public_keys=self.keys)


class ManifestTests(Fixtures):
    def test_native_openssl_accepts_exact_signed_bytes(self):
        self.assertTrue(self.verify()['available'])

    def test_real_server_none_signature_fixture(self):
        path = Path(__file__).resolve().parents[1] / 'tests/fixtures/haoke-updates-none.json'
        data = path.read_bytes()
        issued = json.loads(base64.b64decode(json.loads(data)['payload']))['issuedAt']
        now = datetime.fromisoformat(issued.replace('Z', '+00:00')).timestamp() + 1
        result = verify_manifest(data, self.identity, now=now)
        self.assertFalse(result['available'])
        self.assertEqual(result['checkpoint']['revision'], 0)

    def test_tampering_unknown_key_and_oversize_are_rejected(self):
        original = json.loads(self.envelope())
        bad = dict(original, signature=base64.b64encode(b'0' * 64).decode())
        for data in (json.dumps(bad).encode(), b'x' * 65537,
                     json.dumps(dict(original, keyId='untrusted')).encode(), b'\xff'):
            with self.subTest(data=data[:20]), self.assertRaises(UpdateError):
                verify_manifest(data, self.identity, now=NOW, public_keys=self.keys)

    def test_product_channel_software_and_certificate_are_bound(self):
        changes = [({'applicationId': 'org.other.app'}, None),
                   ({'channel': 'qa'}, None),
                   ({}, {'softwareId': 'another-product'}),
                   ({}, {'certificateSha256': 'b' * 64})]
        for top, release in changes:
            payload = copy.deepcopy(self.payload)
            payload.update(top)
            if release:
                payload['release'].update(release)
            with self.subTest(top=top, release=release), self.assertRaises(UpdateError):
                self.verify(payload)

    def test_time_lifetime_and_schema_fail_closed(self):
        for changes in ({'expiresAt': stamp(NOW)},
                        {'issuedAt': stamp(NOW + 301)},
                        {'expiresAt': stamp(NOW + 49 * 3600)},
                        {'schemaVersion': 2}, {'revision': True}):
            with self.subTest(changes=changes), self.assertRaises(UpdateError):
                self.verify(dict(self.payload, **changes))

    def test_refresh_at_same_revision_allows_only_renewed_times(self):
        checkpoint = self.verify()['checkpoint']
        renewed = dict(self.payload, issuedAt=stamp(NOW + 10),
                       expiresAt=stamp(NOW + 7200))
        self.assertTrue(self.verify(renewed, checkpoint)['available'])
        changed = copy.deepcopy(self.payload)
        changed['release']['notes']['zh'] = 'Different business content'
        with self.assertRaises(UpdateError):
            self.verify(changed, checkpoint)

    def test_revision_and_maximum_version_do_not_roll_back(self):
        checkpoint = self.verify()['checkpoint']
        for payload in (dict(self.payload, revision=0),
                        dict(self.payload, revision=2,
                             release=dict(self.release, versionCode=199))):
            with self.assertRaises(UpdateError):
                self.verify(payload, checkpoint)

    def test_withdrawal_and_none_do_not_offer_cached_release(self):
        first = self.verify()
        withdrawn = dict(self.payload, revision=2, status='withdrawn', release=None)
        result = self.verify(withdrawn, first['checkpoint'])
        self.assertIsNone(result['release'])
        self.assertFalse(result['available'])
        with self.assertRaises(UpdateError):
            self.verify(checkpoint=result['checkpoint'])
        self.assertFalse(self.verify(dict(self.payload, status='none', revision=0,
                                          release=None))['available'])

    def test_incompatible_or_installed_versions_are_not_offered(self):
        for release in (dict(self.release, minSdk=38),
                        dict(self.release, abis=['armeabi-v7a']),
                        dict(self.release, versionCode=100)):
            self.assertFalse(self.verify(dict(self.payload, release=release))['available'])

    def test_url_is_exact_and_nonpublished_release_is_null(self):
        for url in ('http://haoke.org/software/x',
                    self.release['pageUrl'] + '?redirect=evil',
                    self.release['pageUrl'].replace('haoke.org', 'evil.example')):
            with self.assertRaises(UpdateError):
                self.verify(dict(self.payload, release=dict(self.release, pageUrl=url)))
        with self.assertRaises(UpdateError):
            self.verify(dict(self.payload, status='none', revision=0))

    def test_duplicate_json_and_noncanonical_base64_are_rejected(self):
        data = self.envelope().decode()
        data = data.replace('"algorithm": "Ed25519"',
                            '"algorithm":"Ed25519","algorithm":"Ed25519"')
        with self.assertRaises(UpdateError):
            verify_manifest(data.encode(), self.identity, now=NOW, public_keys=self.keys)
        envelope = json.loads(self.envelope())
        envelope['payload'] += '\n'
        with self.assertRaises(UpdateError):
            verify_manifest(json.dumps(envelope).encode(), self.identity,
                            now=NOW, public_keys=self.keys)


class StoreFixture(Fixtures):
    def setUp(self):
        super().setUp()
        self.temp = tempfile.TemporaryDirectory(prefix='pysolfc-update-test-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state.json'
        self.store = UpdateStore(self.path)
        self.manifest = self.verify()
        self.manifest['expiresAt'] = time.time() + 3600


class StoreTests(StoreFixture):
    def test_ack_persists_and_a_newer_version_is_eligible(self):
        self.assertTrue(self.store.should_prompt(self.manifest))
        self.store.remember(200, 'ack')
        restarted = UpdateStore(self.path)
        self.assertFalse(restarted.should_prompt(self.manifest))
        self.assertTrue(restarted.should_prompt(self.manifest, manual=True))
        newer = copy.deepcopy(self.manifest)
        newer['release']['versionCode'] = 201
        self.assertTrue(restarted.should_prompt(newer))

    def test_later_expires_ignore_does_not_and_manual_bypasses_both(self):
        self.store.remember(200, 'later', now=100)
        self.assertFalse(self.store.should_prompt(self.manifest, now=100 + 86399))
        self.assertTrue(self.store.should_prompt(self.manifest, now=100 + 86400))
        self.store.remember(200, 'ignore')
        self.assertFalse(self.store.should_prompt(self.manifest, now=10**12))
        self.assertTrue(self.store.should_prompt(self.manifest, manual=True))

    def test_route_exit_or_failed_presentation_does_not_consume_a_reminder(self):
        for guard, show in ((lambda: False, Mock()),
                            (Mock(side_effect=[True, False]), Mock()),
                            (lambda: True, Mock(side_effect=RuntimeError('closed')))):
            with self.assertRaises((UpdateError, RuntimeError)):
                self.store.present(self.manifest, show, guard)
            self.assertNotIn('reminder', self.store.state)
        show = Mock()
        self.assertTrue(self.store.present(self.manifest, show, lambda: True))
        show.assert_called_once()

    def test_storage_failure_never_shows_or_replaces_existing_checkpoint(self):
        self.store.update(checkpoint=self.manifest['checkpoint'])
        before = self.path.read_bytes()
        show = Mock()
        with patch('pysollib.haokeupdates.os.replace', side_effect=OSError('fixture')):
            with self.assertRaises(UpdateError):
                self.store.present(self.manifest, show, lambda: True)
        show.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertNotIn('reminder', self.store.state)


class FakeClock:
    def __init__(self):
        self.events = []

    def schedule_once(self, command, delay=0):
        event = SimpleNamespace(command=command, delay=delay, cancelled=False)
        event.cancel = lambda: setattr(event, 'cancelled', True)
        self.events.append(event)
        return event


class ControllerTests(StoreFixture):
    def controller(self):
        owner = SimpleNamespace(stopping=False, app=SimpleNamespace(
            game=SimpleNamespace(busy=False, demo=None), dn=SimpleNamespace(config=self.temp.name)),
            mainWindow=SimpleNamespace(visible_panel=SimpleNamespace(title='Main Menu')))
        controller = HaokeUpdates(owner, clock=FakeClock())
        controller.identity, controller.store = self.identity, self.store
        controller._toast = Mock()
        controller._message = Mock()
        return controller

    def start(self, controller, manual=False):
        with patch('pysollib.kivy.haokeupdates.threading.Thread') as thread:
            controller.check(manual=manual)
            return controller.flight, thread.call_count

    def test_single_flight_manual_promotion_and_twelve_second_deadline(self):
        controller = self.controller()
        flight, count = self.start(controller)
        self.assertEqual(count, 1)
        self.assertEqual(flight['deadline'].delay, 12)
        with patch('pysollib.kivy.haokeupdates.threading.Thread') as thread:
            controller.check(manual=True)
        thread.assert_not_called()
        self.assertTrue(flight['manual'])

    def test_background_dispose_and_competing_routes_discard_late_results(self):
        for action in ('background', 'dispose', 'route'):
            controller = self.controller()
            self.store.update(lastAttempt=0)
            flight, _ = self.start(controller)
            if action == 'background':
                controller.set_foreground(False)
            elif action == 'dispose':
                controller.dispose()
            else:
                controller.owner.mainWindow.visible_panel = None
                controller.route_changed()
            self.assertTrue(flight['request'].cancelled.is_set())
            before = copy.deepcopy(self.store.state)
            controller._complete(flight, self.manifest, None)
            self.assertEqual(self.store.state, before)
            controller._message.assert_not_called()

    def test_foreground_failure_retries_are_bounded_and_cancelled(self):
        controller = self.controller()
        controller._failed(False, 'NETWORK')
        first = controller.retry
        self.assertEqual(first.delay, 60)
        controller._failed(False, 'NETWORK')
        self.assertTrue(first.cancelled)
        self.assertEqual(controller.retry.delay, 300)
        controller._failed(False, 'NETWORK')
        self.assertIsNone(controller.retry)
        controller.failures = 0
        controller._failed(False, 'NETWORK')
        pending = controller.retry
        controller.set_foreground(False)
        self.assertTrue(pending.cancelled)
        self.assertIsNone(controller.retry)

    def test_timeout_keeps_one_worker_and_never_accepts_its_late_result(self):
        controller = self.controller()
        flight, _ = self.start(controller, manual=True)
        controller._timeout(flight)
        self.assertFalse(flight['valid'])
        controller._message.assert_called_once()
        with patch('pysollib.kivy.haokeupdates.threading.Thread') as thread:
            controller.check(manual=True)
        thread.assert_not_called()
        before = copy.deepcopy(self.store.state)
        controller._complete(flight, self.manifest, None)
        self.assertEqual(before, self.store.state)

    def test_restart_debounce_is_one_minute_and_manual_can_bypass_it(self):
        controller = self.controller()
        self.store.update(lastAttempt=time.time())
        flight, count = self.start(controller)
        self.assertIsNone(flight)
        self.assertEqual(count, 0)
        self.assertLessEqual(controller.retry.delay, 60)
        flight, count = self.start(controller, manual=True)
        self.assertEqual(count, 1)
        self.assertIsNotNone(flight)

    def test_cancelled_request_never_opens_a_connection(self):
        request = FeedRequest(self.identity)
        request.cancel()
        with patch('pysollib.haokeupdates.http.client.HTTPSConnection') as connection:
            with self.assertRaises(UpdateError):
                request.run()
        connection.assert_not_called()


class TransportTests(Fixtures):
    def test_https_transport_is_bounded_and_sends_no_identity_data(self):
        import io
        response = Mock(status=200)
        response.getheader.return_value = 'identity'
        response.read.side_effect = io.BytesIO(b'fixture-envelope').read
        connection = Mock()
        connection.getresponse.return_value = response
        with patch('pysollib.haokeupdates.http.client.HTTPSConnection',
                   return_value=connection) as factory:
            self.assertEqual(FeedRequest(self.identity).run(), b'fixture-envelope')
        self.assertEqual(factory.call_args.args[0], 'www.haoke.org')
        self.assertEqual(connection.request.call_args.args,
                         ('GET', '/api/client-updates/v1/org.haoke.pysolfc/stable'))
        headers = connection.request.call_args.kwargs['headers']
        self.assertNotIn('Authorization', headers)
        self.assertNotIn('Cookie', headers)
        connection.close.assert_called()

    def test_redirect_oversize_and_timeout_fail_closed_and_close_connection(self):
        import io
        for mode in ('redirect', 'oversize', 'timeout'):
            response = Mock(status=302 if mode == 'redirect' else 200)
            response.getheader.return_value = 'identity'
            response.read.side_effect = io.BytesIO(b'x' * 65537).read
            connection = Mock()
            if mode == 'timeout':
                connection.getresponse.side_effect = TimeoutError('fixture')
            else:
                connection.getresponse.return_value = response
            with self.subTest(mode=mode), patch(
                    'pysollib.haokeupdates.http.client.HTTPSConnection',
                    return_value=connection):
                with self.assertRaises(UpdateError):
                    FeedRequest(self.identity).run()
            connection.close.assert_called()


if __name__ == '__main__':
    unittest.main()
