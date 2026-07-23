from subprocess import check_call, check_output
import os
import sys
import shutil
import argparse

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
    parser.add_argument("--dbdir")

    args = parser.parse_args()

    preflight(check_node=True)

    os.chdir(this_dir)

    # Create virtual environment with uv (Python 3.12+)
    check_call(['uv', 'venv', venv, '--python', 'python3.12'])

    # Run deploy script inside the venv
    check_call([python, os.path.join(this_dir, 'deploy', 'run_deploy.py')] +
               (['--gpu'] if args.gpu else []) +
               (['--gpu-legacy'] if args.gpu_legacy else []) +
               (['--dbdir', args.dbdir] if args.dbdir else []))


if __name__ == "__main__":
    main()
