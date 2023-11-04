# NOTE: The commands below use sudo because they are for Ubuntu VM on Azure

# Prerequisites
# 1. Delete repositories from ACR
# 2. Delete images from Docker Hub
# 3. Update the configuration in the storage account
# 4. Make sure the ACR task `acquire-sign-image-task` have identities and have access to the AKV
#       Key Vault Certificates Officer
#       Key Vault Crypto User
ssh csscadmin@csscjumpbox.westus3.cloudapp.azure.com
az login
az acr login -n tsmacrkubeconna23demousw2  # or whatever your ACR name is
docker login -u toddysm                    # or whatever your Docker Hub username is
docker pull python:3.10.12-slim
docker pull python:3.10.13-slim
clear

# Demo start

# STEP: Show that the ACR is empty
docker images

# Retag the images
docker image tag python:3.10.12-slim toddysm/python:3.10
docker images

# Push the images to Docker Hub
docker push toddysm/python:3.10
clear

# STEP: Show that DockerHub has the image

# STEP: Swith to ACR and show that the new repository is created
#       Show the repository
#       Go over each artifact
#           3.10 image
#           Referrers - source with information where the image came from
#           Referrers - SBOM created with Syft
#           Referrers - Vulnerability report created with Trivy
#           Referrers - Signature created with Notary
#           3.10-patched with SBOM and signature

oras repo ls tsmacrkubeconna23demousw2.azurecr.io
oras repo tags tsmacrkubeconna23demousw2.azurecr.io/toddysm/python
oras discover tsmacrkubeconna23demousw2.azurecr.io/toddysm/python:3.10 -o tree
oras discover tsmacrkubeconna23demousw2.azurecr.io/toddysm/python:3.10-patched -o tree

# STEP: Pull the two images 3.10 and 3.10-patched
docker pull tsmacrkubeconna23demousw2.azurecr.io/toddysm/python:3.10
docker pull tsmacrkubeconna23demousw2.azurecr.io/toddysm/python:3.10-patched
clear

# STEP: Scan the images with Trivy
trivy image \
    --vuln-type os \
    --ignore-unfixed \
    tsmacrkubeconna23demousw2.azurecr.io/toddysm/python:3.10 \
    | grep Total

trivy image --vuln-type os --ignore-unfixed tsmacrkubeconna23demousw2.azurecr.io/toddysm/python:3.10 | grep Total

# STEP: Show that this image has X number of vulnerabilities

trivy image \
    --vuln-type os \
    --ignore-unfixed \
    tsmacrkubeconna23demousw2.azurecr.io/toddysm/python:3.10-patched \
    | grep Total

clear

# STEP: Show that this image has no vulnerabilities

# STEP: Show the slides and explain what happened

# STEP: Switch to GitHub repo
#       Show the environment configuration and explain each one
#       Make sure that 3.10 is selected for base image

# STEP: Run the workflow
#       Explain each step

# STEP: Copy the digest of the patched image and store it in the BASE_IMAGE_DIGEST Github variable

trivy image --vuln-type os --ignore-unfixed tsmacrkubeconna23demousw2.azurecr.io/flaskapp:1.0 | grep Total

oras manifest fetch --descriptor tsmacrkubeconna23demousw2.azurecr.io/toddysm/python:3.10 | jq .

# STEP: Tag the new python image
docker tag python:3.10.13-slim toddysm/python:3.10

# STEP: Push the image to Docker Hub
docker push toddysm/python:3.10
clear

