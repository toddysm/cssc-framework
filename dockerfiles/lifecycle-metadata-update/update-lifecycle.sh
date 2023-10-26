#/bin/sh

if oras manifest fetch --descriptor $1 > /dev/null; then
    date=$(date '+%Y-%m-%dT%H:%M:%SZ')
    oras attach $1 \
        --artifact-type "application/vnd.toddysm.artifact.lifecycle" \
        --annotation "vnd.toddysm.artifact.lifecycle.eol=$date" 
else
    echo "There is no manifest for $1"
    exit 0
fi