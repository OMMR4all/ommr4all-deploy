# OMMR4all-deploy

Deployment/Setup of all OMMR4all services.

## Deployment with Docker

Requires [Docker](https://www.docker.com/) with the Compose plugin (or the
standalone `docker-compose` binary).

### Initial setup

1. Copy the example configuration and adjust it:
   ```shell
   cp .env.example .env
   # edit .env: PORT, STORAGE, optional DJANGO_SUPERUSER_* and LLM API keys
   ```
2. (Optional) Select submodule branches in `.env` and check them out:
   ```shell
   ./setup_branches.sh
   ```
3. Build and start:
   ```shell
   ./start.sh            # add --gpu for NVIDIA GPU passthrough, --no-cache for a full rebuild
   ```

The image is built from your **local checkout** (including the submodule
branches you have checked out). On container start the entrypoint backs up the
SQLite database, applies migrations, and — if `DJANGO_SUPERUSER_USERNAME` is
set in `.env` — creates the initial superuser automatically.

Three services are started: `web` (Apache + mod_wsgi), `ws` (daphne, serves
`/ws` websockets proxied through Apache) and `redis` (shared channel layer).

To create a superuser manually instead:
```shell
docker compose exec web /opt/ommr4all/ommr4all-deploy-venv/bin/python \
  /opt/ommr4all/ommr4all-deploy/modules/ommr4all-server/manage.py createsuperuser
```

### Updating

```shell
git pull --recurse-submodules
./start.sh
```

Run `docker image prune -f` to clean up unused older images.

### Stopping

```shell
./start.sh --stop
```

## Deployment without Docker

Follow the steps in the `Dockerfile` (Apache2 + mod_wsgi, venv at
`/opt/ommr4all/ommr4all-deploy-venv`, `python3 ommr4all-deploy/deploy.py`).
For automatic deployment a `gitlab-runner` can be registered with either tag:
* `deployment-production`: redeploy when a new version tag is added
* `deployment-master`: redeploy when `master` is updated

The runner needs `uv` and Node.js ≥20 on `PATH` (the deploy/test scripts check
for these and abort early if missing). `uv` auto-fetches CPython 3.12 for the venv.

### Websockets on bare metal (live document/chant updates)

`deploy.py` sets up the WSGI (Apache + mod_wsgi) app but does **not** provision the
ASGI websocket stack. Without it, live-update features silently do nothing behind
mod_wsgi (the in-memory channel layer can't cross worker processes). To enable them:

1. Run **Redis** and export `REDIS_URL` (e.g. `redis://localhost:6379/0`) in the
   environment seen by both mod_wsgi and daphne, so `settings.py` selects the
   Redis channel layer instead of the in-memory fallback.
2. Run **daphne** (ASGI) on port 8002, e.g. a systemd unit:

   ```ini
   [Service]
   Environment=REDIS_URL=redis://localhost:6379/0
   WorkingDirectory=/opt/ommr4all/ommr4all-deploy/modules/ommr4all-server
   ExecStart=/opt/ommr4all/ommr4all-deploy-venv/bin/daphne -b 127.0.0.1 -p 8002 --proxy-headers ommr4all.routing:application
   Restart=always
   ```

3. Proxy `/ws` from Apache to daphne (needs `a2enmod proxy proxy_wstunnel`). The
   compose config in `ommr4all-deploy/deploy/apache2.conf` targets the Docker
   service host `ws`; on bare metal use `127.0.0.1` instead:

   ```apache
   ProxyPass /ws ws://127.0.0.1:8002/ws
   ProxyPassReverse /ws ws://127.0.0.1:8002/ws
   ```

Defer this unless live updates are needed now; the rest of the app works without it.

## Development setup

See `CLAUDE.md` for the full, up-to-date instructions. Short version
(requires Python ≥3.12, Node.js ≥20, `uv`):

```shell
# Backend
uv sync                                   # from the repo root
cd modules/ommr4all-server
python manage.py migrate
python manage.py runserver

# Frontend
cd modules/ommr4all-client
npm install
npm start                                 # English; npm run start-de for German
```
