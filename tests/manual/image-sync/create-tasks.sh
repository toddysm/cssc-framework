ACR_NAME=tsmacrquarantineusw2
ACR_TASK_NAME_COPY_IMAGE=acquire-copy-image-task
ACR_TASK_NAME_GENERATE_SBOM=acquire-generate-sbom-task
ACR_TASK_NAME_SCAN_IMAGE=acquire-scan-image-task
ACR_TASK_NAME_SIGN_IMAGE=acquire-sign-image-task

# Create acquire-copy-image-task in ACR
az acr task create -r $ACR_NAME -n $ACR_TASK_NAME_COPY_IMAGE \
    -f ../../../stages/acquire/src/image-sync/copy-image-task.yaml \
    -c /dev/null \
    --commit-trigger-enabled false \
    --base-image-trigger-enabled false

# Create acquire-generate-sbom-task in ACR
az acr task create -r $ACR_NAME -n $ACR_TASK_NAME_GENERATE_SBOM \
    -f ../../../stages/acquire/src/image-sync/generate-sbom-task.yaml \
    -c /dev/null \
    --commit-trigger-enabled false \
    --base-image-trigger-enabled false

# Create acquire-scan-image-task in ACR
az acr task create -r $ACR_NAME -n $ACR_TASK_NAME_SCAN_IMAGE \
    -f ../../../stages/acquire/src/image-sync/scan-and-patch-image-task.yaml \
    -c /dev/null \
    --commit-trigger-enabled false \
    --base-image-trigger-enabled false

# Create acquire-sign-image-task in ACR
az acr task create -r $ACR_NAME -n $ACR_TASK_NAME_SIGN_IMAGE \
    -f ../../../stages/acquire/src/image-sync/sign-image-task.yaml \
    -c /dev/null \
    --commit-trigger-enabled false \
    --base-image-trigger-enabled false