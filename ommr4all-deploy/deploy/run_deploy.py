from subprocess import check_call, call
import os
import re
import shutil
import sys
import logging
import argparse

# run_deploy.py runs as its own process (spawned by deploy.py), so it needs its
# own logging config: without basicConfig the root logger defaults to WARNING
# and every logger.info/debug below is silently dropped. Override the verbosity
# with DEPLOY_LOGLEVEL=INFO to make deploy output quieter.
logging.basicConfig(
    level=os.environ.get('DEPLOY_LOGLEVEL', 'DEBUG').upper(),
    format='%(asctime)s %(name)-24s %(levelname)-8s %(message)s',
)
logger = logging.getLogger(__name__)

this_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.abspath(os.path.join(this_dir, '..', '..'))
ommr4all_dir = '/opt/ommr4all'
storage_dir = os.path.join(ommr4all_dir, 'storage')
db_file_name = 'db.sqlite3'  # must match the filename in ommr4all/settings.py
secret_key = os.path.join(ommr4all_dir, '.secret_key')
python = sys.executable
# this script runs inside the venv deploy.py created, i.e. <venv>/bin/python
venv_dir = os.path.dirname(os.path.dirname(python))

DISK_MARGIN_BYTES = 1 * 1024 ** 3  # headroom required beyond the storage backup copy


def dir_size(path):
    """Total size (bytes) of a directory tree, ignoring entries we can't stat."""
    total = 0
    for entry in os.scandir(path):
        try:
            if entry.is_dir(follow_symlinks=False):
                total += dir_size(entry.path)
            elif entry.is_file(follow_symlinks=False):
                total += entry.stat(follow_symlinks=False).st_size
        except OSError:
            pass
    return total


def fix_web_permissions(web_user, db_file):
    """Hand storage and the database to the Apache worker user.

    This script runs as the deploying user (usually root via the CI runner), so
    everything it creates — the storage tree, the migrated database — is owned by
    that user, while Apache serves as `web_user`. Without this the first write
    (book upload, page save, login session) dies with PermissionError, and books
    whose meta was saved with a restrictive umask become unreadable, which 500s
    the whole book list. The Docker entrypoint does the equivalent.
    """
    import pwd
    try:
        if pwd.getpwnam(web_user).pw_uid == os.geteuid():
            # deploying user *is* the user serving the site (e.g. a gitlab-runner
            # that also hosts Apache) — it already owns everything it just wrote
            logger.info("Deploy runs as the Apache user %r; nothing to hand over", web_user)
            return
    except KeyError:
        logger.warning("Apache worker user %r does not exist; skipping permission fix. "
                       "Make sure the user serving the site can read and write %s and %s.",
                       web_user, storage_dir, db_file)
        return

    # trailing colon = the user's login group, which is not always named after the
    # user (e.g. nobody's group is nogroup); '{user}:{user}' would fail on those.
    owner = '{}:'.format(web_user)
    logger.info("Giving %s ownership of the storage tree %s", web_user, storage_dir)
    try:
        check_call(['chown', '-R', owner, storage_dir])
    except Exception:
        logger.exception("Could not chown %s to %s. The site will fail on the first "
                         "write; fix it manually with: chown -R %s %s",
                         storage_dir, web_user, owner, storage_dir)
        return

    if not os.path.exists(db_file):
        return
    db_dir = os.path.dirname(db_file)
    try:
        check_call(['chown', owner, db_file])
    except Exception:
        logger.exception("Could not chown the database %s to %s", db_file, web_user)
        return
    # SQLite writes -journal/-wal files next to the database, so the *directory*
    # must be writable too. When the db lives inside storage the chown above
    # already covered it; otherwise only widen that one directory — db_dir is
    # often the install root (/opt/ommr4all) and must not be handed over wholesale.
    if os.path.commonpath([os.path.abspath(db_dir),
                           os.path.abspath(storage_dir)]) != os.path.abspath(storage_dir):
        logger.warning("Database %s lives outside the storage tree; granting %s write "
                       "access to %s so SQLite can create its journal files. Consider "
                       "deploying with --dbdir %s to keep data and database together.",
                       db_file, web_user, db_dir, storage_dir)
        try:
            os.chmod(db_dir, os.stat(db_dir).st_mode | 0o002)
        except OSError:
            logger.exception("Could not make %s writable for %s", db_dir, web_user)


def guard_disk_space(path):
    """Abort *before* Apache is stopped if the disk can't hold the storage backup.

    The backup step duplicates the whole storage tree; running out of space
    mid-migration would leave the site down, so fail early while it is still up.
    """
    if not os.path.isdir(path):
        logger.debug("Disk-space guard: %s does not exist yet, nothing to back up", path)
        return
    needed = dir_size(path) + DISK_MARGIN_BYTES
    free = shutil.disk_usage(path).free
    logger.info("Disk-space guard for %s: need ~%.2f GiB (incl. %.0f GiB margin), have %.2f GiB free",
                path, needed / 1024 ** 3, DISK_MARGIN_BYTES / 1024 ** 3, free / 1024 ** 3)
    if free < needed:
        raise RuntimeError(
            "Not enough free disk space to safely back up storage before migrating: "
            "need ~{:.1f} GiB, have {:.1f} GiB free at {}. Free space (e.g. prune the old "
            "'{}.backup') and re-run.".format(
                needed / 1024 ** 3, free / 1024 ** 3, path, path))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dbdir", default=ommr4all_dir)
    parser.add_argument("--gpu", action='store_true')
    parser.add_argument("--gpu-legacy", dest='gpu_legacy', action='store_true',
                        help="Install a Pascal-compatible torch (sm_61, e.g. GTX 10xx) "
                             "instead of the default CUDA build.")
    parser.add_argument("--skip-storage-backup", dest='skip_storage_backup', action='store_true',
                        help="Skip copying the storage tree to storage.backup before migrating "
                             "(and the disk-space guard for it). Use when storage is large and "
                             "backed up elsewhere; note you lose the automatic storage rollback "
                             "if the deploy fails.")
    parser.add_argument("--web-user", dest='web_user', default='www-data',
                        help="User the Apache workers run as; storage and the database are "
                             "handed to it after deploying (default: www-data).")
    parser.add_argument("--skip-permission-fix", dest='skip_permission_fix', action='store_true',
                        help="Do not chown storage/database to --web-user. Use when permissions "
                             "are managed externally (ACLs, a shared group, or a non-standard "
                             "Apache user).")
    args = parser.parse_args()

    db_file = os.path.join(args.dbdir, db_file_name)

    logger.info("run_deploy starting (gpu=%s, gpu_legacy=%s)", args.gpu, args.gpu_legacy)
    logger.debug("root_dir=%s", root_dir)
    logger.debug("ommr4all_dir=%s", ommr4all_dir)
    logger.debug("storage_dir=%s", storage_dir)
    logger.debug("db_file=%s", db_file)
    logger.debug("python (venv interpreter)=%s", python)

    os.chdir(root_dir)

    logger.info("Setting up client")
    os.chdir('modules/ommr4all-client')
    logger.debug("Patching imprint link in src/app/app.component.html")
    check_call(['sed', '-i', '-e', 's#routerLink="/imprint"#href="https://www.uni-wuerzburg.de/en/sonstiges/imprint-privacy-policy/"#g', 'src/app/app.component.html'])
    logger.info("Running 'npm install' for the Angular client")
    check_call(['npm', 'install'])
    for config in ['production', 'production-de']:
        logger.info("Building Angular client (configuration=%s)", config)
        check_call(['node_modules/.bin/ng', 'build', '--configuration', config])

    logger.info("Copying Angular build output to server static directory")
    os.chdir(root_dir)
    client_dist_dir = os.path.join(root_dir, 'modules', 'ommr4all-client', 'dist')
    server_static_dir = os.path.join(root_dir, 'modules', 'ommr4all-server', 'webapp', 'static')
    os.makedirs(server_static_dir, exist_ok=True)
    for dist_name, locale in [('ommr4all-client', None), ('ommr4all-client-de', 'de')]:
        dst = os.path.join(server_static_dir, dist_name)
        # Angular 17+ puts build output in browser/ (and localized builds add a locale subdir)
        browser_dir = os.path.join(client_dist_dir, dist_name, 'browser')
        if locale and os.path.isdir(os.path.join(browser_dir, locale)):
            src = os.path.join(browser_dir, locale)
        elif os.path.isdir(browser_dir):
            src = browser_dir
        else:
            src = os.path.join(client_dist_dir, dist_name)
        logger.info("Copying client build %s -> %s", src, dst)
        shutil.copytree(src, dst, dirs_exist_ok=True)

    logger.info("Setting up virtual environment and dependencies")
    os.chdir(root_dir)

    # The torch build is chosen by a uv extra, all three variants locked in uv.lock
    # (see the [project.optional-dependencies] block in the root pyproject.toml):
    #   no extra -> torch from PyPI, already CUDA-enabled; what Docker uses
    #   cuda     -> newest cu126 build, for hosts whose driver predates CUDA 13
    #   pascal   -> torch 2.7.1+cu126, the last release with Pascal (sm_61) kernels
    extra, label = None, 'default (PyPI, CUDA-enabled) torch'
    if args.gpu_legacy:
        extra, label = 'pascal', 'Pascal-compatible torch 2.7.1+cu126 (sm_61, e.g. GTX 10xx)'
    elif args.gpu:
        extra, label = 'cuda', 'CUDA (cu126) torch/torchvision'

    # uv sync installs exactly what uv.lock pins, including the workspace members
    # (ommr4all-server, -line-detection, -layout-analysis) as editable — replacing
    # both the requirements.txt install and the per-submodule editable installs.
    # --locked fails on a stale lock instead of silently resolving something else;
    # run `uv lock` and commit the result after changing any pyproject.toml.
    sync = ['uv', 'sync', '--locked'] + (['--extra', extra] if extra else [])
    logger.info("Installing locked dependencies with %s", label)
    check_call(sync, env=dict(os.environ, UV_PROJECT_ENVIRONMENT=venv_dir))
    logger.info("Dependency installation complete")

    os.chdir(root_dir)
    logger.debug("Ensuring storage directory exists: %s", storage_dir)
    os.makedirs(storage_dir, exist_ok=True)

    logger.info("Changing server settings")
    os.chdir('modules/ommr4all-server')

    # create/read secret key
    if not os.path.exists(secret_key):
        logger.info("Generating new Django secret key at %s", secret_key)
        from django.core.management import utils
        with open(secret_key, 'w') as f:
            f.write(utils.get_random_secret_key())
    else:
        logger.debug("Reusing existing Django secret key at %s", secret_key)

    with open(secret_key, 'r') as f:
        random_secret_key = f.read()

    with open('ommr4all/settings.py', 'r') as f:
        settings = f.read()

    settings = settings.replace('ALLOWED_HOSTS = []', 'ALLOWED_HOSTS = ["*"]')
    settings = settings.replace('DEBUG = True', 'DEBUG = False')
    # settings.py reads the db path as os.environ.get('OMMR4ALL_DB_PATH', <default>);
    # this only rewrites the *default*, so a runtime OMMR4ALL_DB_PATH (Docker) still wins.
    settings = settings.replace("os.path.join(BASE_DIR, 'db.sqlite3')", "'{}'".format(db_file))
    settings = settings.replace("BASE_DIR, 'storage'", "'{}'".format(storage_dir))
    settings = re.sub(r"SECRET_KEY = .*", "SECRET_KEY = '{}'".format(random_secret_key), settings)

    # The string replacements above silently no-op if the upstream settings.py
    # formatting changes — fail the deploy instead of shipping dev settings.
    for marker in ['ALLOWED_HOSTS = ["*"]',
                   'DEBUG = False',
                   db_file,
                   "'{}'".format(storage_dir),
                   "SECRET_KEY = '{}'".format(random_secret_key)]:
        if marker not in settings:
            raise RuntimeError('Patching settings.py failed: {!r} not found after rewrite. '
                               'Check the replace patterns against the current settings.py.'.format(marker))
    logger.debug("settings.py patch markers verified (ALLOWED_HOSTS, DEBUG, db path, storage, SECRET_KEY)")

    with open('ommr4all/settings.py', 'w') as f:
        f.write(settings)
    logger.info("Wrote patched production settings.py")

    logger.info("Collecting static files")
    check_call([python, 'manage.py', 'collectstatic', '--noinput'])

    logger.info("Migrating database and copying new version")

    # systemctl only available on bare-metal (not inside Docker)
    has_systemctl = os.path.exists('/bin/systemctl')
    logger.debug("systemctl available: %s (Apache will %sbe managed)",
                 has_systemctl, '' if has_systemctl else 'NOT ')

    def apache(action):
        if has_systemctl:
            logger.info("Apache: %s apache2.service", action)
            call(['sudo', '/bin/systemctl', action, 'apache2.service'])

    # Defensive guard: bail out while the site is still up if the disk can't
    # hold the storage backup taken below.
    if not args.skip_storage_backup:
        guard_disk_space(storage_dir)

    db_backup = db_file + '.backup'

    apache('stop')
    try:
        # backup files
        if args.skip_storage_backup:
            logger.warning("Skipping storage backup (--skip-storage-backup): no automatic "
                           "storage rollback if this deploy fails")
        else:
            logger.info("Backing up storage tree %s -> %s", storage_dir, storage_dir + '.backup')
            shutil.copytree(storage_dir, storage_dir + '.backup', dirs_exist_ok=True)
        shutil.rmtree(db_backup, ignore_errors=True)
        if os.path.exists(db_file):
            logger.info("Backing up database %s -> %s", db_file, db_backup)
            shutil.copyfile(db_file, db_backup)
        else:
            logger.debug("No existing database at %s to back up", db_file)

        try:
            logger.info("Running database migrations")
            check_call([python, 'manage.py', 'migrate'])
            logger.info("Migrations applied successfully")
        except Exception:
            # Migration failed with Apache stopped. Restore the DB and leave the
            # already-deployed code untouched (we haven't copied the new version
            # yet), so the old, working site comes back up on restart below.
            logger.error("Migration failed; restoring database from backup and aborting "
                         "deploy (previously deployed version left in place).")
            if os.path.exists(db_backup):
                shutil.copyfile(db_backup, db_file)
            raise

        # copy new version (only after a successful migration)
        os.chdir(root_dir)
        deploy_target = os.path.join(ommr4all_dir, 'ommr4all-deploy')
        logger.info("Deploying new version: %s -> %s", root_dir, deploy_target)
        shutil.rmtree(deploy_target, ignore_errors=True)
        try:
            shutil.copytree(root_dir, deploy_target)
        except Exception:
            # copytree can raise a shutil.Error bundling many per-file failures
            # (e.g. broken symlinks in the checkout); log the full detail so the
            # cause is visible in the deploy output, then re-raise to abort.
            logger.exception("Failed to copy new version %s -> %s", root_dir, deploy_target)
            raise
        logger.info("New version copied into place")

        # After migrating and copying, hand the data over to the Apache user.
        # Inside the try block so a failure here still restarts Apache below.
        if args.skip_permission_fix:
            logger.warning("Skipping permission fix (--skip-permission-fix); ensure %r can "
                           "read and write the storage tree and database itself", args.web_user)
        else:
            try:
                fix_web_permissions(args.web_user, db_file)
            except Exception:
                # never fail an otherwise successful deploy over permissions —
                # the code and database are already in place at this point
                logger.exception("Permission fix failed; the deployed site may not be able "
                                 "to write. Check ownership of %s and %s.", storage_dir, db_file)
    finally:
        # Always bring Apache back up, even if the migration or copy failed.
        apache('start')

    logger.info("Setup finished")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Make sure the traceback lands in the deploy log/stderr before the
        # process exits non-zero, rather than being lost or truncated.
        logger.exception("run_deploy failed with an unhandled exception")
        raise
