# OMMR4all-deploy

Deployment/Setup of all ommr4all services

## Deployment-Setup with Docker
You can setup OMMR4all using [`docker`](https://www.docker.com/) and `docker-compose`.

### Initial setup
1. Download and install `docker-ce` and `docker-compose` for your platform.
2. Download the [`docker-compose.yml`](https://github.com/OMMR4all/ommr4all-deploy/blob/master/docker-compose.yml) file.
3. Open `docker-compose.yml` and replace `${STORAGE}` and the `${PORT}` to your wishes (e.g., use `/opt/ommr4all-storage` and `8001`).
4. Build the container and bring it up:
```shell script
docker-compose up -d
```
5. Create a super user:
```shell script
docker-compose run /opt/ommr4all/ommr4all-deploy-venv/bin/python /opt/ommr4all/ommr4all-deploy/modules/ommr4all-server/manage.py createsuperuser
```

### Updating
1. `docker-compose pull`
2. `docker-compuse up`

You can run `docker image prune -f` to clean all previous versions or older images that are currently unused.

## Deployment-Setup without docker

Follow the instructions in the `Dockerfile`.
You can also setup a `gitlab-runner` for automatic deployment (Clone the project on github.com with CI-integration), create a runner with either
* `deployment-production`: redeploy if a new (version) tag was added
* `deployment-master`: redeploy if the master is updated

## Development-Setup (Any operating system)

These instructions are not complete yet.

1. Download and install all requirements (node>=10, >=python3.6)
2. Install the IDEs (IntelliJ, or PyCharm and WebStorm)
3. Create a virtual environment, activate it, and install your desired tensorflow version (e.g., `pip install tensorflow_gpu<2`)
4. Install all python submodules (located in the `modules` directure) but the server: `python setup.py install`.
5. Install the server `requirements.txt`: `pip install -r requirements.txt`.
6. Open the ommr4all-client directory in WebStorm and launch the `Angluar CLI Server`.
7. Open the ommr4all-sever directory in PyCharm and launch the `Django Server`.
8. In WebStorm launch the `Angular Application` which will open a browser.
