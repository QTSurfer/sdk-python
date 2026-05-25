# Changelog

All notable changes to `qtsurfer-sdk` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-05-25

### Added

- Initial release. `auth(apikey)` helper exchanges a long-lived API key for a short-lived JWT in one call and returns an `AuthenticatedSession`.
  - Reads `QTSURFER_APIKEY` from the environment when no apikey is passed.
  - Caches the JWT in memory by default; adopters can plug in a custom `TokenStore` (file, secret manager, desktop keychain).
  - `session.call(fn)` wraps any `qtsurfer-api-client` call with refresh-on-401: refresh once, retry once, surface the error otherwise.
  - `session.client` exposes the underlying `qtsurfer-api-client` `AuthenticatedClient` for direct typed calls; its `token` attribute is mutated on refresh so in-flight references see the latest JWT.
- `TokenStore` protocol (`load` / `save` / `clear`) with the default `InMemoryTokenStore`.
- `QTSAuthError` (subclass of `QTSError`) for missing-apikey and JWT-exchange failures.
- Depends on `qtsurfer-api-client >= 0.95.1` (provides the `auth` operation and `AuthTokenResponse` / `AuthTokenError` schemas).
