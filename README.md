# OMMR4all-deploy

Deployment/Setup of all OMMR4all services.

## Deployment with Docker

Requires [Docker](https://www.docker.com/) with the Compose plugin (or the
standalone `docker-compose` binary).

### Start

```shell
./start.sh            # add --gpu for NVIDIA GPU passthrough, --no-cache for a full rebuild
```

That is the whole setup. On the first run `start.sh` creates `.env` from
`.env.example`, creates the storage/database directories, builds the image and
starts the services. The app is then served at `http://localhost:8001`.

### Configuration

All settings live in the `.env` file next to `docker-compose.yml`. Edit it and
re-run `./start.sh` to apply. The most relevant ones:

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | `8001` | Host port the app is served on |
| `STORAGE` | `./storage` | **Host** directory holding all book/page data |
| `DB_DIR` | *(= `STORAGE`)* | Host directory for the SQLite database — set it only if you want the database somewhere other than the storage directory |
| `DB_NAME` | `db.sqlite3` | Filename of the database in that directory |
| `DJANGO_SUPERUSER_USERNAME` / `_EMAIL` / `_PASSWORD` | *(empty)* | Auto-create the first admin user on first start |
| `GEMINI_API_KEY`, `OPENAI_API_KEY`, … | *(empty)* | Optional LLM providers for the `text_llm` step |

Both directories are bind-mounted into the container, so data and database
survive rebuilds. By default the database is `<STORAGE>/db.sqlite3`, i.e. data
and database stay together and can be moved as one directory.

Optionally select submodule branches in `.env` and check them out with
`./setup_branches.sh` before starting.

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

### One-time server setup

`deploy.py` builds the client, installs dependencies, migrates and swaps the code
in — but it does **not** install the Apache site. On a new machine, once:

```shell
sudo cp ommr4all-deploy/deploy/apache2.conf /etc/apache2/sites-available/ommr4all.conf
sudo a2enmod proxy proxy_http proxy_wstunnel     # required: the config uses ProxyPass
sudo a2ensite ommr4all.conf
sudo apachectl configtest && sudo systemctl reload apache2
```

`a2enmod` is not optional — `ProxyPass` is an unknown directive without `mod_proxy`
and Apache will refuse to start. If you do not need websockets, delete the two
`ProxyPass` lines from the vhost instead and skip those modules. The shipped config
points `/ws` at the Docker service host `ws`; change it to `127.0.0.1` on bare metal
(see the websocket section).

**mod_wsgi must match the venv's Python.** The deploy venv is Python 3.12, and
mod_wsgi is compiled against one specific Python minor version — `python-home=`
only redirects the venv prefix, it cannot change the interpreter inside the module.
A mod_wsgi built for another version (e.g. an old `mod_wsgi-py38.so` left over from
a previous install) fails at startup. Use the distro package, whose Python matches
the system `python3`:

```shell
sudo apt install libapache2-mod-wsgi-py3    # Ubuntu 24.04 -> Python 3.12
sudo a2enmod wsgi
apachectl -M | grep wsgi                    # verify exactly one wsgi_module
```

Remove any hand-written `LoadModule wsgi_module ...` line when using the package —
loading it twice is an error. On a distro whose `python3` is not 3.12, build the
module against the deploy venv instead (`pip install mod_wsgi` in the venv, then
`mod_wsgi-express module-config` for the `LoadModule` line) — but add `mod_wsgi` to
`modules/ommr4all-server/requirements.txt`, because `deploy.py` deletes and rebuilds
the venv on every deploy and would otherwise remove the module Apache loads.

### File permissions

Apache serves as `www-data`, while `deploy.py` runs as the deploying user (often
root), so everything it creates would otherwise be unwritable for the site. Since
2026-07-26 `run_deploy.py` chowns the storage tree and the database to the Apache
user at the end of each deploy (`--web-user` to change it, `--skip-permission-fix`
to opt out if you manage permissions via ACLs or a shared group).

If the database lives outside the storage tree — which is the default, at
`/opt/ommr4all/db.sqlite3` — its directory must also be writable so SQLite can
create its `-journal`/`-wal` files. The deploy widens just that one directory and
logs a warning; deploying with `--dbdir /opt/ommr4all/storage` keeps data and
database together and avoids it.

Books copied onto the server by hand (rsync, unzip, `manage.py` run as root) are
owned by that user again. Re-running the deploy fixes them, or do it directly:

```shell
sudo chown -R www-data: /opt/ommr4all/storage
```

### Websockets on bare metal (live document/chant updates)

`deploy.py` sets up the WSGI (Apache + mod_wsgi) app but does **not** provision the
ASGI websocket stack. Without it, live-update features silently do nothing behind
mod_wsgi (the in-memory channel layer can't cross worker processes). To enable them:

1. Install and run **Redis** (`sudo apt install redis-server`), then make
   `REDIS_URL` visible to **both** processes so `settings.py` selects the Redis
   channel layer instead of the in-memory fallback.

   For Apache this means the *process* environment — `settings.py` reads
   `os.environ` at import time, so Apache's `SetEnv` does **not** work (it only
   populates the per-request WSGI environ). Put it in `/etc/apache2/envvars`,
   which `apachectl` sources before starting, then restart (not reload) Apache:

   ```shell
   echo 'export REDIS_URL=redis://localhost:6379/0' | sudo tee -a /etc/apache2/envvars
   sudo systemctl restart apache2
   ```

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
