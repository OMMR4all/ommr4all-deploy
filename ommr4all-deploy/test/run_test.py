from subprocess import check_call
import os
import sys

this_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.abspath(os.path.join(this_dir, '..', '..'))
python = sys.executable
pip = os.path.join(os.path.dirname(python), 'pip')


def main():
    os.chdir(root_dir)

    # setup python3 venv for server testing
    check_call([pip, 'install', 'tensorflow'])
    check_call([pip, 'install', '-r', 'modules/ommr4all-server/requirements.txt'])
    for submodule in ['page-segmentation', 'ommr4all-line-detection', 'ommr4all-layout-analysis']:
        os.chdir('modules/' + submodule)
        check_call([python, 'setup.py', 'install'])
        os.chdir(root_dir)

    # run migration and test
    os.chdir(root_dir)
    os.chdir('modules/ommr4all-server')
    check_call([python, 'manage.py', 'migrate'])
    check_call([python, 'manage.py', 'test'])


if __name__ == "__main__":
    main()
