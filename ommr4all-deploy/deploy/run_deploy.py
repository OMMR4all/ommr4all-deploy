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
db_file_name = 'db.sqlite'
secret_key = os.path.join(ommr4all_dir, '.secret_key')
python = sys.executable


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

    logger.info("Setting up virtual environment and dependencies")
    os.chdir(root_dir)
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
    settings = settings.replace('db.sqlite', '{}'.format(db_file))
    settings = settings.replace("BASE_DIR, 'storage'", "'{}'".format(storage_dir))
    settings = re.sub(r"SECRET_KEY = .*", "SECRET_KEY = '{}'".format(random_secret_key), settings)

    with open('ommr4all/settings.py', 'w') as f:
        f.write(settings)

    logger.info("Collecting static files")
    check_call([python, 'manage.py', 'collectstatic', '--noinput'])

    logger.info("Migrating database and copying new version")
    # systemctl only available on bare-metal (not inside Docker)
    if os.path.exists('/bin/systemctl'):
        call(['sudo', '/bin/systemctl', 'stop', 'apache2.service'])

    # backup files
    shutil.copytree(storage_dir, storage_dir + '.backup', dirs_exist_ok=True)
    shutil.rmtree(db_file + '.backup', ignore_errors=True)
    if os.path.exists(db_file):
        shutil.copyfile(db_file, db_file + '.backup')

    check_call([python, 'manage.py', 'migrate'])

    # copy new version
    os.chdir(root_dir)
    deploy_target = os.path.join(ommr4all_dir, 'ommr4all-deploy')
    shutil.rmtree(deploy_target, ignore_errors=True)
    shutil.copytree(root_dir, deploy_target)

    # finally restart the service (bare-metal only)
    if os.path.exists('/bin/systemctl'):
        call(['sudo', '/bin/systemctl', 'start', 'apache2.service'])
    logger.info("Setup finished")


if __name__ == "__main__":
    main()
