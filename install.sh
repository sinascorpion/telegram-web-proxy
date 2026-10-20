#!/usr/bin/env bash
# Copyright (c) 2026 sinascorpion. SPDX-License-Identifier: GPL-3.0-or-later
set -Eeuo pipefail
umask 077
if [[ ${EUID} -ne 0 ]]; then
    echo 'Run as root: sudo bash install.sh' >&2
    exit 1
fi
command -v python3 >/dev/null || { echo 'Python 3.10+ is required (included in Ubuntu 22.04+).' >&2; exit 1; }
task_dir=$(mktemp -d)
trap 'rm -rf -- "$task_dir"' EXIT
repo='sinascorpion/telegram-web-proxy'
ref='main'
local_file=''
if [[ -n ${BASH_SOURCE[0]:-} && -f ${BASH_SOURCE[0]} ]]; then
    local_file="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/mtproxy_web.py"
fi
if [[ -f "$local_file" ]]; then
    cp -- "$local_file" "$task_dir/mtproxy_web.py"
else
    python3 - "$repo" "$ref" "$task_dir/mtproxy_web.py" <<'PY'
import sys, urllib.request
repo, ref, target = sys.argv[1:]
with urllib.request.urlopen(f'https://raw.githubusercontent.com/{repo}/{ref}/mtproxy_web.py', timeout=60) as r:
    data = r.read()
if not data.startswith(b'#!/usr/bin/env python3'):
    raise SystemExit('Invalid installer response')
with open(target, 'wb') as f:
    f.write(data)
PY
fi
# /dev/tty preserves the wizard when the bootstrap is invoked through curl | bash.
if [[ $# -eq 0 ]]; then
    if ! ( : </dev/tty ) 2>/dev/null; then
        echo 'Wizard requires a terminal. For automation use: install --non-interactive --domain DOMAIN --public-ip IP' >&2
        exit 1
    fi
    python3 "$task_dir/mtproxy_web.py" install </dev/tty
else
    python3 "$task_dir/mtproxy_web.py" "$@"
fi
