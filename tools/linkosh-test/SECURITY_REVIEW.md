# Linkosh v0.1.1 security and privacy review

Reviewed package: tools/linkosh-test/extension (the prepared, unmodified release).
ZIP SHA-256: 3768052d91b47c5072669e70a5c93157884e8b7db4c15038ffef20a68d3b4efe

## Assessment

No obvious credential-exfiltration, saved-post upload, or cloud embedding endpoint was found in the application paths examined. This is a limited source review, not a security certification. The current package has powerful browser-session access and privacy limitations. Use a dedicated Chrome profile signed into only the platform being tested; a LinkedIn-only build with reduced permissions would further reduce exposure.

The original extension package was not changed by this review. No real cookies were read and no authenticated platform requests were issued.

## Confirmed concerns

### Broad session access, and disabling a provider is not permission revocation

Evidence:
- extension/manifest.json:6-14 requests cookies and scripting plus host access to seven services.
- extension/ext/providers/env.js:30-34 reads cookie values through chrome.cookies.get.
- extension/ext/background-service.js:141-154 runs checkLogin for ALL registered providers, including disabled ones.
- extension/ext/background-service.js:189 permits a provider-specific sync without checking the disabled-provider preference; the UI hides disabled services but the handler is not a permission boundary.

A synthetic Node test using the shipped createBackgroundService code confirmed that a disabled Instagram provider still had its checkLogin method invoked when providerStatus was requested. The test used fake providers, not browser cookies.

Impact: disabling Instagram, X, etc. in Options prevents normal all-service syncing, but does not remove cookie-access capability or even all cookie-presence checks. The manifest's scope is substantially wider than needed for our LinkedIn test.

Mitigation: a dedicated Chrome profile with only LinkedIn signed in, and/or a separately identified LinkedIn-only build with just the LinkedIn host permission. This would still grant significant access to the LinkedIn session.

Chrome's permission documentation:
https://developer.chrome.com/docs/extensions/reference/api/cookies

### Persistent saved data and raw captures have no application-level encryption

Evidence:
- extension/workers/db.worker.js:17-35 opens an OPFS SQLite database and exports its bytes directly.
- extension/core/db/raw.js:23-35 retains response bodies verbatim when Capture mode is enabled.
- extension/core/sync.js:109-117 stores the complete captured page rather than only the normalized post fields.
- extension/pages/options/options.js:25-36 downloads the complete database.

Impact: a person or program with access to the browser-profile files or exported database can potentially read saved content and account identifiers. Operating-system/disk encryption may protect files separately; the extension supplies no independent encryption layer. The live database is in the Windows Chrome profile; saving an export into WSL creates another copy.

Raw capture stores response bodies and request URLs, not an explicit dump of HTTP request headers/cookies in the reviewed LinkedIn path. Response bodies may contain more account/content metadata than the visible item list.

Mitigation: retain Capture mode only for the limited investigation, keep exports private, and limit exported samples.

### Deleting visible items does not erase the raw archive

Evidence:
- extension/core/db/items.js:237-242 deletes only from saved_items.
- extension/pages/options/options.js:121-128 explicitly confirms that captured raw pages are kept.
- extension/pages/options/options.js:191-205 provides a separate Clear raw operation.

Impact: previously captured content remains after Delete all saved items. Individual Delete operations are soft deletions, retaining rows as well. Already downloaded exports and generated reports are separate copies and are unaffected by either button.

Mitigation: treat saved items, raw captures, and exported files as separate retention surfaces. Disabling Capture mode stops future collection but does not clear earlier captures. No deletion was performed during this review.

### Local processing still includes outbound asset requests

Evidence:
- extension/workers/embedders.js:9-18 and 26-42 fetch the embedding model from Hugging Face and use the bundled WASM runtime.
- extension/workers/embedders.js:65-69 passes post text into the local extractor; no cloud embedding call appears here.
- extension/pages/popup/app.js:129-143 loads thumbnail URLs directly into img elements.

Impact: model downloads and thumbnail viewing cause outbound network requests, exposing normal request metadata such as IP address and requested asset URL to the relevant hosts. I did not find a path uploading the saved-post text to the model host.

Mitigation: a stricter build could disable remote thumbnails and omit embeddings for an ingestion-only test.

## Other hardening opportunities, without a demonstrated exploit

- extension/core/rpc/transports.js:80-87 ignores the sender and dispatches messages by target/op.
- extension/core/rpc/server.js:4-9 looks up operations without an own-property allowlist.
- extension/manifest.json:20-24 exposes a blank debug.html to all sites and has no connect-src network allowlist.
- extension/pages/popup/app.js:143 and 175 does not explicitly allowlist thumbnail/link URL schemes.

These merit hardening before production use. They do not establish that arbitrary websites can export this extension's data: I found no onMessageExternal handler or window-message forwarding bridge, and debug.html is blank. The browser isolates extension origins. No browser exploit was reproduced.

## Positive observations

- The LinkedIn provider's observed request code uses fixed LinkedIn URLs and authenticated GET requests (extension/ext/providers/linkedin.js:38-59).
- No password-entry UI, cookie upload endpoint, or telemetry sender was identified in the application code examined.
- Current embedding provider selection resolves to the local provider regardless of old stored settings (extension/workers/embedders.js:81-86).
- Post text is passed as Preact text children, rather than injected as HTML (extension/pages/popup/app.js:175-179).
- Reviewed insert/search code binds SQL values rather than concatenating captured post text (extension/core/db/items.js:73-76, 188-215).
- No automatic update_url is declared in the unpacked manifest.
- The release checksum matched the published GitHub asset digest. This verifies consistency with that release; it does not prove the publisher, build, or dependencies are trustworthy.

## Scope and limits

Reviewed: manifest, first-party network/credential sinks, LinkedIn connector, provider environment, status/sync handling, RPC boundary, persistence/export/raw-retention paths, local embedding flow, and saved-item rendering. Other provider request paths were scanned and selectively read.

Validation: reproduced disabled-provider login probing with fake providers under Node in WSL. The prior export-inspector tests used synthetic databases and verified unchanged input bytes.

Not completed: live authenticated network capture, a browser exploit test, a full line-by-line review of all bundled dependencies, a WASM binary audit, dependency vulnerability analysis, or verification of build attestations/reproducible builds. Bundled components include Transformers.js, ONNX Runtime, SQLite WASM and Preact; their presence is a separate supply-chain dependency.

Platform account-policy risk also remains distinct from privacy/code risk because the connector uses private platform endpoints. Source review cannot guarantee that a platform accepts that activity.
