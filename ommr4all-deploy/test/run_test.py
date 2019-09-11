from subprocess import check_call
import os
import sys
from runpy import run_path

this_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.abspath(os.path.join(this_dir, '..', '..'))
python = sys.executable
pip = os.path.join(os.path.dirname(python), 'pip')

server_test_manager = run_path(os.path.join(root_dir, 'modules', 'ommr4all-server', 'tests', 'manage_gitlab-ci.py'))


def main():
    os.chdir(root_dir)

    # setup python3 venv for server testing
    check_call([pip, 'install', 'tensorflow'])
    check_call([pip, 'install', '-r', 'modules/ommr4all-server/requirements.txt'])
    for submodule in ['ommr4all-page-segmentation', 'ommr4all-line-detection', 'ommr4all-layout-analysis', 'calamari']:
        os.chdir('modules/' + submodule)

        # check if hash = version in server is equal to the actual submodule
        hash = os.popen('git rev-parse HEAD').read().strip()
        server_hash = [repo.hash for repo in server_test_manager['repos'] if repo.name == submodule]
        if len(server_hash) != 1:
            raise Exception("Module {} not found in {}".format(submodule, server_test_manager['repos']))
        server_hash = server_hash[0]
        if hash != server_hash:
            raise ValueError("Error while processing {}: Server hash {} is not equal to submodule hash {}. You probably must upgrade the modules.".format(submodule, server_hash, hash))

        # install this version
        check_call([python, 'setup.py', 'install'])
        os.chdir(root_dir)

    # run migration and test
    os.chdir(root_dir)
    os.chdir('modules/ommr4all-server')
    check_call([python, 'manage.py', 'migrate'])
    check_call([python, 'manage.py', 'test'])


if __name__ == "__main__":
    main()
