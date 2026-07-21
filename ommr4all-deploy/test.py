from subprocess import check_call
import os
import sys
import shutil

this_dir = os.path.dirname(os.path.realpath(__file__))
venv = os.path.abspath(os.path.join(this_dir, '..', 'test-server-venv'))
python = os.path.join(venv, 'bin', 'python')


def preflight():
    """Fail fast if the runner lacks uv (needed to build the Python 3.12 venv)."""
    if shutil.which('uv') is None:
        sys.exit("Pre-flight check failed: 'uv' is not on PATH. Install uv "
                 "(https://docs.astral.sh/uv/) on this runner; the test script "
                 "requires it to build the Python 3.12 virtualenv.")


def main():
    preflight()

    os.chdir(this_dir)

    # Create virtual environment with uv (Python 3.12+)
    check_call(['uv', 'venv', venv, '--python', 'python3.12'])

    try:
        # Run test script inside the venv
        check_call([python, os.path.join(this_dir, 'test', 'run_test.py')])
    finally:
        # Cleanup venv (also on test failure)
        shutil.rmtree(venv, ignore_errors=True)


if __name__ == "__main__":
    main()
