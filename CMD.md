# Attendee local service

Run these commands from the Attendee app directory:

```zsh
cd /Users/vivek/Documents/Codehub/POC/attendee/attendee
```

The existing `.env` contains generated secrets. Do not run `init_env.py` again.
The Docker image contains the app code, so rebuild after changing the source.

## Start

```zsh
docker compose -f dev.docker-compose.yaml up -d --build
docker compose -f dev.docker-compose.yaml ps
```

On a new database, initialize it once:

```zsh
docker compose -f dev.docker-compose.yaml exec attendee-app-local python manage.py migrate --noinput
```

Open http://localhost:8000. View startup errors with:

```zsh
docker compose -f dev.docker-compose.yaml logs -f attendee-app-local
```

## Confirm your email in local development

Attendee prints sign-up confirmation emails in the app logs. It does not send them to your inbox. After signing up or requesting another confirmation email, run:

```zsh
docker compose -f dev.docker-compose.yaml logs --tail 100 attendee-app-local
```

Open the `http://localhost:8000/accounts/confirm-email/.../` link shown in the logs.

## Stop

This stops and removes the containers and network. The Postgres and Redis data volumes stay intact.

```zsh
docker compose -f dev.docker-compose.yaml down
```

## Remove everything created by this Compose project

This deletes its containers, network, database and Redis volumes, and images. API keys, accounts, and bot data in the local database will be lost. The source code and `.env` remain.

```zsh
docker compose -f dev.docker-compose.yaml down --volumes --rmi all --remove-orphans
```

## Meeting Console frontend

Start the FastAPI backend on port 8010, then in another terminal:

```zsh
cd /Users/vivek/Documents/Codehub/POC/attendee/frontend
bun install
bun run dev
```

Open http://127.0.0.1:3000. The backend URL and API key come from `frontend/.env`. Stop the frontend with `Ctrl+C`. For a production bundle, run `bun run build`.

Use `/calendar` to see upcoming bot joins, `/meetings` for the searchable list, and `/meetings/<meeting-id>` for the live transcript and completed MOM. The calendar refreshes every 30 seconds while open. MOM emails use the studio's visual theme.

## Automatic Teams calendar joins

See [backend/TEAMS_CALENDAR.md](backend/TEAMS_CALENDAR.md) to register the Microsoft Entra app, grant calendar permission, and set `backend/.env`. Once the migration is approved and applied, start the backend normally. Invite `MOM@tcgdigital.com` to a scheduled Teams meeting; the bot will be scheduled from its calendar event. For an unscheduled live call, copy the Teams meeting link into the Meeting Console.
