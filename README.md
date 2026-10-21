# Telegram Web Proxy Wizard

[فارسی](README.fa.md) · Maintained by **sinascorpion**

Easy Telegram WEB proxy setup with automatic SSL, multiple domains and secrets,
CDN support, optional sponsor tags and a management menu.
Each domain serves a lightweight website with its own stable name, colors and articles.

## Install

Use a dedicated Ubuntu server (Ubuntu 24.04 is recommended). Point your domain
to the server and allow ports **80** and **443**. Use a Telegram client that
supports `tg://webproxy`. Automatic SSL uses Let's Encrypt, which accepts up to
10 dot-separated hostname parts. Deeper hostnames require a matching certificate
from another issuer; a CDN also needs an edge certificate covering that hostname.

```bash
curl -fsSLo /tmp/telegram-web-proxy-install.sh https://raw.githubusercontent.com/sinascorpion/telegram-web-proxy/main/install.sh && sudo bash /tmp/telegram-web-proxy-install.sh
```

Select **1 — Install / reinstall**. Enter your domains, secrets and optional
sponsor tags, then choose the CDN and origin HTTPS port for each domain.
Press Enter at a secret prompt to generate one or keep the existing value.
Existing raw 32-hex or `dd`-prefixed WEB secrets are accepted.

## Multiple secrets and domains

Run several domains and secrets on the same server/IP, using different CDN
providers and sponsor tags. Multiple secrets on one domain are supported too.

During setup, choose whether to add another domain. Then enter the secrets and
tags in the same order: first domain → first secret → first tag. You can also
share one secret or tag across the domains, or start with one profile and add
more later.

Open **10 — Domains / secrets / tags** in the management menu to add, edit or
remove profiles and display their links.

## Management

```bash
sudo sinascorpion-webproxy
```

The menu offers reinstall, configuration, domain/secret changes, enable/disable,
status, links, profile management and uninstall. To update an older installation,
rerun the install command and select **1**.
Under **9 — Uninstall**, remove the entire proxy or select one domain and all its
associated secrets/tags. Other domains remain configured; SSL is retained for reuse.

Valid SSL is reused on the same server/domain, including after a secret change.
Uninstall keeps certificates by default; choose certificate deletion for a full
cleanup. Keep the same domain and secret when restoring existing client links.
Reinstall recognizes the retained default NGINX; SSL validation keeps it running.

## CDN and sponsor tags

Choose `none`, `cloudflare` or `other`. For other providers, enter trusted
client-IP ranges/header only if needed. Set verified origin TLS and allow
WebSockets, long requests and uncached proxy traffic.

Public connections use **443**. Other origin HTTPS ports, such as **2053, 2083
or 2096**, require your CDN to map public 443 to that origin port. DNS and CDN
account settings are configured by you.

Get an optional 32-hex sponsor tag from [@MTProxybot](https://t.me/MTProxybot).
A channel username alone is insufficient. Visible sponsorship requires a valid
registration and client support.

## Tests and license

Test details and platform coverage: [TESTING.md](TESTING.md).
License: [LICENSE](LICENSE) · Dependency notices: [NOTICE.md](NOTICE.md).

## Donate

<a href="https://nowpayments.io/donation?api_key=8b06749b-45a1-43aa-983f-986d9d6f38cf" target="_blank" rel="noreferrer noopener">
  <img src="https://nowpayments.io/images/embeds/donation-button-white.svg" alt="Cryptocurrency & Bitcoin donation button by NOWPayments">
</a>

Cloudflare deep hostnames: see the [SSL setup guide](CLOUDFLARE.md).

Select **8 — Links** to list every full `tg://webproxy` link. Links are shown
on separate lines in green on interactive terminals; `NO_COLOR=1` disables colors.
