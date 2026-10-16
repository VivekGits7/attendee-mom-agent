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

Open <http://127.0.0.1:3000> and sign in. The frontend reads the backend URL from `frontend/.env`, see `frontend/.env.example`. Accounts are created through the backend API, see [CMD.md](CMD.md#create-a-login).

- `/` creates a meeting and lists your latest meetings, click one to see its transcript.
- `/meetings` lists saved meetings with search, filters, sorting, and pagination.
- `/meetings/:meetingId` follows the transcript and shows the completed MOM, email result, and bot controls.

The backend exposes `GET /api/meetings` for the list and `GET /api/meetings/{meeting_id}` for the transcript and MOM. Both need a signed in user's Bearer token or the `X-API-Key` header.

For a live transcript, open a WebSocket to `/api/ws/meetings/{meeting_id}/transcript` and send `{"token": "<access token>"}` as the first message within 10 seconds. The server answers with:

| Event | When | Client does |
| --- | --- | --- |
| `snapshot` | right after login, and again when the final transcript replaces the live one | replace every line with `data.utterances`, meeting details are in `data.meeting` |
| `utterance` | each time Attendee sends a line, sentence by sentence with closed captions | add `data`, or replace the line with the same `utterance_id` |
| `status` | status, bot state or email result changed | update the meeting, fetch the REST detail if you need the MOM |
| `ping` | every 25 seconds | nothing, the login is checked again at this point |
| `failed` | just before the server closes | show `message` |

Close codes are 4001 login missing or ended, 4002 bad meeting ID, 4003 server error, 4004 meeting not found. Live events stay inside one backend process, so run the backend with a single worker. See [frontend/README.md](frontend/README.md) for frontend configuration and [CMD.md](CMD.md) for local Attendee service commands.

The `attendee/` source is based on the open source Attendee project and retains its upstream license in that folder.
