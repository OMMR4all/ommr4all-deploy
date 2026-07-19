# Base Image
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Enable Networking on port 8001 (apache)
EXPOSE 8001

# Install system dependencies
RUN apt-get update && apt-get install -y \
    locales \
    git \
    wget curl gnupg \
    python3 python3-pip python3-venv python3-dev \
    libsm6 libxrender1 libfontconfig1 libgl1 \
    apache2 libapache2-mod-wsgi-py3 \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22 LTS
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# Setup locale
RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8

# Copy the local checkout (including submodules at their checked-out branches;
# heavy paths like storage/, node_modules/ and .git/ are excluded via .dockerignore)
WORKDIR /opt/ommr4all
COPY . /opt/ommr4all/ommr4all-deploy-src

# Setup Apache (proxy modules forward /ws to the daphne ASGI service)
RUN cp /opt/ommr4all/ommr4all-deploy-src/ommr4all-deploy/deploy/apache2.conf \
    /etc/apache2/sites-available/ommr4all.conf \
    && a2enmod proxy proxy_http proxy_wstunnel \
    && a2ensite ommr4all.conf \
    && apachectl configtest

# Run deploy script
RUN cd /opt/ommr4all/ommr4all-deploy-src \
    && python3 ommr4all-deploy/deploy.py --dbdir /opt/ommr4all/storage

# Entrypoint backs up + migrates the DB and creates the superuser (from
# DJANGO_SUPERUSER_* env vars) before handing over to Apache
RUN cp /opt/ommr4all/ommr4all-deploy/ommr4all-deploy/docker/entrypoint.sh /entrypoint.sh \
    && chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

# Launch Apache
CMD ["apachectl", "-D", "FOREGROUND"]
