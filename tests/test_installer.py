# Copyright (c) 2026 sinascorpion. SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import hashlib
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
import urllib.parse
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('installer', Path(__file__).parents[1] / 'mtproxy_web.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ValidationTests(unittest.TestCase):
    def test_domain_rejects_config_injection_urls_and_ips(self):
        for domain in ['a.com; include /etc/passwd;', 'https://a.com', '1.2.3.4',
                       'x.com/path', 'a..com', '-bad.com', 'a.com\nserver {}']:
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                m.normalize_domain(domain)
        self.assertEqual(m.normalize_domain('Proxy.Example.com.'), 'proxy.example.com')

    def test_tag_and_secret_validation(self):
        for tag in ['@mychannel', '0' * 32, 'ab' * 15, 'dd' + 'ab' * 16, 'g' * 32]:
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                m.validate_hex(tag, 'tag')
        self.assertEqual(m.validate_hex('AB' * 16, 'tag'), 'ab' * 16)
        self.assertEqual(m.validate_hex('', 'tag', optional=True), '')

    @patch('builtins.print')
    def test_restoring_existing_web_secret_keeps_the_exact_link(self, _print):
        args = SimpleNamespace(secret=None)
        raw = 'abcdef0123456789' * 2
        old = dict(domain='proxy.example.com', secret=raw)
        with patch.object(m.getpass, 'getpass', return_value='DD' + raw.upper()):
            restored = m.choose_secret(args, {}, interactive=True)
        self.assertEqual(restored, raw)
        self.assertEqual(m.link(dict(domain=old['domain'], secret=restored)), m.link(old))
        with patch.object(m.getpass, 'getpass', return_value=''):
            self.assertEqual(m.choose_secret(args, old, interactive=True), raw)
        with patch.object(m.getpass, 'getpass', return_value=''), \
             patch.object(m.secrets, 'token_hex', return_value='12' * 16) as generator:
            self.assertEqual(m.choose_secret(args, {}, interactive=True), '12' * 16)
            generator.assert_called_once_with(16)

    def test_invalid_restoration_secret_retries_without_echoing_it(self):
        import contextlib
        output = io.StringIO()
        raw = '12' * 16
        invalid = 'ee' + raw
        with patch.object(m.getpass, 'getpass', side_effect=[invalid, 'dd' + raw]), \
             contextlib.redirect_stdout(output):
            self.assertEqual(m.choose_secret(SimpleNamespace(secret=None), {}, True), raw)
        self.assertNotIn(invalid, output.getvalue())
        for bad in ['0' * 32, 'dd' + '0' * 32, 'ee' + raw, 'g' * 32, '']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                m.choose_secret(SimpleNamespace(secret=bad), {}, False)
        self.assertEqual(m.choose_secret(SimpleNamespace(secret='dd' + raw), {}, False), raw)

    def test_web_only_and_sponsor_enables_middle_proxy(self):
        import tomllib
        state = dict(domain='proxy.example.com', public_ip='8.8.8.8', secret='12' * 16,
                     ad_tag='', cert_name='mtproxy-web-proxy.example.com')
        direct = tomllib.loads(m.telemt_config(state))
        self.assertFalse(direct['general']['use_middle_proxy'])
        self.assertEqual([l['transport'] for l in direct['server']['listeners']], ['web'])
        self.assertTrue(all(l['ip'] == '127.0.0.1' for l in direct['server']['listeners']))
        state['ad_tag'] = 'ab' * 16
        sponsored = tomllib.loads(m.telemt_config(state))
        self.assertTrue(sponsored['general']['use_middle_proxy'])
        self.assertEqual(sponsored['general']['ad_tag'], state['ad_tag'])

    def test_tls_config_preserves_path_and_disables_replay(self):
        state = dict(domain='proxy.example.com', cert_name='mtproxy-web-proxy.example.com')
        config = m.nginx_config(state, True, ['173.245.48.0/20'])
        self.assertIn('proxy_pass http://mtproxy_web_backend;', config)
        self.assertIn('proxy_next_upstream off;', config)
        self.assertIn('proxy_set_header X-Forwarded-For $remote_addr;', config)
        self.assertIn('access_log off;', config)
        self.assertNotIn('rewrite ', config)
        self.assertIn('real_ip_header CF-Connecting-IP;', config)

    def test_web_link_has_no_native_proxy_port(self):
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(m.link(dict(domain='proxy.example.com', secret='12' * 16))).query)
        self.assertEqual(query['secret'], ['dd' + '12' * 16])
        self.assertNotIn('port', query)

    def test_origin_ports_do_not_change_public_endpoint(self):
        import tomllib
        state = dict(domain='proxy.example.com', public_ip='8.8.8.8', secret='12' * 16,
                     ad_tag='', cert_name='mtproxy-web-proxy.example.com')
        for port in (443, 2053, 2083, 2087, 2096, 8443):
            with self.subTest(port=port):
                self.assertEqual(m.validate_origin_port(port, 'other'), port)
                state['origin_port'] = port
                self.assertIn(f'listen {port} ssl http2;', m.nginx_config(state, tls=True))
                self.assertEqual(tomllib.loads(m.telemt_config(state))['web']['vhosts'][0]['public_addr'], '8.8.8.8:443')
                self.assertNotIn('port=', m.link(state))
        with self.assertRaisesRegex(ValueError, 'require port 443'):
            m.validate_origin_port(2083, 'none')
        for port in (0, 22, 80, 18080, 18082, 65536, '443;include'):
            with self.subTest(invalid=port), self.assertRaises(ValueError):
                m.validate_origin_port(port, 'other')

    def test_other_cdn_trust_is_explicit_and_cannot_trust_everyone(self):
        for cidrs, header in [(['0.0.0.0/0'], 'X-Real-IP'), (['::/0'], 'X-Real-IP'),
                              ([], 'X-Forwarded-For'), (['192.0.2.0/24'], ''),
                              (['192.0.2.0/24'], 'X-Real-IP;bad')]:
            with self.subTest(cidrs=cidrs, header=header), self.assertRaises(ValueError):
                m.validate_proxy_trust(cidrs, header)
        nets, header = m.validate_proxy_trust(['192.0.2.0/24'], 'Fastly-Client-IP')
        state = dict(domain='proxy.example.com', cert_name='test', client_ip_header=header)
        config = m.nginx_config(state, tls=True, ranges=nets)
        self.assertIn('set_real_ip_from 192.0.2.0/24;', config)
        self.assertIn('real_ip_header Fastly-Client-IP;', config)
        self.assertNotIn('CF-Connecting-IP', config)
        self.assertNotIn('real_ip_header', m.nginx_config(state, tls=True))

    def test_generic_cdn_settings_do_not_assume_cloudflare(self):
        args = m.parser().parse_args(['install', '--non-interactive', '--domain', 'proxy.example.com',
                                      '--public-ip', '8.8.8.8', '--cdn', '--origin-port', '2083'])
        settings = m.settings(args, {})
        self.assertEqual(settings['cdn_provider'], 'other')
        self.assertEqual(settings['origin_port'], 2083)
        self.assertEqual(settings['trusted_proxy_cidrs'], [])
        self.assertEqual(settings['client_ip_header'], '')
        previous = dict(cdn=True, cdn_provider='cloudflare', client_ip_header='CF-Connecting-IP')
        settings = m.settings(args, previous)
        self.assertEqual(settings['client_ip_header'], '')

    def test_uninstall_refuses_dependency_removal_of_existing_os_package(self):
        state = dict(baseline=['ubuntu-minimal'], added_packages=['nginx'])
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(stdout='Purg nginx [1]\nRemv ubuntu-minimal [1]\n')

        with patch.object(m, 'load', return_value=state), \
             patch.object(m, 'installed_packages', return_value=['ubuntu-minimal', 'nginx']), \
             patch.object(m, 'run', side_effect=fake_run):
            with self.assertRaisesRegex(RuntimeError, 'pre-existing package'):
                m.uninstall(SimpleNamespace(yes=True, purge_dependencies=True))
        self.assertEqual(len(calls), 1)  # No stop/delete action took place.

    @unittest.skipUnless(os.name == 'posix', 'Unix permissions are checked on Ubuntu CI')
    def test_strict_bootstrap_umask_allows_service_to_traverse_binary_directory(self):
        archive = io.BytesIO()
        payload = b'not-executed-test-binary'
        with tarfile.open(fileobj=archive, mode='w:gz') as tar:
            entry = tarfile.TarInfo('telemt')
            entry.size = len(payload)
            tar.addfile(entry, io.BytesIO(payload))
        data = archive.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / 'service' / 'telemt'
            old_umask = os.umask(0o077)
            try:
                with patch.object(m, 'BIN', binary), \
                     patch.object(m, 'ASSETS', {'x86_64': ('x86_64', digest)}), \
                     patch.object(m.platform, 'machine', return_value='x86_64'), \
                     patch.object(m.urllib.request, 'urlopen', return_value=io.BytesIO(data)):
                    m.install_binary()
            finally:
                os.umask(old_umask)
            self.assertEqual(binary.parent.stat().st_mode & 0o777, 0o755)
            self.assertEqual(binary.stat().st_mode & 0o777, 0o755)
            self.assertEqual(binary.read_bytes(), payload)


if __name__ == '__main__':
    unittest.main()
