ACR_NAME=tsmacrquarantine
ACR_TASK_NAME=acquire-copy-image-task

# Create acquire-copy-image-task in ACR
az acr task create -r $ACR_NAME -n $ACR_TASK_NAME \
    -f ../../../stages/acquire/src/image-sync/copy-image-task.yaml \
    -c /dev/null \
    --commit-trigger-enabled false \
    --base-image-trigger-enabled false