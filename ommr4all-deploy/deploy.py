from subprocess import check_call
import shutil
import os
import argparse

this_dir = os.path.dirname(os.path.realpath(__file__))
venv = os.path.abspath(os.path.join('/opt', 'ommr4all', 'ommr4all-deploy-venv'))
python = os.path.join(venv, 'bin', 'python')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpu', action='store_true')
    parser.add_argument("--dbdir")

    args = parser.parse_args()

    os.chdir(this_dir)

    # setup python3 venv for server testing
    check_call(['virtualenv',  '-p', 'python3.7', venv])

    # run test script inside the venv
    check_call([python, os.path.join(this_dir, 'deploy', 'run_deploy.py')] +
               (['--gpu'] if args.gpu else []) +
               (['--dbdir', args.dbdir] if args.dbdir else []))


if __name__ == "__main__":
    main()
