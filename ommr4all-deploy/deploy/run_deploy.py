from subprocess import check_call, call
import os
import re
import shutil
import sys
import logging
import argparse

logger = logging.getLogger(__name__)

this_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.abspath(os.path.join(this_dir, '..', '..'))
ommr4all_dir = '/opt/ommr4all'
storage_dir = os.path.join(ommr4all_dir, 'storage')
db_file_name = 'db.sqlite3'  # must match the filename in ommr4all/settings.py
secret_key = os.path.join(ommr4all_dir, '.secret_key')
python = sys.executable

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


def guard_disk_space(path):
    """Abort *before* Apache is stopped if the disk can't hold the storage backup.

    The backup step duplicates the whole storage tree; running out of space
    mid-migration would leave the site down, so fail early while it is still up.
    """
    if not os.path.isdir(path):
        return
    needed = dir_size(path) + DISK_MARGIN_BYTES
    free = shutil.disk_usage(path).free
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
    args = parser.parse_args()

    db_file = os.path.join(args.dbdir, db_file_name)

    os.chdir(root_dir)

    logger.info("Setting up client")
    os.chdir('modules/ommr4all-client')
    check_call(['sed', '-i', '-e', 's#routerLink="/imprint"#href="https://www.uni-wuerzburg.de/en/sonstiges/imprint-privacy-policy/"#g', 'src/app/app.component.html'])
    check_call(['npm', 'install'])
    for config in ['production', 'production-de']:
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
        shutil.copytree(src, dst, dirs_exist_ok=True)

    logger.info("Setting up virtual environment and dependencies")
    os.chdir(root_dir)
    if args.gpu:
        # Install CUDA (cu121) torch/torchvision first; requirements.txt pins them
        # unpinned, so the install below sees them satisfied and keeps the GPU build.
        logger.info("Installing CUDA (cu121) torch/torchvision for --gpu")
        check_call(['uv', 'pip', 'install', '--python', python,
                    'torch', 'torchvision',
                    '--index-url', 'https://download.pytorch.org/whl/cu121'])
    check_call(['uv', 'pip', 'install', '--python', python, '-r', 'modules/ommr4all-server/requirements.txt'])
    for submodule in ['ommr4all-line-detection', 'ommr4all-layout-analysis']:
        check_call(['uv', 'pip', 'install', '--python', python, '-e', os.path.join('modules', submodule)])

    os.chdir(root_dir)
    os.makedirs(storage_dir, exist_ok=True)

    logger.info("Changing server settings")
    os.chdir('modules/ommr4all-server')

    # create/read secret key
    if not os.path.exists(secret_key):
        from django.core.management import utils
        with open(secret_key, 'w') as f:
            f.write(utils.get_random_secret_key())

    with open(secret_key, 'r') as f:
        random_secret_key = f.read()

    with open('ommr4all/settings.py', 'r') as f:
        settings = f.read()

    settings = settings.replace('ALLOWED_HOSTS = []', 'ALLOWED_HOSTS = ["*"]')
    settings = settings.replace('DEBUG = True', 'DEBUG = False')
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

    with open('ommr4all/settings.py', 'w') as f:
        f.write(settings)

    logger.info("Collecting static files")
    check_call([python, 'manage.py', 'collectstatic', '--noinput'])

    logger.info("Migrating database and copying new version")

    # systemctl only available on bare-metal (not inside Docker)
    has_systemctl = os.path.exists('/bin/systemctl')

    def apache(action):
        if has_systemctl:
            call(['sudo', '/bin/systemctl', action, 'apache2.service'])

    # Defensive guard: bail out while the site is still up if the disk can't
    # hold the storage backup taken below.
    guard_disk_space(storage_dir)

    db_backup = db_file + '.backup'

    apache('stop')
    try:
        # backup files
        shutil.copytree(storage_dir, storage_dir + '.backup', dirs_exist_ok=True)
        shutil.rmtree(db_backup, ignore_errors=True)
        if os.path.exists(db_file):
            shutil.copyfile(db_file, db_backup)

        try:
            check_call([python, 'manage.py', 'migrate'])
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
        shutil.rmtree(deploy_target, ignore_errors=True)
        shutil.copytree(root_dir, deploy_target)
    finally:
        # Always bring Apache back up, even if the migration or copy failed.
        apache('start')

    logger.info("Setup finished")


if __name__ == "__main__":
    main()
