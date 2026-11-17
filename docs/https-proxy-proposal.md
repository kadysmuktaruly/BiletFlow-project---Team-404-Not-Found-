# Proposal: HTTPS reverse proxy for the demo stack

**Status: proposed, not added.** The Report 6 plan asks to propose this before adding it.
Approve or change it in the PR, and a follow-up PR adds it.

## Why

SRS 7 asks for "sensitive information encrypted in transit". Today the demo runs plain HTTP
on two origins: the web app on `:3000` and the API on `:8000`. One HTTPS origin in front of
both would:

- encrypt every request, including passwords and tokens;
- let the refresh cookie be `Secure` and keep it same-origin (no CORS for the web app);
- match how a real deployment would look.

## Proposal

Add a **Caddy 2** service (`caddy:2.8-alpine`, official image) to `docker-compose.yml`
behind a Compose profile, so `docker compose up` is unchanged and
`docker compose --profile https up` turns it on.

```
https://localhost        → web:3000
https://localhost/api/*  → api:8000
```

```caddyfile
localhost {
    tls internal              # Caddy's own local CA; nothing leaves the machine
    encode gzip
    handle /api/* {
        reverse_proxy api:8000
    }
    handle {
        reverse_proxy web:3000
    }
    header Strict-Transport-Security "max-age=300"   # short: it's a demo
}
```

With the profile on: `PUBLIC_BASE_URL=https://localhost`,
`NEXT_PUBLIC_API_BASE_URL=https://localhost`, and the API marks the refresh cookie `Secure`
when `PUBLIC_BASE_URL` starts with `https://` (a small code change in the same PR).

## Trade-offs and open questions

- **Browsers warn** until Caddy's local CA is trusted (`docker compose exec caddy caddy
  trust`, once per laptop). Acceptable for the demo laptop; document it in the demo script.
- **The scanner on a phone** reaches the API by LAN IP, and phones won't trust Caddy's local
  CA without installing it. Options: (a) keep the scanner on plain HTTP over the LAN for the
  demo (recommended; it's a closed network), or (b) install the CA profile on the demo phones.
- **Alternatives considered:** nginx + mkcert (two tools instead of one, manual cert
  renewal); Traefik (more configuration than this needs). Caddy issues and renews the local
  certificate itself.
- No new library in the app; one new container image.

## Decision needed

1. Caddy behind an `https` profile, as above? 2. Scanner: (a) plain HTTP on the LAN or (b) CA
on phones?
