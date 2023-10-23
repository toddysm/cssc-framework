# Download and extract notation for demo.
# These steps should be replaced by building from source code.
# Currently, this demo only works for linux amd64
ARG NOTATION_VERSION=1.0.0
ARG NOTATION_ARCH=linux_amd64

FROM ubuntu as build

ARG NOTATION_VERSION
ARG NOTATION_ARCH

RUN apt-get update && apt-get install -y curl
WORKDIR /Downloads
RUN curl -Lo notation.tar.gz https://github.com/notaryproject/notation/releases/download/v{$NOTATION_VERSION}/notation_{$NOTATION_VERSION}_{$NOTATION_ARCH}.tar.gz
RUN tar xvzf notation.tar.gz

FROM ubuntu
RUN apt-get update && apt-get install -y ca-certificates libicu-dev
COPY --from=build /Downloads/notation /usr/local/bin/notation
ENTRYPOINT [ "notation" ]