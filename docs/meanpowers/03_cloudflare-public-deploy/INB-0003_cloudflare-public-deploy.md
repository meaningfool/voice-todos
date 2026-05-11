# Cloudflare Public Deploy

Deploy the existing hosted `voice-todos` app to Cloudflare on a subdomain of the
personal site as one same-origin public app. Keep the existing Worker +
Durable Object `/ws` runtime, serve the frontend from the same Cloudflare app
boundary, use Cloudflare-managed secrets, require a local Cloudflare smoke
before publish plus a public smoke after publish, and keep the first release
simple: one public environment, one human-triggered deploy command, no CI, no
staging, no Cloudflare Logfire parity.
