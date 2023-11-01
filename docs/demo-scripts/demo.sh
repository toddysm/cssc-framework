# NOTE: The commands below use sudo because they are for Ubuntu VM on Azure

# Pull the images
sudo docker pull python:3.12.0-slim
sudo docker pull python:3.11.6-slim
sudo docker pull python:3.11.5-slim
sudo docker pull python:3.10.13-slim
sudo docker pull python:3.10.12-slim

sudo docker images

# Retag the images
sudo docker image tag python:3.12.0-slim toddysm/python:3.12
#sudo docker image tag python:3.11.6-slim toddysm/python:3.11.6-slim
sudo docker image tag python:3.11.5-slim toddysm/python:3.11
#sudo docker image tag python:3.10.13-slim toddysm/python:3.10.13-slim
sudo docker image tag python:3.10.12-slim toddysm/python:3.10

# Sign into Docker Hub
sudo docker login -u toddysm

# Push the images to Docker Hub
sudo docker push toddysm/python:3.12
sudo docker push toddysm/python:3.11
sudo docker push toddysm/python:3.10

# Sign into Azure Container Registry
sudo az login --use-device-code
sudo az acr login --name tsmacrquarantineusw2

# Trivy commands
trivy image --vuln-type os --ignore-unfixed python:3.12.0-slim
trivy image --vuln-type os --ignore-unfixed python:3.11.6-slim
trivy image --vuln-type os --ignore-unfixed python:3.11.5-slim
trivy image --vuln-type os --ignore-unfixed python:3.10.13-slim
trivy image --vuln-type os --ignore-unfixed tsmacrquarantineusw2.azurecr.io/python:3.10.12-slim | grep Total
trivy image --vuln-type os --ignore-unfixed tsmacrquarantineusw2.azurecr.io/python:3.10.12-slim-patched | grep Total

# Check the lifecycle metadata
oras login -u tsmacrquarantineusw2 tsmacrquarantineusw2.azurecr.io
# Old toddysm/python:3.10 image
# sha256:13cc673c11ee90d6ba92d95f35f4d8e59148937f1e3b4044788e93268bfe9d2e

oras manifest fetch tsmacrquarantineusw2.azurecr.io/toddysm/python@sha256:e7df7ed9bc4830fdfcc4d2924a02cb8d3070f69ce24a807b85ff66cc4d1b6838 | jq .

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


# 4. Build the sample app
docker build -t tsmacrquarantineusw2.azurecr.io/flasksample:1.0 --build-arg BASE_IMAGE="tsmacrquarantineusw2.azurecr.io/toddysm/python:3.10" .

# 5. Run the sample app
docker run -p 5050:5000 tsmacrquarantineusw2.azurecr.io/flasksample:1.0