# CSSC Dashboard — local development on a kind cluster using the same Helm charts.
#
.DEFAULT_GOAL := help

# Load project-local secrets/config from .env if present (e.g. GITHUB_TOKEN).
# Lines are KEY=value; the file is gitignored. See .env.example.
ifneq (,$(wildcard .env))
include .env
export
endif

CLUSTER   ?= cssc-dashboard
NAMESPACE ?= cssc-dashboard
TAG       ?= dev
RELEASE   ?= cssc
PORT      ?= 8000
CHART     := deploy/helm/cssc-dashboard
SERVICES  := packages-service issues-service dashboard-web

VENV   := .venv
PIP    := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest

.PHONY: help
help:
	@echo "CSSC Dashboard — make targets:"
	@echo "  venv       create the local virtualenv and install all packages"
	@echo "  test       run unit tests for the library and all services"
	@echo "  lint       helm lint all charts"
	@echo "  build      build the three service images (docker)"
	@echo "  kind-up    create the kind cluster"
	@echo "  kind-down  delete the kind cluster"
	@echo "  load       load the images into the kind cluster"
	@echo "  secret     create the GitHub token Secret (needs GITHUB_TOKEN)"
	@echo "  deploy     helm upgrade --install the umbrella chart"
	@echo "  up         kind-up + build + load + secret + deploy"
	@echo "  down       delete the kind cluster"
	@echo "  forward    port-forward dashboard-web to localhost:$(PORT)"

# ---------------------------------------------------------------- local python
.PHONY: venv
venv:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e './libs/cssc_common[test]'
	for s in $(SERVICES); do $(PIP) install -e "./services/$$s[test]"; done

.PHONY: test
test:
	@set -e; for d in libs/cssc_common $(addprefix services/,$(SERVICES)); do \
	  echo "== $$d =="; ( cd "$$d" && $(abspath $(PYTEST)) -q ); \
	done

# ------------------------------------------------------------------------ helm
.PHONY: lint
lint:
	for s in $(SERVICES); do helm lint "services/$$s/deploy/helm/$$s"; done
	helm dependency build $(CHART)
	helm lint $(CHART)

# ---------------------------------------------------------------------- images
.PHONY: build
build:
	for s in $(SERVICES); do \
	  docker build -f "services/$$s/Dockerfile" -t "cssc-dashboard/$$s:$(TAG)" . ; \
	done

# ------------------------------------------------------------------------ kind
.PHONY: kind-up
kind-up:
	kind create cluster --name $(CLUSTER)

.PHONY: kind-down
kind-down:
	kind delete cluster --name $(CLUSTER)

.PHONY: load
load:
	for s in $(SERVICES); do \
	  kind load docker-image "cssc-dashboard/$$s:$(TAG)" --name $(CLUSTER); \
	done

# ---------------------------------------------------------------------- deploy
.PHONY: secret
secret:
	@test -n "$(GITHUB_TOKEN)" || { echo "GITHUB_TOKEN is not set"; exit 1; }
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	kubectl -n $(NAMESPACE) create secret generic cssc-dashboard-github \
	  --from-literal=GITHUB_TOKEN=$(GITHUB_TOKEN) \
	  --dry-run=client -o yaml | kubectl apply -f -

.PHONY: deploy
deploy:
	helm dependency build $(CHART)
	helm upgrade --install $(RELEASE) $(CHART) --namespace $(NAMESPACE) --create-namespace

.PHONY: undeploy
undeploy:
	helm uninstall $(RELEASE) --namespace $(NAMESPACE)

.PHONY: up
up: kind-up build load secret deploy

.PHONY: down
down: kind-down

.PHONY: forward
forward:
	@echo "Dashboard at http://localhost:$(PORT)"
	kubectl -n $(NAMESPACE) port-forward svc/dashboard-web $(PORT):80
