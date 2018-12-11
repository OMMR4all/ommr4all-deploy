# OMMR4all-deploy

Deployment/Setup of all ommr4all services

## Requirements
`sudo apt install nodejs npm python3-pip virtualenv nginx`
`sudo npm install npm@latest -g`
`sudo npm install -g @angular/cli`

## Python virtualenv and requirements
`virtualenv -p python3 ommr4all-venv`
`source ommr4all-venv/bin/activate`
`pip install -r modules/ommr4all-server/requirements.txt`
`cd modules/page-segmentation && python setup.py install && cd ../..`
`cd modules/ommr4all-line-detection && python setup.py install && cd ../..`

## Install
cd modules/ommr4all-client && npm install && ng build && cd ../..

