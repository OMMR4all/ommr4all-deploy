from subprocess import check_call
import os
import shutil

this_dir = os.path.dirname(os.path.realpath(__file__))
venv = os.path.abspath(os.path.join(this_dir, '..', 'test-server-venv'))
python = os.path.join(venv, 'bin', 'python')


def main():
    os.chdir(this_dir)

    # Create virtual environment with uv (Python 3.12+)
    check_call(['uv', 'venv', venv, '--python', 'python3.12'])

    # Run test script inside the venv
    check_call([python, os.path.join(this_dir, 'test', 'run_test.py')])

    # Cleanup venv
    shutil.rmtree(venv)


if __name__ == "__main__":
    main()
