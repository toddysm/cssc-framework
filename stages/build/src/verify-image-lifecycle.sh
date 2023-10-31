#!/bin/bash

base_image_registry=$1
base_image_repository=$2
base_image_tag=$3
base_image_digest=$4

if [ $# -lt 3 ]; then
    echo "Usage: $0 <base_image_registry> <base_image_repository> <base_image_tag> <base_image_digest>"
    exit 1
fi

if [[ $# -lt 4 ]]; then
    base_image="${base_image_registry}/${base_image_repository}:${base_image_tag}"
else
    base_image="${base_image_registry}/${base_image_repository}@${base_image_digest}"
fi

echo "Checking image lifecycle for ${base_image}..."

eol_date=`oras discover \
    --artifact-type "application/vnd.toddysm.artifact.lifecycle" \
    ${base_image} \
    -o json | \
    jq -r 'select (.manifests != null) | .manifests[0].annotations["vnd.toddysm.artifact.lifecycle.eol"]'`

tomorrows_date=$(date --date='+1 day' '+%Y-%m-%dT%H:%M:%SZ')

if [ "$eol_date" != "null" ] && [ "$eol_date" != "" ] && [ "$eol_date" != " " ]; then
    echo "Image has end of life date: ${eol_date}"
    if [[ "$eol_date" \< "$tomorrows_date" ]]; then
        echo "Base image ${base_image} has reached end of life and should not be used for builds."

        # Get the digest for the latest image from this lineage
        latest_image_digest=`oras manifest fetch \
            --descriptor \
            ${base_image_registry}/${base_image_repository}:${base_image_tag} | \
            jq -r 'select(.digest) | .digest'`
        echo "The latest image from this lineage is ${base_image_registry}/${base_image_repository}@${latest_image_digest}"
        exit 1
    else
        echo "Image has not reached end of life. Continuing..."
    fi
else
    echo "Image has no end of life date. Continuing..."
fi