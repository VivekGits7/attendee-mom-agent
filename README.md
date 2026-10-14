# Attendee MOM Agent

This project sends an Attendee bot into Google Meet or Microsoft Teams meetings, stores the transcript, and produces concise meeting minutes with outcomes and an email delivery result.

| Folder | Purpose |
| --- | --- |
| `attendee/` | Self-hosted Attendee meeting bot platform |
| `backend/` | FastAPI meeting API, webhooks, transcript storage, MOM generation, and email |
| `frontend/` | Bun and React console for creating and browsing meetings |

## Frontend

Start Attendee and the FastAPI backend, then run:

```bash
cd frontend
bun install
bun run dev
```

Open <http://127.0.0.1:3000>. The frontend reads the backend URL and API key from `frontend/.env`, see `frontend/.env.example`.

- `/` creates a meeting and lists your latest meetings, click one to see its transcript.
- `/meetings` lists saved meetings with search, filters, sorting, and pagination.
- `/meetings/:meetingId` follows the transcript and shows the completed MOM, email result, and bot controls.

The backend exposes `GET /api/meetings` for the list and `GET /api/meetings/{meeting_id}` for the transcript and MOM. Both require the `X-API-Key` header. See [frontend/README.md](frontend/README.md) for frontend configuration and [CMD.md](CMD.md) for local Attendee service commands.

The `attendee/` source is based on the open source Attendee project and retains its upstream license in that folder.
