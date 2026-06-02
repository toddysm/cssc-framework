# Demo Applications

This directory contains three independent demo applications, each built on a
base image copied from Docker Hub and deployed to a highly scalable Kubernetes
cluster via Helm.

| App | Language | Build tool | Folder |
| --- | -------- | ---------- | ------ |
| Python web app | Python | pip | [`python-app/`](python-app/) |
| Node.js web app | Node.js | npm | [`nodejs-app/`](nodejs-app/) |
| Java web app | Java | Gradle | [`java-app/`](java-app/) |

Each application is self-contained and includes:

- Source code using language-native conventions
- A `Dockerfile` that builds on a configurable base image
- A Helm chart under `deploy/helm/` with scalable Kubernetes resources
  (Deployment, Service, Ingress, HorizontalPodAutoscaler, PodDisruptionBudget,
  ConfigMap)

> Note: This is a structural skeleton. Files are placeholders to be filled in.
