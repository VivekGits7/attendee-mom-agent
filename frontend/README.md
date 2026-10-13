# Meeting Console

A frontend for the backend meeting API. Create Meet or Teams bot sessions, browse saved meetings, follow transcripts, and read the finished minutes.

## Run locally

Start the backend on port 8010, then run:

```bash
cd frontend
bun install
bun run dev
```

Open <http://127.0.0.1:3000>. Paste the `INTERNAL_API_KEY` value from `backend/.env` into the page's **Backend API key** field. The key is held in memory for this tab and is never included in the JavaScript build or browser storage.

The Vite development proxy points at the backend address in `.env.development`. Change `BACKEND_PROXY_TARGET` there if the backend runs elsewhere. For a separately hosted static build, set `VITE_API_BASE_URL` to the backend URL ending in `/api`, allow the frontend origin in backend `CORS_ORIGINS`, and run `bun run build`. Keep the API key out of all `VITE_` variables, since those values are visible to browsers.

## Pages

- `/` creates a meeting and opens its live page. The original ID lookup and controls remain available below the form.
- `/meetings` lists every saved meeting with search, status and platform filters, sorting, and pagination. The list refreshes every 15 seconds while visible.
- `/meetings/:meetingId` displays bot state, transcript, email status, and the complete MOM. It refreshes every 5 seconds while the meeting is active or the minutes email is pending. Bot leave and MOM regeneration controls are available here.

The backend list endpoint is `GET /api/meetings`. It accepts `search`, `status`, `platform`, `sort_by`, `sort_order`, `limit`, and `offset`, and requires `X-API-Key`. Recent IDs on the create page are still kept in browser local storage for convenience. The API key stays only in React memory, so a tab reload asks for it again.
