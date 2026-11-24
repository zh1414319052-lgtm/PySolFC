"""Foreground-only Kivy presentation for Haoke signed update notifications."""

import copy
import logging
import threading
import time
import webbrowser
from pathlib import Path

from pysollib.haokeupdates import (FeedRequest, UpdateError, UpdateStore,
                                  android_identity, verify_manifest)
from pysollib.mygettext import _


class HaokeUpdates:
    def __init__(self, owner, clock=None):
        if clock is None:
            from kivy.clock import Clock
            clock = Clock
        self.clock = clock
        self.owner = owner
        self.identity = self.store = None
        self.foreground = True
        self.disposed = False
        self.eligible = False
        self.generation = 0
        self.flight = self.dialog = self.retry = self.route_timer = None
        self.failures = 0
        self.route_changed()

    def _ensure(self):
        if self.identity is None:
            identity = android_identity()
            name = 'haoke-updates-v1-%s-%s-%s.json' % (
                identity['applicationId'], identity['channel'],
                identity['certificateSha256'][:16])
            store = UpdateStore(Path(self.owner.app.dn.config) / name)
            self.identity, self.store = identity, store

    def _safe(self):
        app = self.owner.app
        panel = getattr(self.owner.mainWindow, 'visible_panel', None)
        return bool(not self.disposed and self.foreground
                    and not self.owner.stopping and app and app.game
                    and not app.game.busy and not app.game.demo
                    and panel and panel.title in (_('Main Menu'), _('Help')))

    def route_changed(self):
        if self.route_timer:
            self.route_timer.cancel()
        # Hide/invalidate immediately on route exit; wait for entry animation.
        if not self._safe():
            self._cancel()
            self.eligible = False
        if not self.disposed:
            self.route_timer = self.clock.schedule_once(self._settled, .3)

    def _settled(self, dt):
        self.route_timer = None
        safe = self._safe()
        entering = safe and not self.eligible
        self.eligible = safe
        if entering:
            self.failures = 0
            self.check()

    def set_foreground(self, foreground):
        self.foreground = foreground
        self.route_changed()

    def dispose(self):
        self.disposed = True
        self._cancel()
        if self.route_timer:
            self.route_timer.cancel()
            self.route_timer = None

    def _cancel(self):
        self.generation += 1
        if self.retry:
            self.retry.cancel()
            self.retry = None
        if self.flight:
            self.flight['deadline'].cancel()
            self.flight['request'].cancel()
            self.flight['valid'] = False
        if self.dialog:
            dialog, self.dialog = self.dialog, None
            try:
                dialog.dismiss()
            except Exception:
                logging.info('Haoke update dialog already closed')

    def _retry(self, delay):
        if self.retry:
            self.retry.cancel()
        if self.failures <= 2 and self._safe():
            self.retry = self.clock.schedule_once(self._retry_now, delay)

    def _retry_now(self, dt):
        self.retry = None
        if self._safe():
            self.check()

    def check(self, manual=False):
        if not self._safe() or self.dialog:
            return
        if self.flight:
            if self.flight['valid'] and manual:
                self.flight['manual'] = True
            if manual:
                self._toast(_('Checking for Haoke updates...'))
            return
        try:
            self._ensure()
            now = time.time()
            elapsed = now - self.store.state.get('lastAttempt', 0)
            if not manual and elapsed < 60:
                # Across restarts as well; a deferral does not lock out a day.
                self._retry(min(60, max(1, 60 - elapsed)))
                return
            self.store.update(lastAttempt=now)
        except Exception as exc:
            self._failed(manual, str(exc) if isinstance(exc, UpdateError)
                         else 'IDENTITY_MISMATCH')
            return
        if manual:
            self._toast(_('Checking for Haoke updates...'))
        generation = self.generation
        request = FeedRequest(self.identity)
        flight = dict(request=request, manual=manual, valid=True,
                      generation=generation)
        self.flight = flight
        checkpoint = copy.deepcopy(self.store.state.get('checkpoint'))
        identity = copy.deepcopy(self.identity)

        def work():
            result, error = None, None
            try:
                result = verify_manifest(request.run(), identity, checkpoint)
            except Exception as exc:
                error = str(exc) if isinstance(exc, UpdateError) else 'NETWORK'
            self.clock.schedule_once(lambda dt: self._complete(flight, result, error))

        thread = threading.Thread(target=work, name='HaokeUpdateCheck', daemon=True)
        flight['thread'] = thread
        flight['deadline'] = self.clock.schedule_once(
            lambda dt: self._timeout(flight), 12)
        thread.start()

    def _timeout(self, flight):
        if self.flight is flight and flight['valid']:
            flight['valid'] = False
            flight['request'].cancel()
            self._failed(flight['manual'], 'NETWORK')

    def _toast(self, text):
        from pysollib.kivy.androidtoast import AndroidToaster
        AndroidToaster.toastShort(text)

    def _complete(self, flight, manifest, error):
        if self.flight is not flight:
            return
        flight['deadline'].cancel()
        self.flight = None
        if (not flight['valid'] or flight['generation'] != self.generation
                or not self._safe()):
            # In particular: no persisted checkpoint/reminder from a late result.
            if self._safe():
                self._retry(60)
            return
        if error:
            self._failed(flight['manual'], error)
            return
        if manifest['expiresAt'] <= time.time():
            self._failed(flight['manual'], 'INVALID_TIME')
            return
        try:
            self.store.update(checkpoint=manifest['checkpoint'])
            self.failures = 0
            if manifest['available']:
                release = manifest['release']
                dialog = self._release_dialog(release)
                self.store.present(
                    manifest, lambda: self._open(dialog),
                    lambda: (self._safe()
                             and flight['generation'] == self.generation),
                    manual=flight['manual'])
            elif flight['manual']:
                self._message(_('No newer compatible Haoke version is available.'))
        except Exception:
            self._failed(flight['manual'], 'STORAGE')

    def _failed(self, manual, code):
        if self.retry:
            self.retry.cancel()
            self.retry = None
        self.failures += 1
        logging.info('Haoke update check unavailable (%s)',
                     code if code in ('NETWORK', 'STORAGE', 'CRYPTO_UNAVAILABLE',
                                      'INVALID_TIME', 'IDENTITY_MISMATCH')
                     else 'VALIDATION')
        if manual and self._safe():
            text = (_('Check the device date and time, then try again.')
                    if code == 'INVALID_TIME' else
                    _('Update check failed. Please try again later.'))
            try:
                self._message(text)
            except Exception:
                logging.info('Haoke update status cannot be displayed')
        elif self.failures <= 2:
            self._retry(60 if self.failures == 1 else 300)

    def _popup(self, message, actions):
        from kivy.metrics import dp, sp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.label import Label
        from kivy.uix.popup import Popup
        from kivy.uix.scrollview import ScrollView
        from pysollib.kivy import boardstyle as style
        root = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))
        style.backing(root, style.PAPER)
        scroll = ScrollView(do_scroll_x=False)
        label = Label(text=message, color=style.rgba(style.INK),
                      font_size=sp(17), size_hint_y=None, halign='left',
                      valign='top', markup=False)
        label.bind(texture_size=lambda obj, size:
                   setattr(obj, 'height', size[1] + dp(24)))
        scroll.bind(width=lambda obj, width:
                    setattr(label, 'text_size', (max(dp(40), width - dp(8)), None)))
        scroll.add_widget(label)
        root.add_widget(scroll)
        rows = (len(actions) + 1) // 2
        buttons = GridLayout(cols=2 if len(actions) > 1 else 1,
                             size_hint_y=None, height=dp(54) * rows,
                             spacing=dp(8))
        popup = Popup(title=_('Check for Haoke updates'), content=root,
                      size_hint=(.94, .78), background='',
                      background_color=style.rgba(style.PAPER),
                      title_color=style.rgba(style.INK),
                      separator_color=style.rgba(style.GOLD))
        for title, callback in actions:
            button = Button(text=title, font_size=sp(15), background_normal='',
                            background_color=style.rgba(style.FELT))
            button.bind(on_release=lambda obj, command=callback: command(popup))
            buttons.add_widget(button)
        root.add_widget(buttons)

        def opened(*args):
            self.dialog = popup

        def dismissed(*args):
            if self.dialog is popup:
                self.dialog = None

        popup.bind(on_open=opened, on_dismiss=dismissed)
        return popup

    def _message(self, text):
        current = self.identity['versionName'] if self.identity else '?'
        text += '\n\n' + _('Current version: %s') % current
        text += '\n\n' + _('Update checks connect to haoke.org. No game data is sent.')
        self._open(self._popup(text, [(_('Close'), lambda popup: popup.dismiss())]))

    def _open(self, popup):
        self.dialog = popup
        try:
            popup.open()
        except Exception:
            self.dialog = None
            raise

    def _release_dialog(self, release):
        from pysollib.mygettext import myGettext
        language = 'zh' if myGettext.language.startswith('zh') else 'en'
        message = (_('New Haoke version: %s') % release['versionName']
                   + '\n\n' + release['notes'][language])

        def choice(popup, action):
            try:
                self.store.remember(release['versionCode'], action)
            except UpdateError:
                self._toast(_('Could not save the update preference.'))
                return
            popup.dismiss()

        def view(popup):
            popup.dismiss()
            webbrowser.open(release['pageUrl'])

        return self._popup(message, [
            (_('View update'), view),
            (_('Later'), lambda popup: choice(popup, 'later')),
            (_('Ignore this version'), lambda popup: choice(popup, 'ignore')),
            (_('Close'), lambda popup: popup.dismiss()),
        ])
