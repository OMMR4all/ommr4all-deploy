from subprocess import check_call
import shutil
import os

this_dir = os.path.dirname(os.path.realpath(__file__))
venv = os.path.abspath(os.path.join('/opt', 'ommr4all', 'ommr4all-deploy-venv'))
python = os.path.join(venv, 'bin', 'python')


def main():
    os.chdir(this_dir)

    # setup python3 venv for server testing
    check_call(['virtualenv',  '-p', 'python3', venv])

    # run test script inside the venv
    check_call([python, os.path.join(this_dir, 'deploy', 'run_deploy.py')])

    # cleanup venv
    shutil.rmtree(venv)


if __name__ == "__main__":
    main()