from subprocess import check_call
import os
import argparse

this_dir = os.path.dirname(os.path.realpath(__file__))
venv = '/opt/ommr4all/ommr4all-deploy-venv'
python = os.path.join(venv, 'bin', 'python')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpu', action='store_true')
    parser.add_argument("--dbdir")

    args = parser.parse_args()

    os.chdir(this_dir)

    # Create virtual environment with uv (Python 3.12+)
    check_call(['uv', 'venv', venv, '--python', 'python3.12'])

    # Run deploy script inside the venv
    check_call([python, os.path.join(this_dir, 'deploy', 'run_deploy.py')] +
               (['--gpu'] if args.gpu else []) +
               (['--dbdir', args.dbdir] if args.dbdir else []))


if __name__ == "__main__":
    main()
