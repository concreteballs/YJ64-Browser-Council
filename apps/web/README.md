# Browser Council web client

React + TypeScript + Vite PWA shell. This is an interface foundation, not yet a
connected chat product.

## Local development

```sh
cd apps/web
npm install
npm run dev
```

## Current behavior

- Responsive desktop/mobile navigation and Council/individual-chat mode switch.
- Local-only draft messages to exercise the composer.
- API liveness indicator reads `/api/v1/health/live`.
- Installable PWA manifest and basic offline shell fallback.

No model provider, authentication, server persistence, attachments or research
tools are connected. The UI labels local drafts and unconnected providers
explicitly; it must not imply that an AI response has been generated.
