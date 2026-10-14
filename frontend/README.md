# Meeting Console

A frontend for the backend meeting API. Create Meet or Teams bot sessions, browse saved meetings, follow transcripts, and read the finished minutes.

## Run locally

Start the backend on port 8010, then run:

```bash
cd frontend
bun install
bun run dev
```

Open <http://127.0.0.1:3000>.

Copy `.env.example` to `.env` and fill it in. `BACKEND_PROXY_TARGET` is the backend address and `BACKEND_API_KEY` must match `INTERNAL_API_KEY` in `backend/.env`. The Vite proxy adds the key as `X-API-Key` on every `/api` call, so the page never asks for it and the key never reaches the browser. Restart `bun run dev` after editing `.env`.

Keep `API_BASE_URL=/api` so requests go through the proxy. `bun run preview` uses the same proxy. A separately hosted static build needs its own reverse proxy that adds the `X-API-Key` header. Never put the key in a `VITE_` variable, since those values ship to the browser.

## Pages

- `/` creates a meeting and opens its live page. Below the form, a list of your latest meetings opens any one in the workspace with its transcript.
- `/meetings` lists every saved meeting with search, status and platform filters, sorting, and pagination. The list refreshes every 15 seconds while visible.
- `/meetings/:meetingId` displays bot state, transcript, email status, and the complete MOM. It refreshes every 5 seconds while the meeting is active or the minutes email is pending. Bot leave and MOM regeneration controls are available here.

The backend list endpoint is `GET /api/meetings`. It accepts `search`, `status`, `platform`, `sort_by`, `sort_order`, `limit`, and `offset`, and requires `X-API-Key`.
