# Build the Copacetic container
docker build -t ghcr.io/toddysm/cssc-framework/copacetic:1.0 --build-arg copa_version=0.5.1 --no-cache .