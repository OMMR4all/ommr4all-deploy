from subprocess import check_call, check_output
import os
import sys
import shutil
import logging
import argparse

# Configure logging so the info/debug statements below (and in run_deploy.py)
# are actually emitted; without this the root logger defaults to WARNING and
# swallows them. Override with DEPLOY_LOGLEVEL=INFO to make the output quieter.
logging.basicConfig(
    level=os.environ.get('DEPLOY_LOGLEVEL', 'DEBUG').upper(),
    format='%(asctime)s %(name)-24s %(levelname)-8s %(message)s',
)
logger = logging.getLogger(__name__)

this_dir = os.path.dirname(os.path.realpath(__file__))
venv = '/opt/ommr4all/ommr4all-deploy-venv'
python = os.path.join(venv, 'bin', 'python')

MIN_NODE_MAJOR = 20  # Angular 21 requires Node.js >= 20


def preflight(check_node):
    """Fail fast (before any venv/build work) if the runner lacks the toolchain.

    Runs while the old site is still up, so a clear message here beats a cryptic
    failure once the deploy is already touching Apache/the database.
    """
    if shutil.which('uv') is None:
        sys.exit("Pre-flight check failed: 'uv' is not on PATH. Install uv "
                 "(https://docs.astral.sh/uv/) on this runner; the deploy/test scripts "
                 "require it to build the Python 3.12 virtualenv.")
    if check_node:
        if shutil.which('node') is None:
            sys.exit("Pre-flight check failed: 'node' is not on PATH. The Angular 21 client "
                     "build requires Node.js >= {}.".format(MIN_NODE_MAJOR))
        version = check_output(['node', '--version']).decode().strip()  # e.g. 'v22.22.2'
        try:
            major = int(version.lstrip('v').split('.')[0])
        except (ValueError, IndexError):
            sys.exit("Pre-flight check failed: could not parse Node.js version from "
                     "{!r}.".format(version))
        if major < MIN_NODE_MAJOR:
            sys.exit("Pre-flight check failed: Node.js >= {} required for the Angular 21 "
                     "client build; runner has {}.".format(MIN_NODE_MAJOR, version))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpu', action='store_true')
    parser.add_argument('--gpu-legacy', dest='gpu_legacy', action='store_true',
                        help="Install a Pascal-compatible torch (sm_61, e.g. GTX 10xx) "
                             "instead of the default CUDA build.")
    parser.add_argument('--skip-storage-backup', dest='skip_storage_backup', action='store_true',
                        help="Skip backing up the storage tree before migrating (forwarded to "
                             "run_deploy.py). Use when storage is large and backed up elsewhere.")
    parser.add_argument("--dbdir")
    parser.add_argument('--web-user', dest='web_user', default='www-data',
                        help="User the Apache workers run as; storage and the database are "
                             "handed to it after deploying (default: www-data).")
    parser.add_argument('--skip-permission-fix', dest='skip_permission_fix', action='store_true',
                        help="Do not chown storage/database to --web-user (forwarded to "
                             "run_deploy.py).")

    args = parser.parse_args()

    logger.info("Starting deploy (gpu=%s, gpu_legacy=%s, dbdir=%s)",
                args.gpu, args.gpu_legacy, args.dbdir or '<default>')

    logger.debug("Running pre-flight toolchain checks")
    preflight(check_node=True)
    logger.debug("Pre-flight checks passed")

    os.chdir(this_dir)

    # Recreate the virtual environment from scratch so a stale or partially
    # installed venv from an earlier (possibly failed) deploy can never leak
    # into this one. A fresh venv guarantees the dependency installs below
    # start from a clean slate.
    if os.path.isdir(venv):
        logger.info("Removing existing virtual environment at %s for a fresh install", venv)
        shutil.rmtree(venv)
    elif os.path.exists(venv):
        # path exists but is not a directory (unexpected) — clear the stray entry
        logger.warning("Found non-directory at venv path %s; removing it", venv)
        os.remove(venv)
    else:
        logger.debug("No existing virtual environment at %s", venv)

    # Create virtual environment with uv (Python 3.12+)
    logger.info("Creating virtual environment at %s (python3.12)", venv)
    check_call(['uv', 'venv', venv, '--python', 'python3.12'])

    # Run deploy script inside the venv
    logger.info("Running run_deploy.py inside the venv (%s)", python)
    check_call([python, os.path.join(this_dir, 'deploy', 'run_deploy.py')] +
               (['--gpu'] if args.gpu else []) +
               (['--gpu-legacy'] if args.gpu_legacy else []) +
               (['--skip-storage-backup'] if args.skip_storage_backup else []) +
               (['--skip-permission-fix'] if args.skip_permission_fix else []) +
               (['--web-user', args.web_user] if args.web_user else []) +
               (['--dbdir', args.dbdir] if args.dbdir else []))
    logger.info("Deploy finished successfully")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Deploy failed with an unhandled exception")
        raise
