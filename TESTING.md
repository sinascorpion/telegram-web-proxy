# Verification

Platform: Ubuntu 24.04 amd64. Core: pinned 3.5.14 release with verified SHA-256.

## Automated checks

- Domain and configuration-injection rejection, secret/tag validation.
- Restoring raw/dd-prefixed WEB secrets keeps the exact link; Enter preserves an
  existing secret or generates one only on a new installation. Invalid interactive
  input retries without printing the supplied secret.
- Sponsor configuration selects middle-proxy routing.
- WEB and management listeners remain loopback-only.
- Public links and inner relay destination stay on 443 even with another origin port.
- Origin port validation, including reserved ports and direct-mode restrictions.
- Generic CDN selection never implicitly trusts Cloudflare headers.
- Custom client-IP trust requires both explicit CIDRs and a valid header; /0 is refused.
- Dependency uninstall refuses removal of pre-existing OS packages.
- Unix permission checks cover the executable under restrictive bootstrap umask.

## Live checks

Date: 2026-10-20. Ubuntu 24.04 amd64, approximately 1.5 GB RAM.

- A clean installation in generic `other` CDN mode succeeds under umask `077`,
  including automatic IPv4 discovery and production Let's Encrypt issuance.
- The public domain uses a Cloudflare edge. With no provider-specific forwarded
  header trusted, all four carriers return real Telegram `resPQ` responses with
  matching nonces, including from a separate external machine.
- Changing only the origin HTTPS listener to **2083** succeeds. NGINX configuration
  validation passes; external TLS/certificate validation and all four real-Telegram
  carrier probes pass against the origin's 2083 socket. The client link and inner
  relay destination remain on 443.
- The certificate-renewal timer is enabled; management and WEB backends remain
  on loopback. The interactive provider/port wizard is checked in an SSH terminal.
- Full dependency-purge uninstall succeeds. The installed package-name set returns
  exactly to the pre-test 690-package baseline; no managed paths or failed services
  remain. SSH stays available and IPv4/IPv6 firewall rules remain empty.

No CDN account was modified to map public 443 to origin 2083. The 2083 test verifies
the origin TLS listener, not such an account-level routing rule. Other origin ports
are covered by configuration/validation tests, not separate live deployments.

## Reproduce

```bash
python3 -m unittest discover -s tests -v
sudo python3 tools/probe.py --state /etc/mtproxy-web/state.json --telegram
sudo python3 tools/probe.py --state /etc/mtproxy-web/state.json \
  --connect-ip ORIGIN_IPV4 --connect-port 2083 --telegram
```

The probe validates certificates and a real Telegram nonce round-trip without
account login or messaging. Sponsor display requires a real bot tag and a client
acceptance check; no such display test is claimed. Other CDN providers/plans and
Ubuntu 22.04/arm64 are not covered by the Ubuntu amd64 live run.
