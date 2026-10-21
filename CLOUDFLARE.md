# Cloudflare and deep hostnames

Universal SSL covers the zone apex and one subdomain level. `*.example.com`
covers `proxy.example.com`, but not `a.b.example.com`. An API token does not
extend that coverage or remove a certificate authority's hostname limits.

For a deeper hostname:

1. Check **SSL/TLS → Edge Certificates** for an active certificate covering the
   exact hostname. Advanced Certificate Manager is a paid add-on; do not enable
   it until its cost and your hostname's eligibility have been checked.
2. For hostnames longer than 64 characters, Cloudflare documents ordering an
   advanced certificate through its API with `cloudflare_branding: true`.
   Issuance still depends on the selected CA and successful validation. This
   project has not live-tested issuance for extremely deep hostnames.
3. Separately obtain an origin certificate covering the same hostname under
   **SSL/TLS → Origin Server**. Origin CA is trusted by Cloudflare, not by
   ordinary clients connecting directly to the server.
4. Keep DNS proxying enabled for this route, use **Full (strict)**, and allow
   WebSockets. An origin certificate alone does not fix missing edge coverage.

The wizard currently automates Let's Encrypt HTTP-01, not Cloudflare certificate
ordering or Origin CA import. Do not retry automatic issuance for a hostname
with more than 10 labels unless a usable matching certificate is already present.
Use a shallower hostname for the automatic installation path.

`GET /zones/{zone_id}/ssl/certificate_packs` lists edge certificate packs; it does
not create certificates. An authenticated API request needs a separately supplied
token with appropriate permissions. Never put tokens, private keys, account/zone
identifiers, or personal hostnames in repository files or commit history.

References: [advanced certificates](https://developers.cloudflare.com/ssl/edge-certificates/advanced-certificate-manager/),
[Origin CA](https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/),
[certificate packs API](https://developers.cloudflare.com/api/resources/ssl/subresources/certificate_packs/methods/list/).

## فارسی

گواهی Universal فقط دامنهٔ اصلی و یک سطح ساب‌دامنه را پوشش می‌دهد.
برای نام چندسطحی، ابتدا در Edge Certificates وجود گواهی فعال برای نام کامل
را بررسی کن. ACM هزینه دارد و پذیرش نام توسط صادرکننده باید بررسی شود.
برای نام بیشتر از ۶۴ کاراکتر، طبق مستندات کلودفلیر درخواست گواهی پیشرفته
از API و گزینهٔ `cloudflare_branding: true` لازم است؛ صدور برای نام‌های بسیار
چندسطحی در این پروژه تست عملی نشده است.

گواهی Origin CA فقط ارتباط کلودفلیر تا سرور را پوشش می‌دهد؛ با ابر خاموش
جایگزین SSL معتبر برای کاربران نیست. پس از آماده‌شدن هر دو گواهی، ابر روشن،
حالت Full (strict) و WebSocket لازم است.

ویزارد فعلاً صدور خودکار کلودفلیر یا واردکردن Origin CA ندارد و از
Let’s Encrypt استفاده می‌کند. برای نصب خودکار از نام با عمق کمتر استفاده کن.
API فهرست گواهی‌ها محدودیت پلن یا صادرکننده را حذف نمی‌کند. توکن و اطلاعات
اختصاصی حساب را داخل سورس یا تاریخچهٔ گیت قرار نده.
