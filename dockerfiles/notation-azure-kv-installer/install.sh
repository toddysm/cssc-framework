#/bin/sh

TARGET_FOLDER="$HOME/.config/notation/plugins/azure-kv"
TARGET_PATH="$TARGET_FOLDER/notation-azure-kv"

echo "Installing notation-azure-kv plugin..."
echo "Target path: $TARGET_PATH"
mkdir -p $TARGET_FOLDER
cp /resources/notation-azure-kv $TARGET_PATH