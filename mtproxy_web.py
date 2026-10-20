#!/usr/bin/env python3
# Copyright (c) 2026 sinascorpion. SPDX-License-Identifier: GPL-3.0-or-later
"""sinascorpion Telegram WEB proxy installer. Python standard library only."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = '1.0.0'
TELEMT_VERSION = '3.5.14'
TELEMT_REVISION = '9d5b896bb695c55e2905b82f276da84e45a0a2ec'
# Official GitHub release asset SHA-256, fixed per architecture; never execute latest unchecked.
ASSETS = {
    'x86_64': ('x86_64', 'b10f86c6851f5c422a49d98deea55e8ef4aea7879605e59c1d4aa43c8f4c70ce'),
    'aarch64': ('aarch64', 'd2e3ca6a3f407aecb190c4a73db74ec581d56b5dd6ab469cb0e1d0f2c3d31c57'),
}
ETC = Path('/etc/mtproxy-web')
STATE = ETC / 'state.json'
CONFIG = ETC / 'telemt.toml'
DATA = Path('/var/lib/mtproxy-web')
CLI = Path('/usr/local/sbin/mtproxy-web')
BIN = Path('/usr/local/lib/mtproxy-web/telemt')
UNIT = Path('/etc/systemd/system/mtproxy-web.service')
SITE = Path('/etc/nginx/sites-available/mtproxy-web.conf')
ENABLED = Path('/etc/nginx/sites-enabled/mtproxy-web.conf')
HOOK = Path('/etc/letsencrypt/renewal-hooks/deploy/mtproxy-web-reload')
USER = 'mtproxy-web'
BACKEND_PORT = 18080
API_PORT = 18082
PACKAGES = ['nginx', 'certbot', 'ca-certificates']


def run(args, *, capture=False, check=True):
    return subprocess.run(args, check=check, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None,
                          env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})


def write(path, text, mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(text, encoding='utf-8')
    temp.chmod(mode)
    temp.replace(path)


def save(state):
    ETC.mkdir(mode=0o700, exist_ok=True)
    write(STATE, json.dumps(state, indent=2) + '\n', 0o600)


def load():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def installed_packages():
    result = run(['dpkg-query', '-W', '-f=${binary:Package}\t${db:Status-Status}\n'], capture=True)
    return sorted(line.split('\t')[0] for line in result.stdout.splitlines()
                  if line.endswith('\tinstalled'))


def normalize_domain(value):
    value = value.strip().rstrip('.').lower()
    try:
        value = value.encode('idna').decode('ascii')
    except UnicodeError as e:
        raise ValueError('Invalid domain / دامنه نامعتبر است') from e
    if len(value) > 253 or '.' not in value or any(
        not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', part)
        for part in value.split('.')
    ):
        raise ValueError('Enter only a domain, e.g. proxy.example.com (no https:// or path).')
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return value
    raise ValueError('A domain is required; an IP address cannot receive this certificate.')


def validate_hex(value, label, optional=False):
    value = value.strip().lower()
    if optional and not value:
        return ''
    if not re.fullmatch('[0-9a-f]{32}', value) or int(value, 16) == 0:
        raise ValueError(f'{label}: use exactly 32 hex characters, without dd/ee prefix; not all zero.')
    return value


def public_ipv4():
    with urllib.request.urlopen('https://api.ipify.org', timeout=15) as r:
        value = r.read(64).decode().strip()
    return str(ipaddress.IPv4Address(value))


def port_available(port):
    with socket.socket() as s:
        s.bind(('0.0.0.0', port))


def prompt(label, default=''):
    result = input(f'{label}' + (f' [{default}]' if default else '') + ': ').strip()
    return result or default


def validate_origin_port(value, provider):
    try:
        port = int(value)
    except (TypeError, ValueError) as e:
        raise ValueError('Origin HTTPS port must be an integer.') from e
    if port < 1 or port > 65535 or port in (22, 80, BACKEND_PORT, API_PORT):
        raise ValueError('Choose an HTTPS origin port from 1–65535, excluding SSH, HTTP and internal ports.')
    if provider == 'none' and port != 443:
        raise ValueError('Direct Telegram WEB connections require port 443. Other origin ports require a CDN mapping public 443 to the origin port.')
    return port


def validate_proxy_trust(cidrs, header):
    nets = [ipaddress.ip_network(cidr.strip(), strict=False) for cidr in cidrs if cidr.strip()]
    if any(net.prefixlen == 0 for net in nets):
        raise ValueError('Trust only your CDN/proxy ranges; /0 is not allowed.')
    if header and not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,63}', header):
        raise ValueError('Invalid client-IP header name.')
    if bool(nets) != bool(header):
        raise ValueError('Client-IP forwarding requires both trusted proxy CIDRs and a header name.')
    return list(map(str, nets)), header


def settings(args, previous):
    interactive = not args.non_interactive
    domain = args.domain or previous.get('domain', '')
    if interactive:
        print('\nTelegram Web Proxy Wizard — راه‌اندازی پروکسی وب تلگرام\n')
        domain = prompt('Domain / دامنه یا ساب‌دامنه', domain)
    domain = normalize_domain(domain)
    email = args.email if args.email is not None else previous.get('email', '')
    if interactive:
        email = prompt('ACME email (optional) / ایمیل تمدید SSL؛ اختیاری', email)
    if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise ValueError('Invalid email')
    tag = args.ad_tag if args.ad_tag is not None else previous.get('ad_tag', '')
    if interactive:
        print('Optional sponsor: obtain a 32-hex proxy tag from https://t.me/MTProxybot.')
        print('تگ اسپانسر ۳۲ کاراکتری از @MTProxybot؛ نام کانال کافی نیست. برای حذف تگ - وارد کن.')
        tag = prompt('Sponsor tag / تگ اسپانسر (Enter = skip/keep)', tag)
    if tag == '-':
        tag = ''
    tag = validate_hex(tag, 'Sponsor tag', optional=True)
    secret = validate_hex(args.secret or previous.get('secret') or secrets.token_hex(16), 'Secret')
    provider = args.cdn_provider or previous.get('cdn_provider') or ('cloudflare' if previous.get('cdn') else 'none')
    if args.cdn is not None and args.cdn_provider is None:
        provider = 'other' if args.cdn else 'none'
    if interactive:
        provider = prompt('CDN provider / حالت اتصال: none, cloudflare, other', provider).lower()
    if provider not in ('none', 'cloudflare', 'other'):
        raise ValueError('CDN provider must be none, cloudflare or other.')
    port = args.origin_port if args.origin_port is not None else previous.get('origin_port', 443)
    if interactive:
        print('Telegram uses public HTTPS 443. A different origin port needs a CDN origin-port override.')
        port = prompt('Origin HTTPS port / پورت HTTPS سرور مبدأ', str(port))
    port = validate_origin_port(port, provider)
    ranges = args.trusted_proxy_cidr if args.trusted_proxy_cidr is not None else previous.get('trusted_proxy_cidrs', [])
    header = args.client_ip_header if args.client_ip_header is not None else previous.get('client_ip_header', '')
    if provider == 'other' and interactive:
        print('Optional: trust a client-IP header only from your CDN official CIDRs. Enter - to clear.')
        ranges_text = prompt('Trusted CDN CIDRs (comma separated) / رنج‌های معتبر؛ اختیاری', ','.join(ranges))
        ranges = [] if ranges_text == '-' else ranges_text.split(',') if ranges_text else []
        if ranges:
            header = prompt('CDN client-IP header / نام هدر IP کاربر', header or 'X-Forwarded-For')
        else:
            header = ''
    if provider != 'other':
        ranges, header = [], ''
    elif not ranges and args.client_ip_header is None:
        header = ''
    ranges, header = validate_proxy_trust(ranges, header)
    address = args.public_ip or previous.get('public_ip') or public_ipv4()
    address = str(ipaddress.IPv4Address(address))
    if not ipaddress.ip_address(address).is_global:
        raise ValueError('public-ip must be a public IPv4 address.')
    return dict(domain=domain, email=email, ad_tag=tag, secret=secret,
                cdn=provider != 'none', cdn_provider=provider, public_ip=address,
                origin_port=port, trusted_proxy_cidrs=ranges, client_ip_header=header)


def telemt_config(s):
    tag = f'ad_tag = "{s["ad_tag"]}"\n' if s['ad_tag'] else ''
    middle = 'true' if s['ad_tag'] else 'false'
    return f'''# Managed by sinascorpion / telegram-web-proxy. WEB only; no public native MTProxy port.
[general]
use_middle_proxy = {middle}
{tag}log_level = "normal"
prefer_ipv6 = false

[general.modes]
classic = false
secure = true
tls = false

[general.links]
show = []

[network]
ipv4 = true
prefer = 4

[access.users]
default = "{s['secret']}"

[server.api]
enabled = true
listen = "127.0.0.1:{API_PORT}"
whitelist = ["127.0.0.1/32"]

[[server.listeners]]
ip = "127.0.0.1"
port = {BACKEND_PORT}
transport = "web"
proxy_protocol = false
web_client_ip_source = "x_forwarded_for"
web_trusted_proxy_cidrs = ["127.0.0.1/32"]

[web]
enabled = true
# HTTPS fallback also supports metadata-free compatible iOS clients.
carrier = "https"
carriers = ["websocket-lanes", "websocket", "https-lanes", "https"]
decoy_fasttrack_mode = "off"

[[web.vhosts]]
host = "{s['domain']}"
public_addr = "{s['public_ip']}:443"

[web.vhosts.decoy]
mode = "static_directory"
directory = "/var/lib/mtproxy-web/public"
index = "index.html"

[[web.vhosts.profiles]]
user = "default"
secret_mode = "dd"
max_sessions = 128
max_streams = 4096
max_streams_per_session = 64
'''


def nginx_config(s, tls=False, ranges=()):
    domain = s['domain']
    trust = ''.join(f'    set_real_ip_from {net};\n' for net in ranges)
    if trust:
        header = s.get('client_ip_header') or 'CF-Connecting-IP'
        trust += f'    real_ip_header {header};\n    real_ip_recursive off;\n'
    http = f'''# Managed by sinascorpion / telegram-web-proxy
server {{
    listen 80;
    server_name {domain};
    access_log off;
    location ^~ /.well-known/acme-challenge/ {{
        root /var/lib/mtproxy-web/acme;
        default_type text/plain;
        try_files $uri =404;
    }}
    location / {{ {'return 301 https://$host$request_uri;' if tls else 'return 503;'} }}
}}
'''
    if not tls:
        return http
    return http + f'''
upstream mtproxy_web_backend {{
    server 127.0.0.1:{BACKEND_PORT};
    keepalive 64;
}}
map $http_upgrade $mtproxy_web_upgrade {{
    default upgrade;
    '' '';
}}
server {{
    listen {s.get('origin_port', 443)} ssl http2;
    server_name {domain};
    ssl_certificate /etc/letsencrypt/live/{s['cert_name']}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{s['cert_name']}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    access_log off;
    # URI may contain a bridge capability. Never log failed request lines either.
    error_log /dev/null crit;
{trust}    client_max_body_size 2m;
    client_body_timeout 75s;
    send_timeout 75s;
    location / {{
        proxy_pass http://mtproxy_web_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $mtproxy_web_upgrade;
        proxy_connect_timeout 5s;
        proxy_send_timeout 75s;
        proxy_read_timeout 75s;
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_next_upstream off;
        add_header Cache-Control "no-store" always;
    }}
}}
'''


def cloudflare_ranges():
    # The API endpoint avoids website bot challenges on /ips-v4 and /ips-v6.
    request = urllib.request.Request('https://api.cloudflare.com/client/v4/ips',
                                     headers={'User-Agent': 'telegram-web-proxy/' + VERSION})
    with urllib.request.urlopen(request, timeout=30) as r:
        response = json.load(r)
    if not response.get('success'):
        raise ValueError('Cloudflare IP API failed')
    group = [ipaddress.ip_network(line) for key in ('ipv4_cidrs', 'ipv6_cidrs')
             for line in response['result'][key]]
    if len(group) < 2 or any(n.prefixlen == 0 or not n.is_global for n in group):
        raise ValueError('Invalid Cloudflare network response')
    return list(map(str, group))


def install_binary():
    arch = platform.machine()
    if arch not in ASSETS:
        raise ValueError('Supported architectures: x86_64, aarch64')
    arch_name, expected = ASSETS[arch]
    name = f'telemt-{arch_name}-linux-gnu.tar.gz'
    url = f'https://github.com/telemt/telemt/releases/download/{TELEMT_VERSION}/{name}'
    with tempfile.TemporaryDirectory(prefix='mtproxy-web-') as temp:
        archive = Path(temp) / name
        print(f'Downloading verified Telemt {TELEMT_VERSION} ({arch_name})…', flush=True)
        request = urllib.request.Request(url, headers={'User-Agent': 'telegram-web-proxy/' + VERSION})
        with urllib.request.urlopen(request, timeout=120) as r, archive.open('wb') as f:
            shutil.copyfileobj(r, f)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Telemt checksum mismatch; refusing to execute downloaded code.')
        with tarfile.open(archive) as tar:
            members = [m for m in tar.getmembers() if Path(m.name).name == 'telemt' and m.isfile()]
            if len(members) != 1:
                raise RuntimeError('Invalid Telemt release archive')
            BIN.parent.mkdir(parents=True, exist_ok=True)
            # Bootstrap deliberately uses umask 077; the unprivileged service must
            # still be able to traverse its root-owned binary directory.
            BIN.parent.chmod(0o755)
            with tar.extractfile(members[0]) as src, BIN.with_suffix('.new').open('wb') as dst:
                shutil.copyfileobj(src, dst)
            BIN.with_suffix('.new').chmod(0o755)
            BIN.with_suffix('.new').replace(BIN)


SERVICE = '''[Unit]
Description=sinascorpion Telegram WEB proxy (Telemt core)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=mtproxy-web
Group=mtproxy-web
WorkingDirectory=/var/lib/mtproxy-web
ExecStart=/usr/local/lib/mtproxy-web/telemt /etc/mtproxy-web/telemt.toml
Restart=on-failure
RestartSec=5
LimitNOFILE=65536
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/mtproxy-web
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK

[Install]
WantedBy=multi-user.target
'''


def set_site(text):
    write(SITE, text)
    if not ENABLED.exists():
        ENABLED.symlink_to(SITE)
    run(['nginx', '-t'])
    if run(['systemctl', 'is-active', '--quiet', 'nginx'], check=False).returncode:
        run(['systemctl', 'start', 'nginx'])
    else:
        run(['systemctl', 'reload', 'nginx'])


def wait_backend():
    for _ in range(45):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{API_PORT}/v1/runtime/web/status', timeout=2) as r:
                result = json.load(r)
            # API responses may wrap runtime payload in data.
            data = result.get('data', result)
            if data.get('ingress', {}).get('accepting_connections'):
                return
        except (OSError, ValueError):
            pass
        time.sleep(1)
    run(['journalctl', '-u', 'mtproxy-web', '-n', '30', '--no-pager'])
    raise RuntimeError('WEB listener did not become ready. Run: mtproxy-web status')


def link(s):
    return 'tg://webproxy?' + urllib.parse.urlencode({'server': s['domain'], 'secret': 'dd' + s['secret']})


def check_os():
    if platform.system() != 'Linux' or not Path('/run/systemd/system').exists():
        raise RuntimeError('Requires Ubuntu 22.04/24.04 with systemd.')
    values = {}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            values[key] = value.strip('"')
    if values.get('ID') != 'ubuntu' or values.get('VERSION_ID') not in ('22.04', '24.04'):
        raise RuntimeError('Supported: Ubuntu 22.04 and 24.04. Tested on Ubuntu 24.04 amd64.')
    if sys.version_info < (3, 10):
        raise RuntimeError('Python 3.10+ required')
    if platform.machine() not in ASSETS:
        raise RuntimeError('Only amd64 and arm64 are supported')


def install(args):
    check_os()
    previous = load()
    s = settings(args, previous)
    if previous and s['domain'] != previous.get('domain'):
        raise ValueError('Changing domain requires uninstall first; the current certificate is retained until then.')
    addresses = {item[4][0] for item in socket.getaddrinfo(s['domain'], 443, type=socket.SOCK_STREAM)}
    if not addresses:
        raise ValueError('Domain has no DNS address')
    if not s['cdn'] and addresses != {s['public_ip']}:
        raise ValueError(f'DNS must contain only {s["public_ip"]}; remove incorrect A/AAAA or select CDN mode.')
    ranges = cloudflare_ranges() if s['cdn_provider'] == 'cloudflare' else s['trusted_proxy_cidrs']
    if s['cdn_provider'] == 'cloudflare':
        s['client_ip_header'] = 'CF-Connecting-IP'
    if not previous:
        if run(['id', '-u', USER], capture=True, check=False).returncode == 0:
            raise RuntimeError('Service account already exists and is not managed by this installer.')
        for port in (80, s['origin_port'], BACKEND_PORT, API_PORT):
            try:
                port_available(port)
            except OSError as e:
                raise RuntimeError(f'Port {port} is occupied. Use a clean/dedicated server.') from e
        for path in (SITE, ENABLED, CONFIG, UNIT, CLI, BIN):
            if path.exists() or path.is_symlink():
                raise RuntimeError(f'Unmanaged path already exists: {path}')
        cert_name = 'mtproxy-web-' + s['domain']
        if Path('/etc/letsencrypt/renewal/' + cert_name + '.conf').exists():
            raise RuntimeError('An unmanaged certificate with this name already exists.')
        s.update(baseline=installed_packages(), created_user=False, cert_name=cert_name, complete=False)
        save(s)
    else:
        s = {**previous, **s}
        if not previous.get('complete'):
            save(s)
    if previous and s['origin_port'] != previous.get('origin_port', 443):
        port_available(s['origin_port'])
    print(f'Installing for {s["domain"]}; public HTTPS:443; origin HTTPS:{s["origin_port"]}; sponsor: {bool(s["ad_tag"])}', flush=True)
    # Keep a root-only recovery CLI even if certificate issuance later fails.
    if Path(__file__).resolve() != CLI.resolve():
        write(CLI, Path(__file__).read_text(encoding='utf-8'), 0o755)
    packages_before = set(installed_packages())
    try:
        run(['apt-get', 'update'])
        run(['apt-get', 'install', '-y', '--no-install-recommends', *PACKAGES])
    finally:
        s['added_packages'] = sorted(set(s.get('added_packages', [])) |
                                     (set(installed_packages()) - packages_before))
        if previous.get('complete'):
            previous['added_packages'] = s['added_packages']
            save(previous)
        else:
            save(s)
    if not previous.get('complete') or not BIN.exists():
        install_binary()
    if run(['id', '-u', USER], capture=True, check=False).returncode:
        run(['useradd', '--system', '--home-dir', str(DATA), '--no-create-home', '--shell', '/usr/sbin/nologin', USER])
        s['created_user'] = True
        save(s)
    elif not previous:
        raise RuntimeError('Service account already exists and is not managed by this installer.')
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / 'public').mkdir(exist_ok=True)
    (DATA / 'acme').mkdir(exist_ok=True)
    # NGINX must traverse the HTTP-01 webroot even under the bootstrap's umask.
    for directory in (DATA, DATA / 'public', DATA / 'acme'):
        directory.chmod(0o755)
    write(DATA / 'public/index.html', '<!doctype html><html lang="en"><meta charset="utf-8"><title>Welcome</title><h1>Welcome</h1><p>This website is online.</p></html>\n')
    run(['chown', '-R', f'{USER}:{USER}', str(DATA)])
    run(['chown', f'root:{USER}', str(ETC)])
    ETC.chmod(0o750)
    old_config = CONFIG.read_text() if CONFIG.exists() else None
    old_site = SITE.read_text() if SITE.exists() else None
    try:
        write(CONFIG, telemt_config(s), 0o640)
        run(['chown', f'root:{USER}', str(CONFIG)])
        write(UNIT, SERVICE)
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'enable', '--now', 'mtproxy-web'])
        if previous:
            run(['systemctl', 'restart', 'mtproxy-web'])
        wait_backend()
        certificate = Path('/etc/letsencrypt/live') / s['cert_name'] / 'fullchain.pem'
        if not certificate.exists():
            set_site(nginx_config(s))
            command = ['certbot', 'certonly', '--non-interactive', '--agree-tos', '--webroot',
                       '-w', str(DATA / 'acme'), '--cert-name', s['cert_name'], '-d', s['domain']]
            command += ['--email', s['email']] if s['email'] else ['--register-unsafely-without-email']
            run(command)
        set_site(nginx_config(s, tls=True, ranges=ranges))
        write(HOOK, '#!/bin/sh\nnginx -t && systemctl reload nginx\n', 0o755)
        run(['systemctl', 'enable', '--now', 'nginx', 'certbot.timer'])
        s['complete'] = True
        s['cloudflare_ranges'] = ranges
        save(s)
    except BaseException:
        if previous.get('complete') and old_config and old_site:
            write(CONFIG, old_config, 0o640)
            run(['chown', f'root:{USER}', str(CONFIG)])
            set_site(old_site)
            run(['systemctl', 'restart', 'mtproxy-web'], check=False)
            save(previous)
        raise
    print('\nsinascorpion — Installed / نصب شد\n' + link(s))
    print('Management: mtproxy-web configure | status | link | uninstall')
    if s['cdn']:
        print('CDN: use verified origin TLS, bypass cache, preserve headers/methods, support WebSockets and long polls; no JS challenges.')
        if s['cdn_provider'] == 'other' and not ranges:
            print('Client-IP forwarding is disabled: per-IP accounting sees CDN edge addresses until trusted ranges/header are configured.')
        if s['origin_port'] != 443:
            print(f'Configure your CDN: public HTTPS 443 -> origin HTTPS {s["origin_port"]}, with the original Host and TLS SNI. The installer cannot change your CDN account.')
    if s['ad_tag']:
        print('Sponsor configured via Telegram middle proxies. Channel display still requires a valid @MTProxybot registration.')


def status():
    s = load()
    if not s:
        raise RuntimeError('Not installed')
    print(f'Domain: {s["domain"]}\nTelemt: {TELEMT_VERSION}\nSponsor configured: {bool(s["ad_tag"])}')
    print(f'CDN: {s.get("cdn_provider", "none")}\nPublic port: 443\nOrigin port: {s.get("origin_port", 443)}')
    run(['systemctl', '--no-pager', '--full', 'status', 'mtproxy-web'], check=False)
    with urllib.request.urlopen(f'http://127.0.0.1:{API_PORT}/v1/runtime/web/status', timeout=5) as r:
        print(json.dumps(json.load(r), indent=2))


def uninstall(args):
    s = load()
    if not s:
        print('Nothing installed / نصب فعالی پیدا نشد')
        return
    if not args.yes and input('Delete this proxy, secret and certificate? / حذف کامل؟ [y/N]: ').strip().lower() != 'y':
        return
    print('Removing only mtproxy-web-owned resources…', flush=True)
    # Decide package removal before deleting recovery state. Never remove a baseline package.
    added = sorted((set(installed_packages()) - set(s['baseline'])) & set(s.get('added_packages', [])))
    if args.purge_dependencies and added:
        simulation = run(['apt-get', '-s', 'purge', *added], capture=True)
        removals = set(re.findall(r'^(?:Remv|Purg) (\S+)', simulation.stdout, re.M))
        baseline_names = {p.split(':')[0] for p in s['baseline']}
        if any(p.split(':')[0] in baseline_names for p in removals):
            raise RuntimeError('Dependency purge would remove a pre-existing package; refusing. Uninstall without --purge-dependencies.')
    run(['systemctl', 'disable', '--now', 'mtproxy-web'], check=False)
    ENABLED.unlink(missing_ok=True)
    SITE.unlink(missing_ok=True)
    HOOK.unlink(missing_ok=True)
    if shutil.which('nginx'):
        run(['nginx', '-t'])
        if run(['systemctl', 'is-active', '--quiet', 'nginx'], check=False).returncode == 0:
            run(['systemctl', 'reload', 'nginx'])
    if shutil.which('certbot') and Path('/etc/letsencrypt/renewal', s['cert_name'] + '.conf').exists():
        run(['certbot', 'delete', '--non-interactive', '--cert-name', s['cert_name']])
    UNIT.unlink(missing_ok=True)
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'reset-failed'], check=False)
    if s.get('created_user'):
        run(['userdel', USER], check=False)
    for p in (DATA, BIN.parent):
        if p.exists():
            shutil.rmtree(p)
    if args.purge_dependencies and added:
        run(['apt-get', 'purge', '-y', *added])
    shutil.rmtree(ETC)
    CLI.unlink(missing_ok=True)
    print('Removed. SSH, firewall and existing packages were preserved. / حذف شد')


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version', action='version', version=VERSION)
    sub = p.add_subparsers(dest='action', required=True)
    for action in ('install', 'configure'):
        s = sub.add_parser(action)
        s.add_argument('--non-interactive', action='store_true')
        s.add_argument('--domain')
        s.add_argument('--email')
        s.add_argument('--ad-tag', help='32 hex from @MTProxybot; - removes existing sponsor tag')
        s.add_argument('--secret', help='Raw 32 hex; omit to generate/keep')
        s.add_argument('--public-ip', help='Origin public IPv4; defaults to automatic detection')
        s.add_argument('--cdn', action=argparse.BooleanOptionalAction, default=None)
        s.add_argument('--cdn-provider', choices=['none', 'cloudflare', 'other'], help='Provider-neutral CDN mode; Cloudflare can populate trusted IP ranges automatically')
        s.add_argument('--origin-port', type=int, help='Origin HTTPS listen port; public Telegram WEB endpoint remains 443')
        s.add_argument('--trusted-proxy-cidr', action='append', help='Official trusted CIDR for other CDN providers; repeat for multiple ranges')
        s.add_argument('--client-ip-header', help='Client-IP header set/overwritten by the trusted CDN; optional with other providers')
    sub.add_parser('status')
    sub.add_parser('link')
    u = sub.add_parser('uninstall')
    u.add_argument('--yes', action='store_true')
    u.add_argument('--purge-dependencies', action='store_true', help='Also purge packages added by this installer; keep all baseline packages')
    return p


def main():
    args = parser().parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run as root / با کاربر root اجرا کن')
    import fcntl
    with open('/run/lock/mtproxy-web.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another mtproxy-web operation is running')
        try:
            if args.action in ('install', 'configure'):
                if args.action == 'configure' and not STATE.exists():
                    raise RuntimeError('Install first')
                install(args)
            elif args.action == 'status':
                status()
            elif args.action == 'link':
                state = load()
                if not state:
                    raise RuntimeError('Not installed')
                print(link(state))
            else:
                uninstall(args)
        except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as e:
            print(f'ERROR: {e}\nIf partially installed, fix DNS/ports then rerun, or run mtproxy-web uninstall --purge-dependencies.', file=sys.stderr)
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
