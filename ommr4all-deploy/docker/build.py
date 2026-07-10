"""
Docker build-time setup.

Runs during `docker build`:
  - Builds the Angular client (both production locales)
  - Patches Django settings.py for production (ALLOWED_HOSTS, DEBUG, paths, SECRET_KEY)
  - Runs manage.py collectstatic

Migrations are intentionally NOT run here; they run at container start
via entrypoint.sh so the volume-mounted storage/database is available.
"""
import os
import re
import shutil
import subprocess
import sys

this_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.abspath(os.path.join(this_dir, "..", ".."))
server_dir = os.path.join(root_dir, "modules", "ommr4all-server")
client_dir = os.path.join(root_dir, "modules", "ommr4all-client")

# These paths are fixed inside the container; the host directory is
# volume-mounted to /opt/ommr4all/storage at runtime.
storage_dir = "/opt/ommr4all/storage"
db_file = os.path.join(storage_dir, "db.sqlite")
secret_key_file = "/opt/ommr4all/.secret_key"

# Python from the uv-managed venv (created by `uv sync` in the Dockerfile).
python = os.path.join(root_dir, ".venv", "bin", "python")


def _generate_secret_key() -> str:
    """Generate a Django secret key using the installed Django package."""
    result = subprocess.run(
        [
            python, "-c",
            "from django.core.management.utils import get_random_secret_key;"
            " print(get_random_secret_key())",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def build_angular() -> None:
    print("==> Building Angular client...")
    os.chdir(client_dir)
    subprocess.run(["npm", "install"], check=True)
    for config in ["production", "production-de"]:
        subprocess.run(["ng", "build", "--configuration", config], check=True)
    os.chdir(root_dir)

    # Copy Angular dist into Django's webapp/static so views.py can find
    # index.html and collectstatic picks up all JS/CSS assets.
    # Always replace — symlinks from the source tree may not resolve correctly
    # inside the container at runtime.
    static_dir = os.path.join(server_dir, "webapp", "static")
    for name in ["ommr4all-client", "ommr4all-client-de"]:
        # Angular 17+ outputs into browser/; localized builds add browser/{locale}/
        src = os.path.join(client_dir, "dist", name, "browser")
        if not os.path.exists(src):
            src = os.path.join(client_dir, "dist", name)  # fallback
        elif not os.path.exists(os.path.join(src, "index.html")):
            # locale subdirectory — pick the single subdir inside browser/
            subdirs = [d for d in os.listdir(src) if os.path.isdir(os.path.join(src, d))]
            if len(subdirs) == 1:
                src = os.path.join(src, subdirs[0])
        dst = os.path.join(static_dir, name)
        if not os.path.exists(src):
            print(f"  WARNING: Angular dist not found at {src}, skipping")
            continue

        if os.path.islink(dst):
            os.unlink(dst)
        elif os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f"  Copied {name} → webapp/static/{name}")


def patch_django_settings() -> None:
    print("==> Patching Django settings...")
    os.makedirs("/opt/ommr4all", exist_ok=True)
    os.makedirs(storage_dir, exist_ok=True)

    if not os.path.exists(secret_key_file):
        key = _generate_secret_key()
        with open(secret_key_file, "w") as f:
            f.write(key)

    with open(secret_key_file, "r") as f:
        secret_key = f.read().strip()

    settings_path = os.path.join(server_dir, "ommr4all", "settings.py")
    with open(settings_path, "r") as f:
        settings = f.read()

    settings = settings.replace('ALLOWED_HOSTS = []', 'ALLOWED_HOSTS = ["*"]')
    settings = settings.replace("DEBUG = True", "DEBUG = False")
    settings = settings.replace("db.sqlite", db_file)
    settings = settings.replace("BASE_DIR, 'storage'", f"'{storage_dir}'")
    settings = re.sub(
        r"SECRET_KEY = .*",
        f"SECRET_KEY = '{secret_key}'",
        settings,
    )

    with open(settings_path, "w") as f:
        f.write(settings)


def collect_static() -> None:
    print("==> Collecting static files...")
    os.chdir(server_dir)
    subprocess.run([python, "manage.py", "collectstatic", "--noinput"], check=True)
    os.chdir(root_dir)


def main() -> None:
    os.chdir(root_dir)
    build_angular()
    patch_django_settings()
    collect_static()
    print("==> Build-time setup complete.")


if __name__ == "__main__":
    main()
