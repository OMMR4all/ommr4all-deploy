from subprocess import check_call, call
import os
import re
from distutils.dir_util import copy_tree
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
pip = os.path.join(os.path.dirname(python), 'pip')


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
    check_call(['npm', 'audit', 'fix'])
    for config in ['production', 'production-de']:
        check_call(['ng', 'build', '--configuration', config])

    logger.info("Setting up virtual environment and dependencies")
    os.chdir(root_dir)
    check_call([pip, 'install', 'tensorflow_gpu~=2.4.0' if args.gpu else 'tensorflow~=2.4.0'])
    check_call([pip, 'install', '-r', 'modules/ommr4all-server/requirements.txt'])
    for submodule in ['ommr4all-page-segmentation', 'ommr4all-line-detection', 'ommr4all-layout-analysis', 'calamari']:
        os.chdir('modules/' + submodule)
        check_call([python, 'setup.py', 'install'])
        os.chdir(root_dir)

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
    call(['sudo', '/bin/systemctl', 'stop',  'apache2.service'])

    # backup files
    copy_tree(storage_dir, storage_dir + '.backup')
    shutil.rmtree(db_file + '.backup', ignore_errors=True)
    if os.path.exists(db_file):
        shutil.copyfile(db_file, db_file + '.backup')

    check_call([python, 'manage.py', 'migrate'])

    # copy new version and remove all
    os.chdir(root_dir)
    shutil.rmtree(os.path.join(ommr4all_dir, 'ommr4all-deploy'), ignore_errors=True)
    copy_tree(root_dir, os.path.join(ommr4all_dir, 'ommr4all-deploy'))

    # finally restart the service

    call(['sudo', '/bin/systemctl', 'start',  'apache2.service'])
    logger.info("Setup finished")


if __name__ == "__main__":
    main()
