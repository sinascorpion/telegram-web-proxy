#!/usr/bin/env python3
# Copyright (c) 2026 sinascorpion. SPDX-License-Identifier: GPL-3.0-or-later
"""sinascorpion Telegram WEB proxy installer. Python standard library only."""
import argparse
import hashlib
import html
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import random
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
MANAGER = Path('/usr/local/bin/sinascorpion-webproxy')
MANAGER_SCRIPT = '#!/bin/sh\n# sinascorpion-webproxy management entry point\nexec /usr/local/sbin/mtproxy-web "$@"\n'
BIN = Path('/usr/local/lib/mtproxy-web/telemt')
UNIT = Path('/etc/systemd/system/mtproxy-web.service')
SITE = Path('/etc/nginx/sites-available/mtproxy-web.conf')
ENABLED = Path('/etc/nginx/sites-enabled/mtproxy-web.conf')
NGINX_ROOT = Path('/etc/nginx')
CERT_ROOT = Path('/etc/letsencrypt')
HOOK = CERT_ROOT / 'renewal-hooks/deploy/mtproxy-web-reload'
USER = 'mtproxy-web'
BACKEND_PORT = 18080
API_PORT = 18082
PACKAGES = ['nginx', 'certbot', 'ca-certificates', 'openssl']
NGINX_HASH_SETTINGS = '# Managed by telegram-web-proxy\nserver_names_hash_bucket_size 512;\n'

DEFAULT_SITE = '''<!doctype html>
<html lang="en" data-site="everyday-notes">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Practical notes on technology, the web and a calmer digital life.">
<meta name="theme-color" content="#173b3b">
<title>Everyday Notes — Notes for a digital life</title>
<style>
:root{--paper:#f5f4ef;--ink:#183332;--muted:#536462;--line:#d7ded8;--accent:#28615c;--white:#fff;--soft:#e6ece5;--gold:#d8b477}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.75 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
a{color:inherit;text-decoration-thickness:1px;text-underline-offset:5px}
a:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:5px}
.wrap{width:min(1120px,calc(100% - 48px));margin:auto}
.skip{position:absolute;left:16px;top:-90px;background:var(--white);padding:10px;z-index:2}.skip:focus{top:12px}
header{border-bottom:1px solid var(--line)}.header{min-height:88px;display:flex;align-items:center;justify-content:space-between;gap:24px}
.brand{display:flex;align-items:center;gap:5px;min-height:44px;font-size:21px;font-weight:750;letter-spacing:-1px;text-decoration:none}.brand span{font-weight:400;color:var(--muted)}
nav{display:flex;gap:26px}nav a{display:inline-flex;align-items:center;min-height:44px;text-decoration:none;font-size:14px}nav a:hover{color:var(--accent);text-decoration:underline}
.hero{padding:76px 0 64px;display:grid;grid-template-columns:1.3fr 1fr;gap:64px;align-items:center}
.eyebrow{font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--accent)}
h1,h2,h3,p{margin:0}h1{font:500 clamp(42px,5.5vw,70px)/1.08 Georgia,serif;letter-spacing:-2px;margin:18px 0 24px;max-width:650px}
.intro{color:var(--muted);max-width:480px;font-size:18px}.hero a{display:inline-block;margin-top:24px;font-weight:650;min-height:44px}
.art{position:relative;aspect-ratio:1.12;background:var(--ink);overflow:hidden;border-radius:3px}
.art:before,.art:after{content:"";position:absolute;border-radius:50%;width:68%;aspect-ratio:1;border:1px solid #78918a}
.art:before{top:12%;left:-14%;box-shadow:0 0 0 36px #ffffff08,0 0 0 72px #ffffff05}
.art:after{bottom:-22%;right:-12%;background:var(--gold);border:0}
.art-label{position:absolute;bottom:26px;left:28px;color:var(--white);font:italic 25px Georgia,serif;z-index:1;max-width:170px;line-height:1.3}
.section-head{border-top:1px solid var(--ink);padding:22px 0 30px;display:flex;justify-content:space-between;align-items:baseline;gap:16px}
h2{font:400 32px/1.2 Georgia,serif;letter-spacing:-.5px}.small{font-size:13px;color:var(--muted)}
.posts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:32px;padding-bottom:64px}
article{min-width:0}.category{font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:var(--accent);font-weight:750;margin-bottom:12px}
h3{font:400 26px/1.25 Georgia,serif;margin-bottom:14px}article>p{color:var(--muted);font-size:15px}
details{margin-top:16px;font-size:15px}summary{cursor:pointer;font-weight:650;min-height:44px;padding:8px 0;list-style-position:inside}summary:hover{color:var(--accent)}
details p{margin-top:14px;color:var(--muted)}details ol{padding-left:22px;color:var(--muted)}
.about{display:grid;grid-template-columns:1fr 1.5fr;gap:48px;border-top:1px solid var(--line);padding:42px 0 54px}.about p{color:var(--muted);max-width:640px}
footer{border-top:1px solid var(--line);padding:24px 0 32px}.footer{display:flex;align-items:center;justify-content:space-between;gap:24px;color:var(--muted);font-size:13px}.footer a{display:inline-flex;align-items:center;min-height:44px}
@media(max-width:760px){.hero{gap:32px;padding:42px 0;grid-template-columns:1fr}.art{aspect-ratio:1.8}.posts{grid-template-columns:1fr;gap:32px}.about{grid-template-columns:1fr;gap:16px}.section-head .small{display:none}article{padding-bottom:24px;border-bottom:1px solid var(--line)}.wrap{width:calc(100% - 36px)}nav{gap:16px}.header{min-height:76px}.brand{font-size:18px}h1{letter-spacing:-1.5px}.footer{flex-wrap:wrap}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header><div class="wrap header"><a class="brand" href="#">Everyday Notes</a><nav aria-label="Main navigation"><a href="#notes">Notes</a><a href="#about">About</a></nav></div></header>
<main id="main" class="wrap">
<section class="hero" aria-labelledby="title">
<div><p class="eyebrow">Welcome to Everyday Notes</p><h1>A little clarity for your digital life.</h1><p class="intro">Useful ideas about technology, the everyday web, and making more room for what matters.</p><a href="#notes">Explore the notes <span aria-hidden="true">↗</span></a></div>
<div class="art" aria-hidden="true"><span class="art-label">Less noise.<br>More perspective.</span></div>
</section>
<section id="notes" aria-labelledby="notes-title">
<div class="section-head"><h2 id="notes-title">From the notebook</h2><span class="small">Small reads. Practical ideas.</span></div>
<div class="posts">
<article><p class="category">Digital habits · 3 min read</p><h3>A calmer browser starts with fewer tabs.</h3><p>A few small changes can turn your browser into a place to focus, rather than a list of unfinished tasks.</p>
<details><summary>Read the note</summary><p>Keep a single window for the task in front of you. Put interesting articles in a reading list instead of leaving them open, and close tabs when you finish.</p><p>Review extensions occasionally. Keep the ones you use, remove the rest, and give new tools only the permissions they need. A simpler browser is easier to maintain.</p><p>At the end of the day, bookmark anything worth returning to. Tomorrow can start with a clean page.</p></details></article>
<article><p class="category">Everyday essentials · 4 min read</p><h3>A simple backup routine you can keep.</h3><p>The best backup plan is one you can repeat. Start small, automate the routine, and check that it works.</p>
<details><summary>Read the note</summary><p>Begin with files you cannot easily replace: photos, documents, and personal projects. Keep an additional copy on a separate device or a storage service you trust.</p><ol><li>Choose the folders that matter.</li><li>Schedule a regular backup.</li><li>Keep one copy separate from your main device.</li><li>Restore a sample file to check the process.</li></ol><p>A backup is useful only if you can recover it. Store any recovery instructions somewhere you can access when your main device is unavailable.</p></details></article>
<article><p class="category">The open web · 3 min read</p><h3>Why lightweight websites feel better.</h3><p>Readable pages, fewer distractions, and less waiting. Sometimes the most useful improvement is to simplify.</p>
<details><summary>Read the note</summary><p>A page does not need a large framework to share a useful idea. Clear headings, comfortable text, and straightforward navigation often do most of the work.</p><p>System fonts and small assets help pages load on slower connections. Good contrast and keyboard navigation make them easier for more people to use.</p><p>Build around the content first. Add a feature when it helps someone read, find, or understand something.</p></details></article>
</div></section>
<section class="about" id="about" aria-labelledby="about-title"><h2 id="about-title">A small corner of the web.</h2><p>Everyday Notes is a collection of short, practical notes about living with technology. No account to create, no feed to keep up with. Just a few ideas to read at your own pace.</p></section>
</main>
<footer><div class="wrap footer"><span>Everyday Notes</span><span>Thoughtfully simple.</span><a href="#main">Back to top ↑</a></div></footer>
</body>
</html>
'''
# Static decoys allow same-origin stylesheets, rather than inline style blocks.
DEFAULT_STYLE = DEFAULT_SITE.split('<style>', 1)[1].split('</style>', 1)[0]
DEFAULT_SITE = DEFAULT_SITE.replace('<style>' + DEFAULT_STYLE + '</style>',
                                    '<link rel="stylesheet" href="/site.css">')


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


def install_default_site():
    path = DATA / 'public/index.html'
    previous = path.read_text(encoding='utf-8') if path.exists() else ''
    legacy = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Welcome</title><h1>Welcome</h1><p>This website is online.</p></html>\n'
    if not path.exists() or previous == legacy or any(marker in previous for marker in
            ('data-site="sinascorpion-journal"', 'data-site="everyday-notes"')):
        write(DATA / 'public/site.css', DEFAULT_STYLE)
        write(path, DEFAULT_SITE)
        old_stylesheet = DATA / 'public/journal.css'
        if old_stylesheet.is_file() and old_stylesheet.read_text(encoding='utf-8') == DEFAULT_STYLE:
            old_stylesheet.unlink()


def domain_site(domain):
    """Stable public presentation derived only from the hostname, never credentials."""
    domain = normalize_domain(domain)
    rng = random.Random(int.from_bytes(hashlib.sha256(domain.encode('ascii')).digest(), 'big'))
    name = rng.choice(('Cedar', 'Willow', 'Amber', 'Quiet', 'Clear', 'Open', 'Morning', 'Maple'))
    name += ' ' + rng.choice(('Pages', 'Notes', 'Corner', 'Compass', 'Field', 'Window', 'Path', 'Letters'))
    palette = rng.choice((
        ('#f5f4ef','#183332','#28615c','#d8b477'),
        ('#f5f3ef','#392e3f','#69456d','#ccb191'),
        ('#f1f4f8','#20334c','#365b89','#c6ab78'),
        ('#f7f3ee','#45352e','#825237','#c5b57e'),
        ('#f2f5f1','#263c2b','#3c6747','#c7b179'),
        ('#f8f3f2','#442e35','#824856','#c7b392'),
    ))
    headline = rng.choice(('Small ideas for a more thoughtful day.',
                          'Make a little room for useful ideas.',
                          'Good things, simply explained.',
                          'A fresh perspective on everyday things.',
                          'Thoughtful notes for curious minds.',
                          'Less noise. A little more discovery.'))
    introduction = rng.choice(('Practical reading about everyday tools, creative habits, and the world around us.',
                               'A quiet place for useful discoveries and small ideas worth keeping.',
                               'Short guides and considered observations to explore at your own pace.',
                               'Simple observations about learning, making, and living with technology.'))
    entries = (
        ('Everyday tools', 'Give your browser a fresh start.',
         'A few small habits can make the web feel less cluttered.',
         'Keep the tabs you are using and save the rest to a reading list. Review browser extensions occasionally and remove the ones you no longer need.',
         'At the end of a session, bookmark anything worth returning to. Starting with a clear window can make the next task easier to find.'),
        ('Practical essentials', 'A backup routine that fits your week.',
         'A useful routine starts with the files that matter most.',
         'Choose a small set of important folders and keep an additional copy on a separate device or a storage service you trust.',
         'Set a reminder to check the copy and restore a sample file. A simple routine you can repeat is more useful than an elaborate plan you forget.'),
        ('The web', 'The pleasure of a lightweight page.',
         'Readable text and straightforward navigation go a long way.',
         'Start with the words and the structure. Clear headings and comfortable spacing help readers find their way without extra distractions.',
         'Smaller assets and system fonts can reduce loading time. Add a feature when it helps someone find, read, or understand something.'),
        ('Learning', 'Keep a notebook for small discoveries.',
         'You do not need a perfect system to keep a useful record.',
         'Write down an idea in a few sentences while it is still fresh. Add a title you will recognize later and one concrete example.',
         'Return to your notes once in a while. Connecting two small observations can be more interesting than collecting another long list of links.'),
        ('Creative habits', 'Leave a little space between tasks.',
         'A short pause can be a useful part of getting things done.',
         'Finish one small piece of work before opening the next. Write down where to resume, then step away from the screen for a moment.',
         'A change of pace does not need to be complicated. Make a drink, look outside, or clear your desk before you begin again.'),
        ('Photography', 'Notice the light before the subject.',
         'An ordinary scene can look different at another hour.',
         'Look for soft light near a window or an area of open shade. Notice where the highlights and shadows fall before choosing your frame.',
         'Try a second angle and keep the background simple. Practicing with familiar subjects is a good way to discover what catches your eye.'),
        ('Home workspace', 'Make a small desk work a little better.',
         'A comfortable corner starts with a few useful choices.',
         'Keep frequently used items within reach and put occasional tools away. Give cables a clear path and leave some open space in front of you.',
         'Work with the light you have and adjust the arrangement as your needs change. A workspace can be simple without being empty.'),
        ('Reading', 'Choose one thing to read slowly.',
         'Not every interesting page needs to become another open tab.',
         'Set aside one article or chapter you want to spend time with. Read it without switching between a dozen other things.',
         'Keep a sentence or an observation that stays with you. A small amount of reading can be rewarding when you give it your attention.'),
    )
    cards = []
    for category, title, lead, first, second in rng.sample(entries, 3):
        cards.append('<article><p class="category">' + html.escape(category) + '</p><h3>' + html.escape(title)
                     + '</h3><p>' + html.escape(lead) + '</p><details><summary>Read the note</summary><p>'
                     + html.escape(first) + '</p><p>' + html.escape(second) + '</p></details></article>')
    page = DEFAULT_SITE.replace('Everyday Notes', name).replace(' data-site="everyday-notes"', '')
    page = page.replace('A little clarity for your digital life.', html.escape(headline))
    page = page.replace('Useful ideas about technology, the everyday web, and making more room for what matters.', html.escape(introduction))
    page = re.sub(r'<div class="posts">.*?</div></section>',
                  '<div class="posts">' + '\n'.join(cards) + '</div></section>', page, flags=re.S)
    section_title = rng.choice(('Latest notes', 'A few things worth reading', 'On the reading table', 'Ideas to take with you'))
    page = page.replace('From the notebook', section_title)
    page = page.replace('Thoughtfully simple.', rng.choice(('Read at your own pace.', 'Small ideas, thoughtfully collected.', 'A little curiosity goes a long way.')))
    paper, ink, accent, gold = palette
    style = DEFAULT_STYLE + f'\n:root{{--paper:{paper};--ink:{ink};--accent:{accent};--gold:{gold}}}\n'
    style += rng.choice(('.hero{grid-template-columns:1.3fr 1fr}',
                         '.hero{grid-template-columns:1fr 1.1fr}.art{border-radius:40px 3px 40px 3px}',
                         '.art{border-radius:50% 50% 3px 3px}'))
    style += '\n@media(max-width:760px){.hero{grid-template-columns:1fr}}\n'
    return page, style


def site_directory(domain):
    """Keep a pre-existing custom shared site; defaults get one directory per host."""
    root = DATA / 'public'
    if (root / 'index.html').exists():
        content = (root / 'index.html').read_text(encoding='utf-8')
        if not any(marker in content for marker in ('data-site="everyday-notes"', 'data-site="sinascorpion-journal"',
                                                    '<p>This website is online.</p>')):
            return root
    return DATA / 'sites' / normalize_domain(domain)


def install_domain_sites(s):
    install_default_site()
    manifest_path = ETC / 'sites.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for domain in dict.fromkeys(p['domain'] for p in profile_list(s)):
        directory = site_directory(domain)
        if directory == DATA / 'public':
            continue
        directory.parent.mkdir(parents=True, exist_ok=True)
        directory.parent.chmod(0o755)
        directory.mkdir(exist_ok=True)
        directory.chmod(0o755)
        page, style = domain_site(domain)
        paths = (directory / 'index.html', directory / 'site.css')
        existing = [hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None for p in paths]
        if any(p.exists() for p in paths) and manifest.get(domain) != existing:
            continue  # Preserve a site the administrator customized.
        write(paths[0], page)
        write(paths[1], style)
        manifest[domain] = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    write(manifest_path, json.dumps(manifest, indent=2) + '\n', 0o600)


def save(state):
    ETC.mkdir(mode=0o700, exist_ok=True)
    write(STATE, json.dumps(state, indent=2) + '\n', 0o600)


def load():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def owned_manager():
    return (MANAGER.is_file() and MANAGER.read_text() == MANAGER_SCRIPT
            and CLI.is_file() and 'Copyright (c) 2026 sinascorpion' in CLI.read_text()[:200])


def install_manager():
    if MANAGER.exists() and MANAGER.read_text() != MANAGER_SCRIPT:
        raise RuntimeError(f'Unmanaged command already exists: {MANAGER}')
    if Path(__file__).resolve() != CLI.resolve():
        write(CLI, Path(__file__).read_text(encoding='utf-8'), 0o755)
    write(MANAGER, MANAGER_SCRIPT, 0o755)


def remove_manager():
    if MANAGER.exists() and MANAGER.read_text() == MANAGER_SCRIPT:
        MANAGER.unlink()
    if CLI.exists():
        if 'Copyright (c) 2026 sinascorpion' not in CLI.read_text()[:200]:
            raise RuntimeError(f'Refusing to remove an unmanaged command: {CLI}')
        CLI.unlink()


def owned_certificates(s):
    return list(dict.fromkeys(s.get('cert_names', []) + [s['cert_name']]))


def installed_packages():
    result = run(['dpkg-query', '-W', '-f=${binary:Package}\t${db:Status-Status}\n'], capture=True)
    return sorted(line.split('\t')[0] for line in result.stdout.splitlines()
                  if line.endswith('\tinstalled'))


def stock_nginx_only():
    """Recognize an unchanged Ubuntu default server, never a custom NGINX site."""
    conf = NGINX_ROOT / 'conf.d'
    enabled = NGINX_ROOT / 'sites-enabled'
    default = NGINX_ROOT / 'sites-available/default'
    if not enabled.is_dir() or (conf.exists() and any(conf.iterdir())):
        return False
    entries = list(enabled.iterdir())
    if len(entries) != 1 or entries[0].name != 'default' or entries[0].resolve() != default.resolve():
        return False
    result = run(['dpkg-query', '-W', '-f=${Conffiles}', 'nginx-common'], capture=True, check=False)
    if result.returncode:
        return False
    hashes = dict(re.findall(r'^\s*(/\S+)\s+([0-9a-f]{32})(?:\s+obsolete)?\s*$', result.stdout, re.M))
    for path in (NGINX_ROOT / 'nginx.conf', default):
        if not path.is_file() or hashlib.md5(path.read_bytes()).hexdigest() != hashes.get(str(path)):
            return False
    return True


def normalize_domain(value):
    value = value.strip().rstrip('.').lower()
    try:
        value = value.encode('idna').decode('ascii')
    except UnicodeError as e:
        raise ValueError('Invalid domain') from e
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


def normalize_secret(value):
    value = value.strip().lower()
    if len(value) == 34 and value.startswith('dd'):
        value = value[2:]
    return validate_hex(value, 'WEB secret')


def choose_secret(args, previous, interactive):
    candidate = args.secret if args.secret is not None else previous.get('secret')
    if interactive:
        print('Use an existing WEB secret (32 hex or dd + 32 hex), or press Enter to keep/generate:')
        while True:
            entered = input('Secret (Enter = keep/generate): ').strip()
            if not entered:
                break
            try:
                selected = normalize_secret(entered)
                print(f'Proxy secret: {selected}')
                return selected
            except ValueError:
                print('Invalid WEB secret: enter 32 hex or dd + 32 hex; not an ee/FakeTLS secret.')
    selected = normalize_secret(candidate) if candidate is not None else secrets.token_hex(16)
    if interactive:
        print(f'Proxy secret: {selected}')
    return selected


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


def settings(args, previous, identity=None):
    if identity is not None:
        previous = {**previous, **identity}
    interactive = not args.non_interactive and identity is None
    domain = args.domain or previous.get('domain', '')
    if interactive:
        print('\nTelegram Web Proxy Wizard')
        domain = prompt('Domain', domain)
    domain = normalize_domain(domain)
    email = args.email if args.email is not None else previous.get('email', '')
    if interactive:
        email = prompt('ACME email (optional)', email)
    if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise ValueError('Invalid email')
    secret = choose_secret(args, previous, interactive)
    tag = args.ad_tag if args.ad_tag is not None else previous.get('ad_tag', '')
    if interactive:
        print('Optional sponsor: obtain a 32-hex proxy tag from https://t.me/MTProxybot.')
        tag = prompt('Sponsor tag', tag)
    if tag == '-':
        tag = ''
    tag = validate_hex(tag, 'Sponsor tag', optional=True)
    if identity is not None:
        domain, email, secret, tag = (identity[k] for k in ('domain', 'email', 'secret', 'ad_tag'))
        interactive = not args.non_interactive
    provider = args.cdn_provider or previous.get('cdn_provider') or ('cloudflare' if previous.get('cdn') else 'none')
    if args.cdn is not None and args.cdn_provider is None:
        provider = 'other' if args.cdn else 'none'
    if interactive:
        provider = prompt('CDN provider: none, cloudflare, other', provider).lower()
    if provider not in ('none', 'cloudflare', 'other'):
        raise ValueError('CDN provider must be none, cloudflare or other.')
    port = args.origin_port if args.origin_port is not None else previous.get('origin_port', 443)
    if interactive:
        print('Telegram uses public HTTPS 443. A different origin port needs a CDN origin-port override.')
        port = prompt('Origin HTTPS port', str(port))
    port = validate_origin_port(port, provider)
    ranges = args.trusted_proxy_cidr if args.trusted_proxy_cidr is not None else previous.get('trusted_proxy_cidrs', [])
    header = args.client_ip_header if args.client_ip_header is not None else previous.get('client_ip_header', '')
    if provider == 'other' and interactive:
        print('Optional: trust a client-IP header only from your CDN official CIDRs. Enter - to clear.')
        ranges_text = prompt('Trusted CDN CIDRs (comma separated)', ','.join(ranges))
        ranges = [] if ranges_text == '-' else ranges_text.split(',') if ranges_text else []
        if ranges:
            header = prompt('CDN client-IP header', header or 'X-Forwarded-For')
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


def profile_list(s):
    return s.get('profiles') or ([s] if s else [])


def validate_profiles(items):
    if not items or len(items) > 32:
        raise ValueError('Use 1–32 profiles.')
    pairs, hosts = set(), {}
    result = []
    for item in items:
        args = parser().parse_args(['configure', '--non-interactive'])
        p = settings(args, item)
        p['cert_name'] = 'mtproxy-web-' + p['domain']
        pair = p['domain'], p['secret']
        if pair in pairs:
            raise ValueError('This domain/secret pair already exists.')
        pairs.add(pair)
        connection = tuple(json.dumps(p[k], sort_keys=True) for k in
                           ('cdn_provider', 'origin_port', 'trusted_proxy_cidrs', 'client_ip_header', 'public_ip'))
        if p['domain'] in hosts and hosts[p['domain']] != connection:
            raise ValueError('Profiles sharing a domain must use the same CDN/port settings.')
        hosts[p['domain']] = connection
        result.append(p)
    return result


def wizard_profiles(args, previous):
    old = profile_list(previous)
    domains = []
    while True:
        index = len(domains)
        domain = normalize_domain(prompt(f'Domain {index + 1}', old[index]['domain'] if index < len(old) else ''))
        domains.append(domain)
        if len(domains) >= 32 or prompt('Add another domain?', 'y' if index + 1 < len(old) else 'n').lower() != 'y':
            break
    email = prompt('SSL email (optional)', previous.get('email', ''))
    if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise ValueError('Invalid email')
    values = []
    for index in range(len(domains)):
        print(f'Secret {index + 1}')
        values.append(choose_secret(args, old[index] if index < len(old) else {}, True))
        separate = 'y' if any(p['secret'] != values[-1] for p in old[index + 1:len(domains)]) else 'n'
        if index + 1 < len(domains) and prompt('Separate secret for next domain? (n = reuse this for the rest)', separate).lower() != 'y':
            values.extend([values[-1]] * (len(domains) - len(values)))
            break
    tags = []
    for index in range(len(domains)):
        tag = prompt(f'Sponsor tag {index + 1} (optional, @MTProxybot)', old[index].get('ad_tag', '') if index < len(old) else '')
        tags.append(validate_hex('' if tag == '-' else tag, 'Sponsor tag', optional=True))
        separate = 'y' if any(p.get('ad_tag', '') != tags[-1] for p in old[index + 1:len(domains)]) else 'n'
        if index + 1 < len(domains) and prompt('Separate tag for next domain? (n = reuse this for the rest)', separate).lower() != 'y':
            tags.extend([tags[-1]] * (len(domains) - len(tags)))
            break
    result = []
    for index, domain in enumerate(domains):
        print(f'CDN / HTTPS — {domain}')
        base = old[index] if index < len(old) else result[0] if result else {}
        if not old:
            base = next((p for p in getattr(args, '_connection_defaults', []) if p['domain'] == domain), base)
        identity = dict(domain=domain, email=email, secret=values[index], ad_tag=tags[index])
        result.append(settings(args, base, identity))
    return validate_profiles(result)


def telemt_config(s):
    if s.get('profiles'):
        items = profile_list(s)
        # Preserve the single-profile format and backwards-compatible user name.
        base = telemt_config({**items[0], 'profiles': None})
        if len(items) == 1:
            return base
        users = {}
        for p in items:
            key = p['secret'], p['ad_tag']
            users.setdefault(key, 'default' if not users else f'user{len(users) + 1}')
        user_text = '[access.users]\n' + ''.join(f'{name} = "{key[0]}"\n' for key, name in users.items())
        tags = {users[(p['secret'], p['ad_tag'])]: p['ad_tag'] for p in items if p['ad_tag']}
        if tags:
            user_text += '\n[access.user_ad_tags]\n' + ''.join(f'{u} = "{tag}"\n' for u, tag in tags.items())
        base = re.sub(r'\[access.users\].*?(?=\[server.api\])', user_text + '\n', base, flags=re.S)
        base = re.sub(r'^ad_tag = .*\n', '', base, flags=re.M)
        base = re.sub(r'use_middle_proxy = (?:true|false)', 'use_middle_proxy = ' + ('true' if tags else 'false'), base)
        base = base.split('[[web.vhosts]]')[0]
        base += '[web.limits]\nmax_vhosts = 32\nmax_profiles = 32\n\n'
        for domain in dict.fromkeys(p['domain'] for p in items):
            group = [p for p in items if p['domain'] == domain]
            vhost = telemt_config({**group[0], 'profiles': None}).split('[[web.vhosts]]', 1)[1]
            vhost = vhost.split('[[web.vhosts.profiles]]')[0]
            base += '[[web.vhosts]]' + vhost
            for p in group:
                block = telemt_config({**p, 'profiles': None}).split('[[web.vhosts.profiles]]', 1)[1]
                base += '[[web.vhosts.profiles]]' + block.replace('user = "default"', f'user = "{users[(p["secret"], p["ad_tag"])]}"')
        return base
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
directory = "{site_directory(s['domain']).as_posix()}"
index = "index.html"

[[web.vhosts.profiles]]
user = "default"
secret_mode = "dd"
max_sessions = 128
max_streams = 4096
max_streams_per_session = 64
'''


def nginx_config(s, tls=False, ranges=(), shared=True):
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
    common = f'''
upstream mtproxy_web_backend {{
    server 127.0.0.1:{BACKEND_PORT};
    keepalive 64;
}}
map $http_upgrade $mtproxy_web_upgrade {{
    default upgrade;
    '' '';
}}
'''
    return http + (common if shared else '') + f'''
server {{
    listen {s.get('origin_port', 443)} ssl http2;
    server_name {domain};
    ssl_certificate {CERT_ROOT}/live/{s['cert_name']}/fullchain.pem;
    ssl_certificate_key {CERT_ROOT}/live/{s['cert_name']}/privkey.pem;
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


def nginx_sites(s, tls=False):
    sites, seen = [], set()
    for p in profile_list(s):
        if p['domain'] in seen:
            continue
        seen.add(p['domain'])
        sites.append(nginx_config(p, tls=tls, ranges=p.get('cloudflare_ranges', []), shared=len(seen) == 1))
    return '\n'.join(sites)


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


def nginx_hash_path():
    return NGINX_ROOT / 'conf.d/mtproxy-web-hash.conf'


def ensure_nginx_hash_settings():
    owned = nginx_hash_path()
    if owned.exists() and owned.read_text() != NGINX_HASH_SETTINGS:
        raise RuntimeError(f'Unmanaged NGINX settings already exist: {owned}')
    files = [NGINX_ROOT / 'nginx.conf']
    files += list((NGINX_ROOT / 'conf.d').glob('*.conf'))
    files += list((NGINX_ROOT / 'sites-enabled').glob('*'))
    external = []
    for path in files:
        if path == owned or path.resolve() == SITE.resolve() or not path.is_file():
            continue
        external += re.findall(r'^\s*server_names_hash_bucket_size\s+(\d+)\s*;', path.read_text(), re.M)
    if external:
        if any(int(value) < 512 for value in external):
            raise RuntimeError('Existing custom server_names_hash_bucket_size must be at least 512 for long domains.')
        owned.unlink(missing_ok=True)
    else:
        write(owned, NGINX_HASH_SETTINGS)


def set_site(text):
    previous = SITE.read_text() if SITE.exists() else None
    had_link = ENABLED.exists() or ENABLED.is_symlink()
    hash_path = nginx_hash_path()
    previous_hash = hash_path.read_text() if hash_path.exists() else None
    try:
        ensure_nginx_hash_settings()
        write(SITE, text)
        if not had_link:
            ENABLED.symlink_to(SITE)
        run(['nginx', '-t'])
        if run(['systemctl', 'is-active', '--quiet', 'nginx'], check=False).returncode:
            run(['systemctl', 'start', 'nginx'])
        else:
            run(['systemctl', 'reload', 'nginx'])
    except BaseException:
        if previous is None:
            SITE.unlink(missing_ok=True)
        else:
            write(SITE, previous)
        if not had_link:
            ENABLED.unlink(missing_ok=True)
        if previous_hash == NGINX_HASH_SETTINGS:
            write(hash_path, previous_hash)
        elif previous_hash is None and hash_path.exists() and hash_path.read_text() == NGINX_HASH_SETTINGS:
            hash_path.unlink()
        raise


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


def check_certificate_eligibility(profile):
    domain = profile['domain']
    if len(domain.split('.')) > 10 and not certificate_usable(profile['cert_name'], domain):
        raise ValueError(
            "Let's Encrypt supports at most 10 DNS labels (dot-separated parts). "
            "This hostname needs a matching certificate from another issuer before installation; "
            "NGINX supports the hostname, but changing NGINX or the challenge port cannot fix this CA restriction. "
            "A CDN also needs an edge certificate covering the exact hostname.")


def install(args):
    check_os()
    previous = load()
    if hasattr(args, '_profiles'):
        items = validate_profiles(args._profiles)
    elif not args.non_interactive:
        items = wizard_profiles(args, previous)
    else:
        items = [dict(p) for p in profile_list(previous)]
        index = getattr(args, '_profile_index', 0)
        updated = settings(args, items[index] if items else {})
        if items:
            items[index] = updated
        else:
            items = [updated]
        items = validate_profiles(items)
    for profile in items:
        check_certificate_eligibility(profile)
    s = {**items[0], 'profiles': items}
    target_certs = list(dict.fromkeys(p['cert_name'] for p in items))
    known_certs = owned_certificates(previous) if previous else []
    cf_ranges = None
    for p in items:
        retained = CERT_ROOT / 'mtproxy-web-retained' / (p['cert_name'] + '.conf')
        if p['cert_name'] not in known_certs and not retained.exists() and (CERT_ROOT / 'renewal' / (p['cert_name'] + '.conf')).exists():
            raise RuntimeError('An unmanaged certificate with this name already exists; refusing to replace it.')
        addresses = {item[4][0] for item in socket.getaddrinfo(p['domain'], 443, type=socket.SOCK_STREAM)}
        if not addresses or (not p['cdn'] and addresses != {p['public_ip']}):
            raise ValueError(f'Check DNS/CDN settings for {p["domain"]}.')
        if p['cdn_provider'] == 'cloudflare':
            if cf_ranges is None:
                cf_ranges = cloudflare_ranges()
            p['client_ip_header'] = 'CF-Connecting-IP'
        p['cloudflare_ranges'] = cf_ranges if p['cdn_provider'] == 'cloudflare' else p['trusted_proxy_cidrs']
    s.update(items[0])
    if not previous:
        if run(['id', '-u', USER], capture=True, check=False).returncode == 0:
            raise RuntimeError('Service account already exists and is not managed by this installer.')
        has_manager = owned_manager()
        for port in {80, BACKEND_PORT, API_PORT, *(p['origin_port'] for p in items)}:
            try:
                port_available(port)
            except OSError as e:
                if (port == 80 and has_manager and stock_nginx_only()
                        and run(['systemctl', 'is-active', '--quiet', 'nginx'], check=False).returncode == 0):
                    print('Reusing the retained default NGINX server for HTTP-01 SSL validation.')
                    continue
                raise RuntimeError(f'Port {port} is occupied. Use a clean/dedicated server.') from e
        for path in (SITE, ENABLED, CONFIG, UNIT, CLI, MANAGER, BIN):
            if has_manager and path in (CLI, MANAGER):
                continue
            if path.exists() or path.is_symlink():
                raise RuntimeError(f'Unmanaged path already exists: {path}')
        s.update(baseline=installed_packages(), created_user=False,
                 cert_names=target_certs, complete=False, enabled=True)
        save(s)
    else:
        s = {**previous, **s}
        s['cert_names'] = list(dict.fromkeys(known_certs + target_certs))
        if not previous.get('complete'):
            save(s)
    if previous:
        old_ports = {p.get('origin_port', 443) for p in profile_list(previous)}
        for port in {p['origin_port'] for p in items} - old_ports:
            port_available(port)
    print(f'Installing for {s["domain"]}; public HTTPS:443; origin HTTPS:{s["origin_port"]}; sponsor: {bool(s["ad_tag"])}', flush=True)
    # Keep a root-only recovery CLI even if certificate issuance later fails.
    install_manager()
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
    if args.action == 'reinstall' or not previous.get('complete') or not BIN.exists():
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
    install_domain_sites(s)
    run(['chown', '-R', f'{USER}:{USER}', str(DATA)])
    run(['chown', f'root:{USER}', str(ETC)])
    ETC.chmod(0o750)
    old_config = CONFIG.read_text() if CONFIG.exists() else None
    old_site = SITE.read_text() if SITE.exists() else None
    restored, created = [], []
    should_enable = args.action in ('install', 'reinstall') or previous.get('enabled', True)
    try:
        seen = set()
        for p in items:
            name = p['cert_name']
            if name in seen:
                continue
            seen.add(name)
            retained = CERT_ROOT / 'mtproxy-web-retained' / (name + '.conf')
            if retained.exists():
                renewal = CERT_ROOT / 'renewal' / (name + '.conf')
                if renewal.exists():
                    raise RuntimeError('Both retained and active renewal records exist; refusing to overwrite either.')
                renewal.parent.mkdir(parents=True, exist_ok=True)
                retained.replace(renewal)
                restored.append(name)
                if not any(retained.parent.iterdir()):
                    retained.parent.rmdir()
            certificate = CERT_ROOT / 'live' / name / 'fullchain.pem'
            existed = certificate.exists()
            if existed and certificate_usable(name, p['domain']):
                print(f'Reusing SSL: {p["domain"]}')
                continue
            old_domains = {q['domain'] for q in profile_list(previous)}
            if old_site and p['domain'] not in old_domains:
                challenge_site = old_site + '\n' + nginx_sites(
                    {'profiles': [q for q in items if q['domain'] not in old_domains]})
            else:
                challenge_site = nginx_sites(s)
            set_site(challenge_site)
            if not existed:
                created.append(name)
            command = ['certbot', 'certonly', '--non-interactive', '--agree-tos', '--webroot',
                       '-w', str(DATA / 'acme'), '--cert-name', name, '-d', p['domain']]
            command += ['--email', p['email']] if p['email'] else ['--register-unsafely-without-email']
            if existed:
                command.append('--force-renewal')
            run(command)
        write(CONFIG, telemt_config(s), 0o640)
        run(['chown', f'root:{USER}', str(CONFIG)])
        write(UNIT, SERVICE)
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'enable', '--now', 'mtproxy-web'])
        if previous:
            run(['systemctl', 'restart', 'mtproxy-web'])
        wait_backend()
        set_site(nginx_sites(s, tls=should_enable))
        if not should_enable:
            run(['systemctl', 'disable', '--now', 'mtproxy-web'])
        write(HOOK, '#!/bin/sh\nnginx -t && systemctl reload nginx\n', 0o755)
        run(['systemctl', 'enable', '--now', 'nginx', 'certbot.timer'])
        s['complete'] = True
        s['enabled'] = should_enable
        s['cloudflare_ranges'] = items[0]['cloudflare_ranges']
        save(s)
    except BaseException:
        if previous.get('complete') and old_config and old_site:
            write(CONFIG, old_config, 0o640)
            run(['chown', f'root:{USER}', str(CONFIG)])
            set_site(old_site)
            run(['systemctl', 'enable', '--now', 'mtproxy-web'] if previous.get('enabled', True)
                else ['systemctl', 'disable', '--now', 'mtproxy-web'], check=False)
            if previous.get('enabled', True):
                run(['systemctl', 'restart', 'mtproxy-web'], check=False)
            save(previous)
            for name in restored:
                if name not in known_certs:
                    retain_certificate(name)
            for name in created:
                if name not in known_certs and name not in restored:
                    delete_certificate(name, check=False)
        raise
    for old_cert in known_certs:
        if old_cert not in target_certs:
            if getattr(args, '_retain_removed_certificates', False):
                retain_certificate(old_cert)
                s['cert_names'].remove(old_cert)
            elif delete_certificate(old_cert, check=False):
                s['cert_names'].remove(old_cert)
    save(s)
    print('\nsinascorpion — Installed' + '\n'.join(link(p) for p in items))
    print('Management: mtproxy-web configure | status | link | uninstall')
    print('Open the management menu any time: sinascorpion-webproxy (or sudo sinascorpion-webproxy)')
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
    if not s.get('complete'):
        print('Installation incomplete. Select Install / reinstall to resume.')
        return
    print(f'Domain: {s["domain"]}\nTelemt: {TELEMT_VERSION}\nSponsor configured: {bool(s["ad_tag"])}')
    print(f'CDN: {s.get("cdn_provider", "none")}\nPublic port: 443\nOrigin port: {s.get("origin_port", 443)}')
    run(['systemctl', '--no-pager', '--full', 'status', 'mtproxy-web'], check=False)
    for index, p in enumerate(profile_list(s), 1):
        print(f'Profile {index}: {p["domain"]} / {p.get("cdn_provider", "none")} / origin {p.get("origin_port", 443)} / sponsor {bool(p.get("ad_tag"))}')
    if not s.get('enabled', True):
        print('Proxy disabled; settings and certificate retained.')
        return
    with urllib.request.urlopen(f'http://127.0.0.1:{API_PORT}/v1/runtime/web/status', timeout=5) as r:
        print(json.dumps(json.load(r), indent=2))


def certificate_usable(name, domain):
    live = CERT_ROOT / 'live' / name
    cert, key = live / 'fullchain.pem', live / 'privkey.pem'
    if not cert.exists() or not key.exists():
        return False
    # The locally retained managed certificate is the trust anchor here. Verify
    # enforces hostname and validity dates with a meaningful failure exit status.
    valid = run(['openssl', 'verify', '-trusted', str(cert), '-partial_chain',
                 '-verify_hostname', domain, str(cert)], capture=True, check=False)
    if valid.returncode:
        return False
    public = run(['openssl', 'x509', '-in', str(cert), '-pubkey', '-noout'], capture=True, check=False)
    private = run(['openssl', 'pkey', '-in', str(key), '-pubout'], capture=True, check=False)
    return public.returncode == private.returncode == 0 and public.stdout == private.stdout


def retain_certificate(name):
    renewal = CERT_ROOT / 'renewal' / (name + '.conf')
    if renewal.exists():
        destination = CERT_ROOT / 'mtproxy-web-retained' / renewal.name
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        renewal.replace(destination)


def delete_certificate(name, check=True):
    if not (CERT_ROOT / 'renewal' / (name + '.conf')).exists():
        return True
    if not shutil.which('certbot'):
        if check:
            raise RuntimeError('Certbot is missing; reinstall it before removing the managed certificate.')
        print(f'Certificate retained for later cleanup: {name}')
        return False
    result = run(['certbot', 'delete', '--non-interactive', '--cert-name', name], check=check)
    if result.returncode:
        print(f'Certificate retained for later cleanup: {name}')
    return result.returncode == 0


def set_enabled(enabled):
    s = load()
    if not s or not s.get('complete'):
        raise RuntimeError('Complete installation first')
    old_site = SITE.read_text()
    was_enabled = s.get('enabled', True)
    try:
        if enabled:
            run(['systemctl', 'enable', '--now', 'mtproxy-web'])
            wait_backend()
            set_site(nginx_sites(s, tls=True))
        else:
            # Retain only HTTP-01 so certificates can renew while the proxy is off.
            set_site(nginx_sites(s, tls=False))
            run(['systemctl', 'disable', '--now', 'mtproxy-web'])
        s['enabled'] = enabled
        save(s)
    except BaseException:
        set_site(old_site)
        run(['systemctl', 'enable', '--now', 'mtproxy-web'] if was_enabled
            else ['systemctl', 'disable', '--now', 'mtproxy-web'], check=False)
        raise
    print('Enabled' if enabled else 'Disabled')


def uninstall(args):
    s = load()
    if not s:
        if getattr(args, 'remove_manager', False):
            if args.yes or input('Remove the management command too? [y/N]: ').lower() == 'y':
                remove_manager()
                return True
        print('Nothing installed')
        return False
    if not args.yes and input('Delete this proxy and secret?').strip().lower() != 'y':
        return False
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
    hash_path = nginx_hash_path()
    if hash_path.exists() and hash_path.read_text() == NGINX_HASH_SETTINGS:
        hash_path.unlink()
    if shutil.which('nginx'):
        run(['nginx', '-t'])
        if run(['systemctl', 'is-active', '--quiet', 'nginx'], check=False).returncode == 0:
            run(['systemctl', 'reload', 'nginx'])
    for name in owned_certificates(s):
        if getattr(args, 'delete_certificate', False):
            delete_certificate(name)
        else:
            retain_certificate(name)
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
    if getattr(args, 'remove_manager', False):
        remove_manager()
    print('Removed. SSH, firewall and existing packages were preserved.')
    if not getattr(args, 'delete_certificate', False):
        print('Certificate/key retained for same-domain reinstall; renewal paused until reinstall.')
    if not getattr(args, 'remove_manager', False):
        print('Management menu retained: sinascorpion-webproxy')
    return True


def configured_args(action='configure'):
    return parser().parse_args([action, '--non-interactive'])


def change_domain():
    s = load()
    if not s:
        raise RuntimeError('Install first')
    index = select_profile(s)
    p = profile_list(s)[index]
    domain = normalize_domain(prompt('New domain', p['domain']))
    if domain == p['domain']:
        print('Domain unchanged')
        return
    args = configured_args()
    args._profile_index = index
    args.domain = domain
    install(args)


def change_secret():
    s = load()
    if not s:
        raise RuntimeError('Install first')
    args = configured_args()
    args._profile_index = select_profile(s)
    p = profile_list(s)[args._profile_index]
    args.secret = choose_secret(args, p, True)
    if args.secret == p['secret']:
        print('Secret unchanged')
        return
    print('Changing the secret invalidates existing users’ links.')
    if input('Apply new secret?').strip().lower() == 'y':
        install(args)


def select_profile(s):
    items = profile_list(s)
    if len(items) == 1:
        return 0
    for index, p in enumerate(items, 1):
        print(f'{index}) {p["domain"]} — {p.get("cdn_provider", "none")}')
    index = int(prompt('Profile number', '1')) - 1
    if not 0 <= index < len(items):
        raise ValueError('Invalid profile number')
    return index


def manage_profiles():
    while True:
        s = load()
        if not s or not s.get('complete'):
            raise RuntimeError('Install first')
        items = [dict(p) for p in profile_list(s)]
        for index, p in enumerate(items, 1):
            print(f'{index}) {p["domain"]} — {p.get("cdn_provider", "none")}')
        print('1) Add')
        choice = input('Select: ').strip()
        if choice == '0':
            return
        if choice == '4':
            print('\n'.join(link(p) for p in items))
            continue
        args = configured_args()
        if choice == '1':
            interactive = parser().parse_args(['configure'])
            interactive._connection_defaults = items
            items.extend(wizard_profiles(interactive, {}))
        elif choice == '2':
            index = select_profile(s)
            items[index] = settings(parser().parse_args(['configure']), items[index])
        elif choice == '3':
            if len(items) == 1:
                raise ValueError('Use Uninstall to remove the last profile.')
            index = select_profile(s)
            if prompt('Remove this profile?', 'n').lower() != 'y':
                continue
            items.pop(index)
        else:
            print('Invalid choice')
            continue
        args._profiles = items
        install(args)


def remove_domain():
    s = load()
    if not s:
        print('Nothing installed')
        return
    items = profile_list(s)
    domains = list(dict.fromkeys(p['domain'] for p in items))
    print('\nInstalled domains:')
    for index, domain in enumerate(domains, 1):
        group = [p for p in items if p['domain'] == domain]
        secrets_count = len({p['secret'] for p in group})
        tags_count = len({p['ad_tag'] for p in group if p.get('ad_tag')})
        print(f'{index}) {domain} — {secrets_count} secret(s), {tags_count} sponsor tag(s)')
    print('0) Back')
    selected = input('Select: ').strip()
    if selected == '0':
        return
    index = int(selected) - 1
    if not 0 <= index < len(domains):
        raise ValueError('Invalid domain number')
    domain = domains[index]
    remaining = [dict(p) for p in items if p['domain'] != domain]
    if not remaining:
        print('This is the last domain. Proxy services will be removed; packages, SSL and the management command will be kept.')
    if prompt(f'Remove {domain} and its secrets/tags? y/n', 'n').lower() != 'y':
        return
    if remaining:
        args = configured_args()
        args._profiles = remaining
        args._retain_removed_certificates = True
        install(args)
    else:
        uninstall(argparse.Namespace(yes=True, purge_dependencies=False, remove_manager=False,
                                     delete_certificate=False))
    print(f'Domain removed: {domain}')


def uninstall_menu():
    while True:
        print('\nUninstall\n1) Remove the entire proxy\n2) Remove one domain and its secrets/tags\n0) Back')
        choice = input('Select: ').strip()
        if choice == '0':
            return False
        if choice == '2':
            remove_domain()
            return False
        if choice == '1':
            purge = prompt('Remove installer-added packages?', 'y').lower() == 'y'
            remove = prompt('Remove management command too?', 'n').lower() == 'y'
            delete_cert = prompt('Delete SSL certificate too?', 'n').lower() == 'y'
            return bool(uninstall(argparse.Namespace(yes=False, purge_dependencies=purge, remove_manager=remove,
                                                     delete_certificate=delete_cert)) and remove)
        print('Invalid choice')


def menu():
    while True:
        s = load()
        state = ('not installed' if not s else 'incomplete' if not s.get('complete')
                 else 'enabled' if s.get('enabled', True) else 'disabled')
        print(f'\nTelegram Web Proxy Wizard — {state}')
        print('1) Install / reinstall')
        print('2) Configure')
        print('3) Change domain')
        print('4) Change secret')
        print('5) Disable')
        print('6) Enable')
        print('7) Status')
        print('8) Show link')
        print('9) Uninstall')
        print('10) Domains / secrets / tags')
        print('0) Exit')
        choice = input('Select: ').strip()
        if choice == '0':
            return
        try:
            if choice == '1':
                install(parser().parse_args(['reinstall' if s else 'install']))
            elif choice == '2':
                if not s:
                    raise RuntimeError('Install first')
                install(parser().parse_args(['configure']))
            elif choice == '3':
                change_domain()
            elif choice == '4':
                change_secret()
            elif choice == '5':
                set_enabled(False)
            elif choice == '6':
                set_enabled(True)
            elif choice == '7':
                status()
            elif choice == '8':
                if not s:
                    raise RuntimeError('Install first')
                print('\n'.join(link(p) for p in profile_list(s)))
            elif choice == '9':
                if uninstall_menu():
                    return
            elif choice == '10':
                manage_profiles()
            else:
                print('Invalid choice')
        except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as e:
            print(f'ERROR: {e}')


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version', action='version', version=VERSION)
    sub = p.add_subparsers(dest='action')
    p.set_defaults(action='menu')
    sub.add_parser('menu')
    for action in ('install', 'configure', 'reinstall'):
        s = sub.add_parser(action)
        s.add_argument('--non-interactive', action='store_true')
        s.add_argument('--domain')
        s.add_argument('--email')
        s.add_argument('--ad-tag', help='32 hex from @MTProxybot; - removes existing sponsor tag')
        s.add_argument('--secret', help='Existing WEB secret: raw 32 hex or dd + 32 hex; omit to generate/keep')
        s.add_argument('--public-ip', help='Origin public IPv4; defaults to automatic detection')
        s.add_argument('--cdn', action=argparse.BooleanOptionalAction, default=None)
        s.add_argument('--cdn-provider', choices=['none', 'cloudflare', 'other'], help='Provider-neutral CDN mode; Cloudflare can populate trusted IP ranges automatically')
        s.add_argument('--origin-port', type=int, help='Origin HTTPS listen port; public Telegram WEB endpoint remains 443')
        s.add_argument('--trusted-proxy-cidr', action='append', help='Official trusted CIDR for other CDN providers; repeat for multiple ranges')
        s.add_argument('--client-ip-header', help='Client-IP header set/overwritten by the trusted CDN; optional with other providers')
    sub.add_parser('status')
    sub.add_parser('link')
    sub.add_parser('enable')
    sub.add_parser('disable')
    sub.add_parser('change-domain')
    sub.add_parser('change-secret')
    sub.add_parser('profiles')
    u = sub.add_parser('uninstall')
    u.add_argument('--yes', action='store_true')
    u.add_argument('--purge-dependencies', action='store_true', help='Also purge packages added by this installer; keep all baseline packages')
    u.add_argument('--remove-manager', action='store_true', help='Also remove both management commands')
    u.add_argument('--delete-certificate', action='store_true', help='Delete the certificate/key instead of retaining them for reinstall')
    return p


def main():
    args = parser().parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run: sudo sinascorpion-webproxy')
    import fcntl
    with open('/run/lock/mtproxy-web.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another mtproxy-web operation is running')
        try:
            if args.action == 'menu':
                menu()
            elif args.action in ('install', 'configure', 'reinstall'):
                if args.action == 'configure' and not STATE.exists():
                    raise RuntimeError('Install first')
                install(args)
            elif args.action == 'status':
                status()
            elif args.action in ('enable', 'disable'):
                set_enabled(args.action == 'enable')
            elif args.action == 'change-domain':
                change_domain()
            elif args.action == 'change-secret':
                change_secret()
            elif args.action == 'profiles':
                manage_profiles()
            elif args.action == 'link':
                state = load()
                if not state:
                    raise RuntimeError('Not installed')
                print('\n'.join(link(p) for p in profile_list(state)))
            else:
                uninstall(args)
        except (EOFError, KeyboardInterrupt):
            print('\nClosed')
            return 0
        except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as e:
            print(f'ERROR: {e}\nIf partially installed, fix DNS/ports then rerun, or run mtproxy-web uninstall --purge-dependencies.', file=sys.stderr)
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
