# Copyright (c) 2026 sinascorpion. SPDX-License-Identifier: GPL-3.0-or-later
import contextlib
import importlib.util
import io
import json
import os
import shutil
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
        self.stack.enter_context(patch.object(m, 'certificate_usable', return_value=True))

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
        self.assertTrue((m.CERT_ROOT/'live'/self.old['cert_name']/'fullchain.pem').exists())
        self.assertTrue((m.CERT_ROOT/'mtproxy-web-retained'/(self.old['cert_name']+'.conf')).exists())
        self.assertFalse((m.CERT_ROOT/'renewal'/(self.old['cert_name']+'.conf')).exists())
        self.calls.clear()
        args = m.parser().parse_args(['install','--non-interactive','--domain',self.old['domain'],
                                      '--public-ip','8.8.8.8','--secret','34'*16])
        with patch.object(m, 'port_available'), \
             patch.object(m, 'install_binary', side_effect=lambda: m.write(m.BIN, 'fresh core', 0o755)):
            m.install(args)
        self.assertTrue(m.load()['complete'])
        self.assertTrue(m.load()['enabled'])
        self.assertEqual(m.load()['secret'], '34'*16)
        self.assertFalse(any(c[:2] == ['certbot', 'certonly'] for c in self.calls))
        self.assertTrue((m.CERT_ROOT/'renewal'/(self.old['cert_name']+'.conf')).exists())
        self.assertFalse((m.CERT_ROOT/'mtproxy-web-retained').exists())

    def test_secret_change_reuses_certificate_without_issuance(self):
        args = m.parser().parse_args(['configure', '--non-interactive', '--secret', '34'*16])
        m.install(args)
        self.assertEqual(m.load()['secret'], '34'*16)
        self.assertFalse(any(c[:2] == ['certbot', 'certonly'] for c in self.calls))

    def test_unusable_certificate_is_replaced(self):
        with patch.object(m, 'certificate_usable', return_value=False):
            m.install(m.configured_args())
        issuance = next(c for c in self.calls if c[:2] == ['certbot', 'certonly'])
        self.assertIn('--force-renewal', issuance)

    def test_failed_domain_change_returns_cached_certificate_to_paused_state(self):
        name = 'mtproxy-web-new.example.com'
        self.make_certificate(name)
        m.retain_certificate(name)
        self.fail_backend = True
        with self.assertRaises(RuntimeError):
            m.install(self.domain_args())
        self.assertEqual(m.load()['domain'], self.old['domain'])
        self.assertTrue((m.CERT_ROOT/'mtproxy-web-retained'/(name+'.conf')).exists())
        self.assertFalse((m.CERT_ROOT/'renewal'/(name+'.conf')).exists())
        self.assertFalse(any(c[:2] == ['certbot', 'certonly'] for c in self.calls))

    def test_certificate_can_be_deleted_explicitly_on_uninstall(self):
        m.uninstall(m.parser().parse_args(['uninstall', '--yes', '--delete-certificate']))
        self.assertFalse((m.CERT_ROOT/'live'/self.old['cert_name']).exists())
        self.assertFalse((m.CERT_ROOT/'mtproxy-web-retained').exists())

    def test_menu_routes_selected_actions_and_stops_after_full_removal(self):
        with patch('builtins.input', side_effect=['5','6','3','4','9','y','y','n']), \
             patch.object(m, 'set_enabled') as enabled, \
             patch.object(m, 'change_domain') as domain, \
             patch.object(m, 'change_secret') as secret, \
             patch.object(m, 'uninstall', return_value=True) as remove:
            m.menu()
        self.assertEqual([x.args[0] for x in enabled.call_args_list], [False, True])
        domain.assert_called_once()
        secret.assert_called_once()
        self.assertTrue(remove.call_args.args[0].remove_manager)

    def test_multiple_domains_secrets_tags_and_origin_ports(self):
        second = {**self.old, 'domain': 'two.example.com', 'secret': '34'*16,
                  'ad_tag': '56'*16, 'cdn': True, 'cdn_provider': 'other', 'origin_port': 2083}
        args = m.configured_args()
        args._profiles = [self.old, second]
        m.install(args)
        state = m.load()
        self.assertEqual(len(state['profiles']), 2)
        config, site = m.CONFIG.read_text(), m.SITE.read_text()
        self.assertIn('[access.user_ad_tags]', config)
        self.assertIn('user2 = "' + '56'*16 + '"', config)
        self.assertIn('host = "two.example.com"', config)
        self.assertEqual(site.count('upstream mtproxy_web_backend'), 1)
        self.assertEqual(site.count('map $http_upgrade'), 1)
        self.assertIn('listen 2083 ssl', site)
        self.assertEqual(len(state['cert_names']), 2)
        self.assertFalse(any(c[:2] == ['certbot', 'delete'] for c in self.calls))

    def test_multiple_secrets_on_one_domain_share_one_certificate_and_vhost(self):
        args = m.configured_args()
        args._profiles = [self.old, {**self.old, 'secret': '34'*16, 'ad_tag': '56'*16}]
        m.install(args)
        self.assertEqual(m.CONFIG.read_text().count('[[web.vhosts]]'), 1)
        self.assertEqual(m.CONFIG.read_text().count('[[web.vhosts.profiles]]'), 2)
        self.assertEqual(m.SITE.read_text().count('ssl_certificate_key'), 1)
        self.assertFalse(any(c[:2] == ['certbot', 'certonly'] for c in self.calls))

    def test_shared_secret_with_domain_specific_tags_has_distinct_users(self):
        items = m.validate_profiles([self.old, {**self.old, 'domain': 'two.example.com', 'ad_tag': '56'*16}])
        config = m.telemt_config({'profiles': items})
        self.assertIn('user = "default"', config)
        self.assertIn('user = "user2"', config)
        self.assertIn('user2 = "' + '56'*16 + '"', config)

    def test_conflicting_same_domain_cdn_settings_and_duplicate_pairs_are_rejected(self):
        for second in [self.old, {**self.old, 'secret': '34'*16, 'cdn_provider': 'other', 'origin_port': 2083}]:
            with self.assertRaises(ValueError):
                m.validate_profiles([self.old, second])

    def test_edit_one_profile_keeps_other_secret_and_reuses_ssl(self):
        args = m.configured_args()
        args._profiles = [self.old, {**self.old, 'secret': '34'*16}]
        m.install(args)
        self.calls.clear()
        args = m.configured_args()
        args._profile_index, args.secret = 1, '56'*16
        m.install(args)
        items = m.load()['profiles']
        self.assertEqual(items[0]['secret'], self.old['secret'])
        self.assertEqual(items[1]['secret'], '56'*16)
        self.assertFalse(any(c[:2] == ['certbot', 'certonly'] for c in self.calls))

    def test_wizard_pairs_domains_secrets_and_tags_in_input_order(self):
        args = m.parser().parse_args(['install', '--public-ip', '8.8.8.8'])
        answers = ['one.example.com','y','two.example.com','n','',
                   '12'*16,'y','34'*16,'56'*16,'y','78'*16,'none','443','none','443']
        with patch('builtins.input', side_effect=answers):
            items = m.wizard_profiles(args, {})
        self.assertEqual([(p['domain'], p['secret'], p['ad_tag']) for p in items],
                         [('one.example.com','12'*16,'56'*16), ('two.example.com','34'*16,'78'*16)])

    def test_wizard_can_share_one_secret_and_tag_across_domains(self):
        args = m.parser().parse_args(['install', '--public-ip', '8.8.8.8'])
        answers = ['one.example.com','y','two.example.com','n','',
                   '12'*16,'n','56'*16,'n','none','443','none','443']
        with patch('builtins.input', side_effect=answers):
            items = m.wizard_profiles(args, {})
        self.assertEqual(items[0]['secret'], items[1]['secret'])
        self.assertEqual(items[0]['ad_tag'], items[1]['ad_tag'])

    def test_blank_reinstall_wizard_preserves_all_existing_profiles(self):
        old = [self.old, {**self.old, 'domain':'two.example.com'},
               {**self.old, 'domain':'three.example.com','secret':'34'*16,'ad_tag':'56'*16}]
        args = m.parser().parse_args(['reinstall','--public-ip','8.8.8.8'])
        with patch('builtins.input', return_value=''):
            items = m.wizard_profiles(args, {**self.old,'profiles':old})
        self.assertEqual([(p['domain'],p['secret'],p['ad_tag']) for p in items],
                         [(p['domain'],p['secret'],p['ad_tag']) for p in old])

    def test_profile_menu_can_add_and_remove_without_replacing_other_profiles(self):
        second = {**self.old,'domain':'two.example.com','secret':'34'*16}
        with patch('builtins.input', side_effect=['1','0']), \
             patch.object(m,'wizard_profiles',return_value=[second]):
            m.manage_profiles()
        self.assertEqual(len(m.load()['profiles']),2)
        with patch('builtins.input', side_effect=['3','2','y','0']):
            m.manage_profiles()
        self.assertEqual(len(m.load()['profiles']),1)
        self.assertEqual(m.load()['secret'],self.old['secret'])

    def test_failed_addition_restores_all_existing_profiles(self):
        args = m.configured_args()
        args._profiles = [self.old,{**self.old,'secret':'34'*16}]
        m.install(args)
        previous = m.load()
        config,site = m.CONFIG.read_text(),m.SITE.read_text()
        args._profiles.append({**self.old,'domain':'two.example.com','secret':'56'*16})
        self.fail_backend = True
        with self.assertRaises(RuntimeError):
            m.install(args)
        self.assertEqual(m.load()['profiles'],previous['profiles'])
        self.assertEqual(m.CONFIG.read_text(),config)
        self.assertEqual(m.SITE.read_text(),site)


@unittest.skipUnless(os.name == 'posix' and shutil.which('openssl'), 'Requires Linux/OpenSSL')
class CertificateValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.patch = patch.object(m, 'CERT_ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.live = self.root/'live/test'
        self.live.mkdir(parents=True)
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(self.live/'privkey.pem'), '-out', str(self.live/'fullchain.pem'),
                        '-days', '1', '-subj', '/CN=valid.example.com',
                        '-addext', 'subjectAltName=DNS:valid.example.com'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_matching_certificate_and_private_key_can_be_reused(self):
        self.assertTrue(m.certificate_usable('test', 'valid.example.com'))

    def test_wrong_domain_is_not_reused(self):
        self.assertFalse(m.certificate_usable('test', 'other.example.com'))

    def test_expired_and_not_yet_valid_certificates_are_not_reused(self):
        real_run = m.run
        for timestamp in ('1', '4102444800'):
            def at_time(command, **kwargs):
                if command[:2] == ['openssl', 'verify']:
                    command = command[:2] + ['-attime', timestamp] + command[2:]
                return real_run(command, **kwargs)
            with self.subTest(timestamp=timestamp), patch.object(m, 'run', side_effect=at_time):
                self.assertFalse(m.certificate_usable('test', 'valid.example.com'))

    def test_missing_key_is_not_reused(self):
        (self.live/'privkey.pem').unlink()
        self.assertFalse(m.certificate_usable('test', 'valid.example.com'))

    def test_mismatched_private_key_is_not_reused(self):
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048',
                        '-out', str(self.live/'privkey.pem')], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.assertFalse(m.certificate_usable('test', 'valid.example.com'))


if __name__ == '__main__':
    unittest.main()
