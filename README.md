# OMMR4all-deploy

Deployment/Setup of all ommr4all services

## Requirements
`sudo apt install nodejs npm python3-pip virtualenv libsm6 libxrender1 libfontconfig1`
`sudo npm install npm@latest -g`
`sudo npm install -g @angular/cli`

## Python virtualenv and requirements
`virtualenv -p python3 ommr4all-venv`
`source ommr4all-venv/bin/activate`
`pip install -r modules/ommr4all-server/requirements.txt`
`cd modules/page-segmentation && python setup.py install && cd ../..`
`cd modules/ommr4all-line-detection && python setup.py install && cd ../..`
`cd modules/ommr4all-server && python managy.py collectstatic --noinput && cd ../..`

## Install
cd modules/ommr4all-client && npm install && ng build && cd ../..

## Setup apache to serve the app
`sudo apt install apache2 libapache2-mod-wsgi-py`
`sudo a2enmod wsgi`
`sudo service apache2 restart`
Create file `sudo /etc/apache2/sites-available/ommr4all.conf`
```
Listen 8001
<VirtualHost *:8001>
        ErrorLog ${APACHE_LOG_DIR}/ommr4all-error.log
        CustomLog ${APACHE_LOG_DIR}/ommr4all-access.log combined

        WSGIPassAuthorization Off
        WSGIDaemonProcess ommr4all python-home=/opt/ommr4all/ommr4all-deploy/ommr4all-venv python-path=/opt/ommr4all/ommr4all-deploy/modules/ommr4all-server
        WSGIProcessGroup ommr4all

        Alias /static /opt/ommr4all/ommr4all-deploy/modules/ommr4all-server/static
        <Directory /opt/ommr4all/ommr4all-deploy/modules/ommr4all-server/static>
                Require all granted
        </Directory>

        Alias /assets /opt/ommr4all/ommr4all-deploy/modules/ommr4all-server/static/ommr4all-client/assets
        <Directory /opt/ommr4all/ommr4all-deploy/modules/ommr4all-server/static/ommr4all-client/assets>
                Require all granted
        </Directory>

        Alias /storage /opt/ommr4all/ommr4all-deploy/modules/ommr4all-server/storage
        <Directory /opt/ommr4all/ommr4all-deploy/modules/ommr4all-server/storage>
                Require all granted
        </Directory>

        # Alias /media /opt/ommr4all/ommr4all-deploy/modules/ommr4all-server/media
        # <Directory /opt/ommr4all/ommr4all-deploy/modules/ommr4all-server/media>
        #         Require all granted
        # </Directory>

        WSGIScriptAlias / /opt/ommr4all/ommr4all-deploy/modules/ommr4all-server/ommr4all/wsgi.py
        <Directory /opt/ommr4all/ommr4all-deploy/modules/ommr4all-server/ommr4all>
                <Files wsgi.py>
                        Require all granted
                </Files>
        </Directory>
</VirtualHost>
```
Activate `sudo a2ensite ommr4all`
`sudo service apache2 restart`
