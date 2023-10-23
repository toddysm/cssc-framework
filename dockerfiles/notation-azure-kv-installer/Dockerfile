FROM alpine as build
RUN apk update && apk add curl
WORKDIR /workspace
RUN curl -Lo notation-azure-kv.tar.gz https://github.com/Azure/notation-azure-kv/releases/download/v1.0.1/notation-azure-kv_1.0.1_linux_amd64.tar.gz
RUN tar xvzf notation-azure-kv.tar.gz

FROM alpine
COPY --from=build /workspace/notation-azure-kv /resources/notation-azure-kv
ADD install.sh install.sh
ENTRYPOINT [ "sh", "/install.sh" ]