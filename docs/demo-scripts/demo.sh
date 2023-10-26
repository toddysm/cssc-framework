

# Trivy commands
trivy image --vuln-type os --ignore-unfixed python:3.12.0-slim
trivy image --vuln-type os --ignore-unfixed python:3.11.6-slim
trivy image --vuln-type os --ignore-unfixed python:3.11.5-slim
trivy image --vuln-type os --ignore-unfixed python:3.10.13-slim
trivy image --vuln-type os --ignore-unfixed python:3.10.12-slim | grep Total
trivy image --vuln-type os --ignore-unfixed python:3.10.12-slim-patched | grep Total


# Copa commands
# 1. Scan with Trivy
trivy image \
    --vuln-type os \
    --ignore-unfixed \
    -f json \
    -o python:3.10.12-slim.json \
    python:3.10.12-slim

# 2. Run buildkit container
sudo docker run \
    --detach \
    --rm \
    --privileged \
    -p 127.0.0.1:8888:8888/tcp \
    --name buildkitd \
    --entrypoint buildkitd \
    moby/buildkit:v0.11.4 --addr tcp://0.0.0.0:8888

# 3. Patch with Copacetic container
sudo docker run \
    --net=host \
    --mount=type=bind,source=$(pwd),target=/data \
    --mount=type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock \
    ghcr.io/toddysm/cssc-framework/copacetic:1.0 docker.io/library/python:3.10.12-slim python\:3.10.12-slim.json 3.10.12-slim-patched