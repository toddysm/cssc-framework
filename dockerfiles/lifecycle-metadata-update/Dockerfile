ARG VERSION="1.1.0"

FROM ubuntu as build
ARG VERSION

RUN apt-get update && apt-get install -y \
    curl

WORKDIR /Downloads

RUN curl -LO "https://github.com/oras-project/oras/releases/download/v${VERSION}/oras_${VERSION}_linux_amd64.tar.gz"
RUN mkdir -p oras-install/
RUN tar -zxf oras_${VERSION}_*.tar.gz -C oras-install/

FROM ubuntu
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /Downloads/oras-install/oras /usr/local/bin/

ADD update-lifecycle.sh update-lifecycle.sh
ENTRYPOINT [ "sh", "/update-lifecycle.sh" ]