# Base Image
FROM ubuntu:18.04

ENV DEBIAN_FRONTEND=noninteractive

# Enable Networking on port 8001 (apache)
EXPOSE 8001

# Install dependencies
RUN apt-get update && apt-get install -y \
    locales \
    git \
    wget curl gnupg \
    python3-pip virtualenv libsm6 libxrender1 libfontconfig1 \
    apache2 libapache2-mod-wsgi-py3 \
    && rm -rf /var/lib/apt/lists/*

# install latest node
RUN curl -sL https://deb.nodesource.com/setup_12.x  | bash - && apt-get -y install nodejs

# setup locale
RUN locale-gen en_US.UTF-8

# setup basic npm packages
RUN npm install npm@latest -g && npm install -g @angular/cli

# basic dirs
RUN mkdir -p /opt

# clone code and all its dependencies
RUN git clone --recursive http://github.com/OMMR4all/ommr4all-deploy && cd ommr4all-deploy && git checkout docker

# setup apache
RUN cp ommr4all-deploy/ommr4all-deploy/deploy/apache2.conf /etc/apache2/sites-available/ommr4all.conf && a2ensite ommr4all.conf && apachectl configtest

# run deploy script
RUN cd ommr4all-deploy && python3 ommr4all-deploy/deploy.py --dbdir /opt/ommr4all/storage

# launch apache
CMD apachectl -D FOREGROUND
