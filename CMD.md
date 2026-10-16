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

## Deploy on the VM

`docker-compose.yml` at the repo root runs Attendee, the backend and the frontend together.

| Port | Service |
| --- | --- |
| 9901 | Meeting Console frontend, nginx adds the backend API key |
| 9902 | FastAPI backend |
| 9903 | Attendee dashboard and API |

Create the env files on the VM: the root `.env` from `.env.example`, `attendee/.env`, and `backend/.env`. Compose sets the internal Attendee and webhook URLs itself, so leave those two backend values as they are.

The backend stores its data on `doe-postgres`, the Postgres server already running on the VM. Set it up once with [Backend database](#backend-database), then run from the repo root:

```bash
docker compose up -d --build
docker compose ps
```

On a fresh Attendee database, open `http://<vm-ip>:9903`, sign up, and get the confirmation link from the logs:

```bash
docker compose logs attendee-app | grep confirm-email
```

Create an API key and copy the webhook secret into `ATTENDEE_API_KEY` and `ATTENDEE_WEBHOOK_SECRET` in `backend/.env`. Add the transcription credentials in the Attendee project settings, then reload the backend:

```bash
docker compose up -d --force-recreate mom-backend
```

For a full check of every service, see [HEALTHCHECK.md](HEALTHCHECK.md).

Check that the backend reaches Attendee over the internal network:

```bash
docker compose exec mom-backend printenv ATTENDEE_BASE_URL ATTENDEE_WEBHOOK_URL
docker compose exec mom-backend curl -s -o /dev/null -w "%{http_code}\n" http://attendee-app:8000/health/
```

## Backend database

In production the backend keeps its tables on `doe-postgres`, the Postgres 16 server the DOE agents already run on the VM. It is only reachable from Docker on the VM, as `doe-postgres:5432` on the `doe-net` network, so every command here runs on the VM. The backend gets its own `attendee-mom` database there, separate from the DOE data in `pguserdb`.

Make sure the root `.env` has `DB_NETWORK=doe-net`, the backend joins that network:

```bash
grep -q '^DB_NETWORK=' .env || echo "DB_NETWORK=doe-net" >> .env
```

Point `backend/.env` at the server. The old settings stay in `~/backend.env.old`, and the password prompt keeps it out of the shell history:

```bash
cp backend/.env ~/backend.env.old
sed -i -e 's|^POSTGRES_DB_HOST=.*|POSTGRES_DB_HOST=doe-postgres|' \
       -e 's|^POSTGRES_DB_PORT=.*|POSTGRES_DB_PORT=5432|' \
       -e 's|^POSTGRES_DB_NAME=.*|POSTGRES_DB_NAME=attendee-mom|' \
       -e 's|^POSTGRES_DB_USER=.*|POSTGRES_DB_USER=postgres|' backend/.env
read -rsp "doe-postgres password: " PW; echo
sed -i "s|^POSTGRES_DB_PASSWORD=.*|POSTGRES_DB_PASSWORD=$PW|" backend/.env; unset PW
grep '^POSTGRES_DB_' backend/.env | grep -v PASSWORD
```

Create the database and its tables inside the server, then recreate the backend so it joins `doe-net` and reads the new settings:

```bash
docker exec doe-postgres psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'attendee-mom'" | grep -q 1 \
  || docker exec doe-postgres psql -U postgres -c 'CREATE DATABASE "attendee-mom"'
docker exec -i doe-postgres psql -v ON_ERROR_STOP=1 -U postgres -d attendee-mom < backend/database/meeting.sql
docker exec doe-postgres psql -U postgres -d attendee-mom -c '\dt'
docker compose up -d --force-recreate --no-deps mom-backend
docker compose logs --tail 20 mom-backend
```

Later schema changes run the same way, `docker exec -i doe-postgres psql -v ON_ERROR_STOP=1 -U postgres -d attendee-mom < backend/database/migrations/<file>.sql`. Migration files are not committed, so copy the file to the VM first.

| Task | Command |
| --- | --- |
| Open the backend database | `docker exec -it doe-postgres psql -U postgres -d attendee-mom` |
| Back up | `docker exec doe-postgres pg_dump -U postgres -d attendee-mom -Fc > attendee-mom_$(date +%F).dump` |
| Restore | `docker exec -i doe-postgres pg_restore -U postgres -d attendee-mom --clean --if-exists --no-owner < attendee-mom_<date>.dump` |

## Shared Postgres server

The meeting backend no longer uses this server, it runs on `doe-postgres` now. The stack stays here for other projects.

`postgres/` holds a general Postgres 17 server that any project on the VM can use. The folder is self-contained, so you can also copy it elsewhere and run it from there, but run only one copy per VM.

| Item | Value |
| --- | --- |
| Container and host name | `postgres-server` |
| Docker network | `postgres-network` |
| Port inside Docker | `5432` |
| Port on the VM | `127.0.0.1:5433`, Langfuse already uses 5432 |
| Data volume | `postgres-server-data` |

Create `postgres/.env` with a strong admin password, then start the server from the repo root:

```bash
cp postgres/.env.example postgres/.env
sed -i "s|^POSTGRES_ADMIN_PASSWORD=.*|POSTGRES_ADMIN_PASSWORD=$(openssl rand -hex 24)|" postgres/.env
chmod 600 postgres/.env
docker compose -f postgres/docker-compose.yml up -d --build
docker compose -f postgres/docker-compose.yml ps
```

### Add a database for a project

`create-db` makes a database and a user that can only reach that database, then prints the connection settings. Use lowercase letters, digits and underscores in the name. Save the output, the password is shown only once:

```bash
docker exec postgres-server create-db my_project
```

A project running in Docker joins the network and connects to `postgres-server:5432`:

```yaml
services:
  app:
    networks:
      - default
      - postgres-network

networks:
  postgres-network:
    external: true
```

A project running directly on the VM connects to `127.0.0.1:5433` instead.

### Everyday commands

| Task | Command |
| --- | --- |
| List databases | `docker exec postgres-server sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "\l"'` |
| Open psql as admin | `docker exec -it postgres-server sh -c 'psql -U "$POSTGRES_USER" -d postgres'` |
| Open a project database | `docker exec -it postgres-server psql -U <name>_user -d <name>` |
| Stop | `docker compose -f postgres/docker-compose.yml stop` |
| Start | `docker compose -f postgres/docker-compose.yml start` |
| Logs | `docker compose -f postgres/docker-compose.yml logs -f` |
| Back up one database | `docker exec postgres-server sh -c 'pg_dump -U "$POSTGRES_USER" -d <name> -Fc' > <name>_$(date +%F).dump` |
| Restore one database | `docker exec -i postgres-server sh -c 'pg_restore -U "$POSTGRES_USER" -d <name> --clean --if-exists --no-owner --role=<name>_user' < <name>_<date>.dump` |
| Remove a project database | `docker exec postgres-server sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE <name>" -c "DROP ROLE <name>_user"'` |

To use a database client on your Mac, open a tunnel and connect to `127.0.0.1:5433` with a project user, or the admin login from `postgres/.env`:

```bash
ssh -N -L 5433:localhost:5433 tcg-mcp-server
```

Never run `docker compose -f postgres/docker-compose.yml down -v`, it deletes the databases of every project on the server.

## Manage the backend and frontend

Run these from the repo root. Add `--no-deps` so only the named service changes, otherwise `up` also starts Attendee, Postgres and Redis.

| Task | Backend | Frontend |
| --- | --- | --- |
| Stop, keep the container | `docker compose stop mom-backend` | `docker compose stop mom-frontend` |
| Start again | `docker compose start mom-backend` | `docker compose start mom-frontend` |
| Stop and remove | `docker compose down mom-backend` | `docker compose down mom-frontend` |
| Bring back | `docker compose up -d --no-deps mom-backend` | `docker compose up -d --no-deps mom-frontend` |
| After a code change | `docker compose up -d --build --no-deps mom-backend` | `docker compose up -d --build --no-deps mom-frontend` |
| After an env change | `docker compose up -d --force-recreate --no-deps mom-backend` | `docker compose up -d --force-recreate --no-deps mom-frontend` |
| Follow logs | `docker compose logs -f mom-backend` | `docker compose logs -f mom-frontend` |

The backend reads `backend/.env`. The frontend reads `BACKEND_API_KEY` from the root `.env`, and its React build lives inside the nginx image, so frontend code changes always need `--build`.

Rebuild both at once:

```bash
docker compose up -d --build --no-deps mom-backend mom-frontend
docker compose ps mom-backend mom-frontend
```

`docker compose restart` reuses the old image and env, so it does not pick up code or `.env` changes. Bring the backend up before the frontend, nginx returns 502 on `/api` while the backend is down. On Compose older than v2.20, use `docker compose rm -sf <service>` instead of `docker compose down <service>`.

Stop everything while keeping the data:

```bash
docker compose down
```

Never add `-v` to that command unless you want to delete the Attendee database, its accounts, API keys and bots.

## Reach the services through the bastion

The VM sits behind `tcg-bastion`. Forward the three ports to your Mac and keep the terminal open:

```bash
ssh -N -L 9901:localhost:9901 -L 9902:localhost:9902 -L 9903:localhost:9903 tcg-mcp-server
```

Then open http://localhost:9901 for the console, http://localhost:9903 for Attendee, and http://localhost:9902/docs for the backend Swagger, which only shows when `ENVIRONMENT` is not `production`.


Console   http://3.219.186.189:9901
Backend   http://3.219.186.189:9902/docs
Attendee  http://3.219.186.189:9903