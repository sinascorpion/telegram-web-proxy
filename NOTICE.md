# sinascorpion — project and dependency notices

The installer, management commands and deployment probe in this repository are
maintained by **sinascorpion**. Copyright (c) 2026 sinascorpion.
This repository's installer and tests are GPL-3.0-or-later; see LICENSE.

## Proxy core dependency

The installer downloads the official, unmodified **Telemt 3.5.14** release
separately and verifies its pinned SHA-256 before use. No upstream proxy binary
or source code is vendored in this repository.

- Source revision: [9d5b896bb695c55e2905b82f276da84e45a0a2ec](https://github.com/telemt/telemt/tree/9d5b896bb695c55e2905b82f276da84e45a0a2ec).
- Dependency license: [TELEMT Public License](https://github.com/telemt/telemt/blob/9d5b896bb695c55e2905b82f276da84e45a0a2ec/LICENSE).

Telemt retains its own copyright and license; it is not covered by this
installer's GPL license. This is an independent sinascorpion project and is
not an official Telegram or Telemt product.

The deployment probe implements the public WEB framing and standard MTProto
handshake to verify a deployment. It creates no Telegram account and sends
no messages.
