# Dreame app API — what the APK gave up, and where it stopped

**Written 2026-08-27 at a restart.** The analysis lived in a session scratchpad that does
not survive; everything durable is here. The APK itself is at
`C:\Users\CKing\Downloads\Dreamehome_2.6.3.0_APKPure.xapk` (179 MB) and everything below
is re-derivable from it.

## ⭐ THE FINDING THAT MATTERS, AND IT NEEDED NO API AT ALL

**The HA model string IS the document code.**

    core.device_registry -> Robin -> model: dreame.vacuum.r2469a
    corpus               -> manuals/robot/r2469a-en-fi-da-ms-*.pdf
    guide library        -> l10s_gen2 provenance = R2469X-Dreame_L10s_Ultra_Gen_2

So `dreame.vacuum.<rcode>` gives **HA model -> R-code -> document** directly. Chris went
after the APK expecting to find a code->URL template; the device registry already had the
link. Anything the API adds is on top of a chain that already works offline.

## What the APK is

`Dreamehome_2.6.3.0_APKPure.xapk` unpacks to `com.dreame.smartlife.apk` (70 MB) plus
`config.arm64_v8a.apk` (109 MB). It is a **Flutter** app, not React Native - so there is
no JS bundle to read. Dart string constants live in
`config.arm64_v8a.apk -> lib/arm64-v8a/libapp.so` (21 MB), which is where every finding
below came from via plain byte-regex.

⚠ `assets/nedata.db` (29 MB) is NOT SQLite - the header is high-entropy, so it is
encrypted or packed. The runtime host configuration probably lives in it, which is very
likely why the base URL could not be found by string search.

## Endpoints (real, from libapp.so)

    /dreame-product/public/smarthomeManual/list        <- the manual list
    /dreame-product/public/faqs/pdf
    /dreame-product/public/faqs/product
    /dreame-product/public/products/
    /dreame-product/public/v1/productCategory/by-models
    /dreame-product/public/v1/productCategory/checkModel
    /dreame-product/public/v1/productCategory/by-pids-with-model
    /dreame-third-proxy/thirdProxy/queryDeviceMaintenanceRecords

Fifteen microservice prefixes exist: `dreame-auth, -cms, -log, -mall, -message-push,
-messaging, -mqtt-log, -product, -smarthome, -store, -system, -third-proxy, -third-video,
-user, -user-iot`.

⚠ MOST `/path/like/this` STRINGS IN libapp.so ARE DART SOURCE FILENAMES, not endpoints.
A naive grep returns 400 "paths" of which ~390 are `*_widget.dart` and friends. Filter
anything containing `.dart`, `_widget`, `_state`, `_page`, `_model` before reading the
list as API surface.

## Hosts (30 found; the ones that resolve)

    us.iot.dreame.tech      47.251.9.249    live, HTTPS on :8080, nginx
    cn.iot.dreame.tech      101.34.72.62    live, HTTPS on :8080
    app.dreame.tech         18.193.185.114  live, nginx
    cn-cms.dreame.tech      43.145.6.65
    oss.iot.dreame.tech     (IPv6)          Alibaba OSS bucket - 403 AccessDenied
    global.dreametech.com   23.227.38.74    the Shopify site already scraped
    iot.dreame.tech                         DOES NOT RESOLVE - not a real host

Chris's own config entry gives the region: `10000.mt.us.iot.dreame.tech:19973`,
`country: us`, `account_type: dreame`.

## WHERE IT STOPPED, AND A FALSE LEAD TO NOT REPEAT

The endpoint paths are right and the hosts are right, but **the base URL was never
found**. `<host>:8080/dreame-product/...` returns an nginx 404 on both US and CN.

⚠ `/api/` IS A CATCH-ALL. `POST/GET /api/dreame-product/public/products/` returns an
application-layer JSON error rather than nginx HTML:

    {"msg":"系统未知异常[HttpStatus]:404","code":10000,"success":false}

That looked like proof the gateway routes `/api/<service>/`. It is not:
`/api/this-is-not-a-real-service/xyz` returns the IDENTICAL body. Do not spend time on
it again. ~45 requests were made against their servers before this was checked; check the
nonsense-path control FIRST next time.

## Traffic capture: what will and will not work

* **Full decryption will NOT work on an unrooted phone.** The HTTP stack is Dart-level
  (`dio` x25, `IOHttpClientAdapter`), and Flutter reads `/system/etc/security/cacerts`,
  never the user CA store where a proxy certificate lands. Android's
  `network_security_config` does not govern Dart HTTP either. mitmproxy + install-the-cert
  gets nothing without root, Frida, or repackaging.
* **There is NO pinning** - `CertificatePinner` 0, `badCertificateCallback` 0,
  `certificate_pinning` 0. Only the Flutter CA problem stands in the way.
* **Decryption is not needed.** The paths are already known; only the HOST is missing, and
  hostnames are in the clear in TLS SNI and DNS.

IN FLIGHT AT THE RESTART: Chris was starting Wireshark. Plan agreed:

    filter:  dns.qry.name contains "dreame" or
             tls.handshake.extensions_server_name contains "dreame"

    1. capture on the interface the PHONE's traffic crosses (hotspot adapter)
    2. FORCE-STOP the app first - a warm connection means no new handshake to see
    3. open app -> robot -> User Manual
    4. read the Server Name column

Looking for a host NOT already in the list above. If it is `global.dreametech.com` or
`cdn.shopify.com`, the app serves the same Shopify PDFs already scraped and the whole
line is moot - a cheap, useful negative. If it is only `oss.iot.dreame.tech`, the manual
comes straight from object storage and the interesting part is the OBJECT KEY, which SNI
will not reveal.

## ⚠ Security note

`Z:\.storage\core.config_entries` holds a live JWT `auth_key` for the Dreame account, and
the app writes an `authcode` plus session host into
`Android/data/com.dreame.smartlife/files/AndroidJNI/*.log` on world-readable storage. A
copy of one such log was pulled during analysis and has been deleted. Do not send that
credential anywhere; none of the endpoints above need it - they are all namespaced
`public`.

## Why this may not be worth resuming

The R-code link at the top already gives HA model -> document with no network call. The
API is only worth chasing for the LANGUAGE EDITIONS the corpus lacks - principally
Japanese, where only ~7 robot machines carry any kana at all. That is a real prize, but it
is the only one left on this line.

---

# ✅ SOLVED, 2026-08-27 — the working pipeline

The section above records where it stopped. It no longer stops there. A Wireshark SNI
capture supplied the one missing fact: **the API is on a non-standard port.**

## The pipeline

    LOOKUP  (needs the account token)
      GET https://us.iot.dreame.tech:13267/dreame-product/public/faqs/pdf
          ?model=dreame.vacuum.r2469a&lang=en
      headers: Authorization: Bearer <jwt>   (Dreame-Auth: <jwt> also accepted)
      -> {"code":0,"success":true,"data":"https://oss.iot.dreame.tech/pub/faq/..."}

    FETCH   (NO auth at all)
      GET that URL with a bare User-Agent
      -> HTTP 200, application/pdf, %PDF-1.4

**The token is only needed for the LOOKUP. The PDFs are public**, on an Alibaba OSS
bucket with the model in the path:

    https://oss.iot.dreame.tech/pub/faq/000000/ali_dreame/{model}/{hash}{ts}.pdf

⚠ PORT 13267, NOT 443. Nothing else answers. 443/80/8443 time out; 8080 is a different
vhost that returns nginx 404 for every path and wasted an hour. The port came from the
TCP SYN in the capture - `45738 -> 13267 [SYN]`.

⚠ `lang` IS REQUIRED. Without it: `{"code":10005,"msg":"缺少必要的请求参数: lang"}`.

## Other endpoints that work

    /dreame-product/public/v1/productCategory/checkModel?model=X&lang=en
        -> productId, categoryPath, displayName, images, firmware type
    /dreame-product/public/v1/productCategory?lang=en
        -> the OFFICIAL TAXONOMY: 26 robot-vacuum series (productList comes back EMPTY)
    /dreame-product/public/products/?lang=en&tenantId=000000&size=500&page=0
        -> paginated catalogue, 399 products (Spring Data Page shape)
    /dreame-product/public/faqs/product?model=X&lang=en   -> FAQ text, not manuals

⚠ `smarthomeManual/list` IS NOT MANUALS. Despite the name it returns Alexa / Google Home
linking cards. The manual endpoint is `faqs/pdf`.

## Result

**114 of 114** models that had no manual in the corpus returned a URL. 112 distinct PDFs.
Whole series recovered that the corpus never had: F21 (7/7), X60 (10/10), Aqua10 (11/11),
Aqua20, D15, D40, M1, C9, C20, C30, E20, F9.

Artifacts in `derived/`:
    dreame_api_catalogue.json     399 products (US tenant)
    dreame_api_categories.json    the official 26-series taxonomy
    dreame_api_series_map.json    series -> models, with held/new flags
    dreame_api_new_manuals.json   the 114 model -> URL results
    api_fetch_manifest.json       what was downloaded

## Scope limits, measured

* **`tenantId` IS A NO-OP.** `000000`, `000001`, `100000`, `000002` all return the
  identical 399. The app only ever sends `000000`.
* **Region = HOST + ACCOUNT, not a parameter.** `cn.iot.dreame.tech:13267` returns
  **HTTP 401** with the US token. The app's "Countries and Regions" screen is phone
  dialling codes for account registration, not a catalogue switch. Reaching the CN
  catalogue needs an account registered there.
* **`lang` does not select a language edition.** `en`, `ja`, `de`, `fr`, `ko`, `es`, `it`
  all return the SAME multilingual master; only `zh` differs. So Japanese is not
  separately addressable - it is either inside the master or absent.
* Tasshack lists 587 dreame models against this catalogue's 331; the 283 missing are
  most likely the CN catalogue.

## What this replaces

The corpus was built by scraping 407 Shopify product pages and reconstructing each
document's identity by inference - reg codes, cover names, printed-name joins, the whole
apparatus in STATE-dreame-manual-corpus.md. This returns documents **already keyed to the
model that requested them**. The hunting list is obsolete for `dreame.vacuum.*`.
