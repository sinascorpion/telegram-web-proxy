# Telegram Web Proxy Wizard

[فارسی](README.fa.md) · Maintained by **sinascorpion**

One-command interactive setup for Telegram WEB proxy: automatic HTTPS, certificate
renewal, provider-neutral CDN configuration, optional sponsor tags and clean uninstall.

```text
Telegram WEB client → public HTTPS :443 → optional CDN → origin HTTPS :PORT
                                                      → private proxy core → Telegram
```

## Install

Use a dedicated Ubuntu server (Ubuntu 24.04 is recommended), root access,
an A record for your domain, and reachable HTTP port 80 for certificate issuance
and renewal. Keep SSH open. Public Telegram WEB connections require HTTPS **443**.
Ubuntu 22.04 and arm64 are supported code paths; live testing uses Ubuntu 24.04 amd64.

```bash
curl -fsSLo /tmp/telegram-web-proxy-install.sh https://raw.githubusercontent.com/sinascorpion/telegram-web-proxy/main/install.sh && sudo bash /tmp/telegram-web-proxy-install.sh
```

The wizard asks for:

1. Domain/subdomain.
2. Optional certificate contact email.
3. Optional 32-hex sponsor tag.
4. Connection mode: `none` (direct), `cloudflare`, or `other` CDN.
5. Origin HTTPS port, default `443`.
6. For another CDN, optional trusted IP ranges and its client-IP header.

It generates a secret, downloads a checksum-verified core, creates a restricted
system service, obtains and renews a Let's Encrypt certificate, and prints a
`tg://webproxy` link. No server password or CDN API token is requested.

For the simplest first issuance, temporarily point DNS directly at the origin.
Issuance can also work behind a CDN if its HTTP-01 challenge path reaches the
origin unchanged, without cache, login, challenge or a redirect to unavailable TLS.
An incorrect origin AAAA record must be removed.

```bash
# Cloudflare with automatic trusted-range discovery
sudo bash /tmp/telegram-web-proxy-install.sh install --non-interactive \
  --domain proxy.example.com --cdn-provider cloudflare

# Another CDN, with the normal 443 origin port
sudo bash /tmp/telegram-web-proxy-install.sh install --non-interactive \
  --domain proxy.example.com --cdn-provider other
```

Optional flags: `--public-ip ORIGIN_IPV4` (otherwise detected using api.ipify.org),
`--email you@example.com`, `--ad-tag YOUR_32_HEX_TAG`, `--secret YOUR_RAW_32_HEX_SECRET`.
`--cdn` is shorthand for provider-neutral `other` mode; `--no-cdn` selects direct mode.

## CDN compatibility

This is not limited to Cloudflare. Other CDNs, including Fastly or ArvanCloud,
can be used **when the chosen service and plan meet the following contract**:

- Public HTTPS port 443 with a valid certificate, verified TLS to the origin.
- Original Host, TLS SNI, exact paths/query strings and authentication/carrier
  headers preserved. Do not rewrite the bridge or API endpoints.
- POST and DELETE requests, streamed bodies and long polls above 75 seconds.
- HTTP/2 for HTTPS lanes; WebSocket passthrough for WSS modes.
- Bypass cache, page optimization, CAPTCHA, JS challenges and access-login pages
  for the proxy hostname. Use one origin or whole-session affinity.
- HTTP-01 challenge files remain reachable on public HTTP port 80 for renewal.

Opening the right ports alone is not sufficient. A CDN's WebSocket feature can
require separate enablement or a qualifying plan. For example, consult
[Fastly WebSockets passthrough](https://www.fastly.com/documentation/guides/concepts/real-time-messaging/websockets-tunnel/).
Cloudflare has been live-tested; other providers are configurable, not certified
against every provider/plan/account configuration.

Cloudflare mode fetches its official network ranges and trusts `CF-Connecting-IP`
only from those peers. Use Full (strict) origin TLS and enable WebSockets.
Re-run configure to refresh the range list.

For other providers, no forwarded header is trusted by default. Traffic still
works, but per-IP accounting sees CDN edge IPs. To retain real client IPs, supply
the provider's official ranges and the header it reliably overwrites:

```bash
sudo mtproxy-web configure --non-interactive --cdn-provider other \
  --trusted-proxy-cidr PROVIDER_CIDR --client-ip-header PROVIDER_HEADER
```

Repeat `--trusted-proxy-cidr` for each range. Do not trust `/0`, an arbitrary
client header, or a header your provider does not sanitize. The wizard accepts
`-` to clear custom ranges. The installer does not edit your CDN account or DNS.

## HTTPS ports: client vs origin

**Telegram Desktop WEB proxies currently require public port 443.** Their links
omit a port; putting `:2083`, `:2096`, or `:2053` in the host does not enable a
different public client port. This restriction is enforced by the client:
[official proxy-data implementation](https://github.com/telegramdesktop/tdesktop/blob/dev/Telegram/SourceFiles/mtproto/mtproto_proxy_data.cpp)
and [WEB view checks](https://github.com/telegramdesktop/tdesktop/blob/dev/Telegram/SourceFiles/mtproto/web_proxy/web_proxy_webview.cpp).

The **origin** TLS listener can use another port:

```bash
sudo mtproxy-web configure --non-interactive --cdn-provider other --origin-port 2083
```

Then configure your CDN to send **public HTTPS 443 → origin HTTPS 2083**, with the
original hostname as Host and TLS SNI. Support for an origin-port override depends
on the provider and plan; merely changing the server's listening port does not
configure this mapping. The `tg://webproxy` link remains unchanged.

The same applies to 2053, 2087, 2096, 8443 or another available TLS origin port.
Cloudflare lists [443, 2053, 2083, 2087, 2096 and 8443 as HTTPS proxy ports](https://developers.cloudflare.com/fundamentals/reference/network-ports/),
but that list does not override Telegram's fixed public WEB port. Direct mode
therefore refuses an origin port other than 443. SSH, HTTP and internal service
ports are reserved. HTTP port 80 remains required for HTTP-01 renewal.

## Manage

```bash
sudo mtproxy-web configure
sudo mtproxy-web link
sudo mtproxy-web status
sudo certbot renew --dry-run --no-random-sleep-on-renew
sudo mtproxy-web uninstall --purge-dependencies
```

The wizard preserves the current secret and certificate. Enter `-` to remove
a sponsor tag. A domain change requires uninstall first. `--yes` skips the
uninstall prompt. Uninstall removes this proxy's certificate, settings, secret,
service and data. Dependency purge removes only packages added by the installer,
and refuses a removal that would also remove a pre-existing OS package. SSH and
firewall settings are preserved. Package logs/account metadata may remain.

An interrupted installation retains recovery state where possible: fix the cause
and rerun, or uninstall. A failed managed reconfiguration restores previous active
proxy/NGINX settings. Use a clean dedicated server; occupied required ports or
unmanaged project paths cause a first installation to stop.

## Sponsor channel

Obtain a **32-hex proxy tag** from [@MTProxybot](https://t.me/MTProxybot), then enter
it in the wizard. A channel username alone is not a tag. Follow the bot's current
registration flow; any required legacy-proxy validation must be completed
separately because this project exposes WEB transport only.

A tag enables Telegram middle proxies; direct-to-DC operation has no sponsored
channel support. Actual channel display depends on a valid bot registration and
Telegram client/server behavior. Without a supplied live tag, visible sponsorship
is not considered tested.

## Verification and scope

Use a Telegram build that supports `tg://webproxy`. Older `tg://proxy` clients are
not compatible. Negotiated carriers are `https`, `https-lanes`, `websocket`, and
`websocket-lanes`, with `https` as the compatibility fallback.

```bash
python3 -m unittest discover -s tests -v
sudo python3 tools/probe.py --state /etc/mtproxy-web/state.json --telegram
# Test an origin override without claiming a non-443 Telegram client link:
sudo python3 tools/probe.py --state /etc/mtproxy-web/state.json \
  --connect-ip ORIGIN_IPV4 --connect-port 2083 --telegram
```

The real-Telegram probe needs `python3-cryptography`. It checks public certificate
validation, the decoy, wrong-secret rejection, authenticated sessions, all four
carriers and matching `req_pq_multi`/`resPQ` nonces. It logs no proxy credentials,
does not log into Telegram, and sends no messages. See [TESTING.md](TESTING.md).

The core/API listen only on loopback. Secrets are stored in root-only state and
a service-readable config; access logs are disabled. This installer does not
change SSH, UFW, iptables, DNS or CDN account settings. Core version/checksums are
pinned. Review downloaded code before running it as root.
Dependency copyrights and licensing are documented in [NOTICE.md](NOTICE.md).

## Donate

<a href="https://nowpayments.io/donation?api_key=8b06749b-45a1-43aa-983f-986d9d6f38cf" target="_blank" rel="noreferrer noopener">
  <img src="https://nowpayments.io/images/embeds/donation-button-white.svg" alt="Cryptocurrency & Bitcoin donation button by NOWPayments">
</a>
