from subprocess import check_call
import os
import sys
from runpy import run_path

this_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.abspath(os.path.join(this_dir, '..', '..'))
python = sys.executable

server_test_manager = run_path(os.path.join(root_dir, 'modules', 'ommr4all-server', 'tests', 'manage_gitlab-ci.py'))


def main():
    os.chdir(root_dir)

    # Install exactly what uv.lock pins. The workspace members (ommr4all-server,
    # -line-detection, -layout-analysis) are dependencies of the root project, so
    # this replaces both the requirements.txt install and the per-submodule
    # editable installs — uv puts workspace members in the venv as editable.
    # --locked fails if uv.lock is stale rather than silently resolving something
    # else, so CI can never test a dependency set that was never locked; run
    # `uv lock` and commit the result after changing any pyproject.toml.
    venv_dir = os.path.dirname(os.path.dirname(python))
    check_call(['uv', 'sync', '--locked'],
               env=dict(os.environ, UV_PROJECT_ENVIRONMENT=venv_dir))

    #for submodule in ['ommr4all-line-detection', 'ommr4all-layout-analysis']:
        # check if hash = version in server is equal to the actual submodule
        #hash = os.popen('git rev-parse HEAD').read().strip()
        #server_hash = [repo.hash for repo in server_test_manager['repos'] if repo.name == submodule]
        #if len(server_hash) != 1:
        #    raise Exception("Module {} not found in {}".format(submodule, server_test_manager['repos']))
        #server_hash = server_hash[0]
        #if hash != server_hash:
        #    raise ValueError("Error while processing {}: Server hash {} is not equal to submodule hash {}. You probably must upgrade the modules.".format(submodule, server_hash, hash))

    # run migration and test
    os.chdir(root_dir)
    os.chdir('modules/ommr4all-server')
    check_call([python, 'manage.py', 'migrate'])
    check_call([python, 'manage.py', 'test'])


if __name__ == "__main__":
    main()
