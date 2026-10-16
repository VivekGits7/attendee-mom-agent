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

Copy `.env.example` to `.env` and fill it in. `BACKEND_PROXY_TARGET` is the backend address. Restart `bun run dev` after editing `.env`.

Keep `API_BASE_URL=/api` so requests go through the proxy. `bun run preview` uses the same proxy. Every page except `/login` needs a signed in user. The browser keeps the access token and sends it as `Authorization: Bearer` on each `/api` call, and a 401 sends the user back to `/login`.

## Pages

- `/login` signs in with a work email and password. There is no sign up page, accounts are created through the backend API, see [CMD.md](../CMD.md#create-a-login).
- `/account` shows the signed in user and changes the password, which signs out every other device.
- `/` creates a meeting and opens its live page. Below the form, a list of your latest meetings opens any one in the workspace with its transcript.
- `/meetings` lists every saved meeting with search, status and platform filters, sorting, and pagination. The list refreshes every 15 seconds while visible.
- `/meetings/:meetingId` displays bot state, transcript, email status, and the complete MOM. While the meeting is active or the minutes email is pending, new transcript lines and status changes stream in over a WebSocket, shown as `Live · real time`, with a light refresh every 30 seconds. If the socket cannot connect, the page shows `Live sync · every 5s` and refreshes every 5 seconds until the socket is back. Bot leave and MOM regeneration controls are available here.

The backend list endpoint is `GET /api/meetings`. It accepts `search`, `status`, `platform`, `sort_by`, `sort_order`, `limit`, and `offset`, and needs a signed in user's Bearer token or `X-API-Key`.
