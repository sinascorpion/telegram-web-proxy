# Copyright (c) 2026 sinascorpion. SPDX-License-Identifier: GPL-3.0-or-later
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('management', Path(__file__).parents[1] / 'mtproxy_web.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


@unittest.skipUnless(os.name == 'posix', 'Service/filesystem lifecycle tests run on Ubuntu')
class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        paths = dict(ETC=root/'etc', STATE=root/'etc/state.json', CONFIG=root/'etc/telemt.toml',
                     DATA=root/'data', CLI=root/'sbin/mtproxy-web', MANAGER=root/'bin/sinascorpion-webproxy',
                     BIN=root/'lib/telemt', UNIT=root/'units/proxy.service', SITE=root/'nginx/proxy.conf',
                     ENABLED=root/'nginx/enabled', HOOK=root/'certs/hook', CERT_ROOT=root/'certs')
        for name, value in paths.items():
            self.stack.enter_context(patch.object(m, name, value))
        self.old = dict(domain='old.example.com', secret='12'*16, email='', ad_tag='', cdn=False,
                        cdn_provider='none', origin_port=443, public_ip='8.8.8.8',
                        trusted_proxy_cidrs=[], client_ip_header='', cloudflare_ranges=[],
                        baseline=['ubuntu-minimal'], added_packages=[], created_user=False,
                        cert_name='mtproxy-web-old.example.com', complete=True, enabled=True)
        m.save(self.old)
        m.write(m.CONFIG, 'OLD_CORE_CONFIG', 0o640)
        m.write(m.SITE, 'OLD_NGINX_CONFIG')
        m.write(m.BIN, 'placeholder executable', 0o755)
        self.make_certificate(self.old['cert_name'])
        self.calls = []
        self.fail_issue = False
        self.fail_backend = False
        self.migrating = False
        self.account_exists = True
        self.stack.enter_context(patch.object(m, 'run', side_effect=self.fake_run))
        self.stack.enter_context(patch.object(m, 'check_os'))
        self.stack.enter_context(patch.object(m, 'installed_packages', return_value=['ubuntu-minimal']))
        self.stack.enter_context(patch.object(m, 'wait_backend', side_effect=self.backend))
        self.stack.enter_context(patch.object(m, 'set_site', side_effect=lambda text: m.write(m.SITE, text)))
        self.stack.enter_context(patch.object(m.socket, 'getaddrinfo', return_value=[(2,1,6,'',('8.8.8.8',443))]))
        self.stack.enter_context(patch.object(m.shutil, 'which', return_value='/mock/bin'))

    def make_certificate(self, name):
        m.write(m.CERT_ROOT/'live'/name/'fullchain.pem', 'test certificate')
        m.write(m.CERT_ROOT/'renewal'/(name+'.conf'), 'test renewal')

    def fake_run(self, command, **kwargs):
        self.calls.append(command)
        if command[:2] == ['id', '-u']:
            return subprocess.CompletedProcess(command, 0 if self.account_exists else 1, stdout='', stderr='')
        if command[0] == 'useradd':
            self.account_exists = True
        if command[0] == 'userdel':
            self.account_exists = False
        if command[:2] == ['certbot', 'certonly']:
            # New-domain issuance cannot destroy the currently serving config.
            if self.migrating:
                self.assertEqual(m.CONFIG.read_text(), 'OLD_CORE_CONFIG')
                self.assertIn('OLD_NGINX_CONFIG', m.SITE.read_text())
            if self.fail_issue:
                raise subprocess.CalledProcessError(1, command)
            self.make_certificate(command[command.index('--cert-name')+1])
        if command[:2] == ['certbot', 'delete']:
            name = command[-1]
            if name == self.old['cert_name'] and self.migrating:
                self.assertEqual(m.load()['domain'], 'new.example.com')
                self.assertIn('new.example.com', m.CONFIG.read_text())
            (m.CERT_ROOT/'renewal'/(name+'.conf')).unlink(missing_ok=True)
            live = m.CERT_ROOT/'live'/name
            if live.exists():
                m.shutil.rmtree(live)
        return subprocess.CompletedProcess(command, 0, stdout='', stderr='')

    def backend(self):
        if self.fail_backend:
            raise RuntimeError('backend failed')

    def domain_args(self):
        self.migrating = True
        return m.parser().parse_args(['configure', '--non-interactive', '--domain', 'new.example.com'])

    def test_domain_change_commits_new_certificate_before_retiring_old_one(self):
        m.install(self.domain_args())
        state = m.load()
        self.assertEqual(state['domain'], 'new.example.com')
        self.assertEqual(state['secret'], self.old['secret'])
        self.assertEqual(state['cert_names'], ['mtproxy-web-new.example.com'])
        self.assertIn('new.example.com', m.SITE.read_text())
        self.assertTrue(m.owned_manager())

    def test_certificate_failure_restores_old_domain_and_certificate(self):
        self.fail_issue = True
        with self.assertRaises(subprocess.CalledProcessError):
            m.install(self.domain_args())
        self.assertEqual(m.load()['domain'], self.old['domain'])
        self.assertEqual(m.CONFIG.read_text(), 'OLD_CORE_CONFIG')
        self.assertEqual(m.SITE.read_text(), 'OLD_NGINX_CONFIG')
        self.assertFalse(any(c[:2] == ['certbot','delete'] for c in self.calls))

    def test_backend_failure_after_issuance_rolls_back_and_cleans_new_certificate(self):
        self.fail_backend = True
        with self.assertRaisesRegex(RuntimeError, 'backend failed'):
            m.install(self.domain_args())
        self.assertEqual(m.load()['domain'], self.old['domain'])
        self.assertEqual(m.CONFIG.read_text(), 'OLD_CORE_CONFIG')
        self.assertEqual(m.SITE.read_text(), 'OLD_NGINX_CONFIG')
        self.assertIn(['certbot','delete','--non-interactive','--cert-name','mtproxy-web-new.example.com'], self.calls)
        self.assertTrue((m.CERT_ROOT/'renewal'/(self.old['cert_name']+'.conf')).exists())

    def test_disable_enable_and_failed_enable_preserve_settings(self):
        m.set_enabled(False)
        self.assertFalse(m.load()['enabled'])
        self.assertNotIn('listen 443 ssl', m.SITE.read_text())
        self.assertIn('acme-challenge', m.SITE.read_text())
        self.assertIn(['systemctl','disable','--now','mtproxy-web'], self.calls)
        disabled_site = m.SITE.read_text()
        self.fail_backend = True
        with self.assertRaises(RuntimeError):
            m.set_enabled(True)
        self.assertFalse(m.load()['enabled'])
        self.assertEqual(m.SITE.read_text(), disabled_site)
        self.fail_backend = False
        m.set_enabled(True)
        self.assertTrue(m.load()['enabled'])
        self.assertEqual(m.load()['secret'], self.old['secret'])
        self.assertIn('listen 443 ssl', m.SITE.read_text())

    def test_reconfigure_does_not_silently_reenable_a_disabled_proxy(self):
        m.set_enabled(False)
        m.install(m.configured_args())
        self.assertFalse(m.load()['enabled'])
        self.assertNotIn('listen 443 ssl', m.SITE.read_text())

    def test_reinstall_replaces_core_and_preserves_secret(self):
        m.set_enabled(False)
        with patch.object(m, 'install_binary') as download:
            m.install(m.configured_args('reinstall'))
        download.assert_called_once()
        self.assertTrue(m.load()['enabled'])
        self.assertEqual(m.load()['secret'], self.old['secret'])

    def test_uninstall_can_keep_menu_or_remove_it_explicitly(self):
        m.install_manager()
        self.assertTrue(m.uninstall(m.parser().parse_args(['uninstall','--yes'])))
        self.assertFalse(m.STATE.exists())
        self.assertTrue(m.owned_manager())
        self.assertEqual(m.parser().parse_args([]).action, 'menu')
        self.assertTrue(m.uninstall(m.parser().parse_args(['uninstall','--yes','--remove-manager'])))
        self.assertFalse(m.CLI.exists())
        self.assertFalse(m.MANAGER.exists())

    def test_retained_menu_can_install_again_after_dependency_removal(self):
        self.old['created_user'] = True
        m.save(self.old)
        m.install_manager()
        m.uninstall(m.parser().parse_args(['uninstall','--yes','--purge-dependencies']))
        self.assertTrue(m.owned_manager())
        args = m.parser().parse_args(['install','--non-interactive','--domain',self.old['domain'],
                                      '--public-ip','8.8.8.8','--secret',self.old['secret']])
        with patch.object(m, 'port_available'), \
             patch.object(m, 'install_binary', side_effect=lambda: m.write(m.BIN, 'fresh core', 0o755)):
            m.install(args)
        self.assertTrue(m.load()['complete'])
        self.assertTrue(m.load()['enabled'])
        self.assertEqual(m.load()['secret'], self.old['secret'])

    def test_menu_routes_selected_actions_and_stops_after_full_removal(self):
        with patch('builtins.input', side_effect=['5','6','3','4','9','y','y']), \
             patch.object(m, 'set_enabled') as enabled, \
             patch.object(m, 'change_domain') as domain, \
             patch.object(m, 'change_secret') as secret, \
             patch.object(m, 'uninstall', return_value=True) as remove:
            m.menu()
        self.assertEqual([x.args[0] for x in enabled.call_args_list], [False, True])
        domain.assert_called_once()
        secret.assert_called_once()
        self.assertTrue(remove.call_args.args[0].remove_manager)


if __name__ == '__main__':
    unittest.main()
