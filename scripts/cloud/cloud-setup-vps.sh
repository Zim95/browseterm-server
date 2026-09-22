#!/bin/bash

# Production VPS variant of cloud-setup.sh - applies infra/cloud/cloud-vps.yaml (Traefik +
# cert-manager ingress) instead of cloud.yaml (nginx, local k3d only). Same three pre-existing
# Secrets are required in the target namespace - see cloud-setup.sh's own header comment for
# their exact keys.
#
# expected-kube-context is NOT optional here (unlike cloud-setup.sh) - this script's only real
# target is a shared production VM also running other live projects, so applying against the
# wrong context by accident is a much higher-stakes mistake than on a local k3d cluster.

if [ $# -lt 12 ]; then
    echo "Usage: $0 <namespace> <image> <image-pull-policy> <redis-host> <redis-port> <redis-password> <redis-username> <redis-db> <auth-redirect-base-uri> <local-callback-url> <allowed-hosts> <cloud-ingress-host> <expected-kube-context> [postgres-host] [postgres-port] [snapshot-registry-repo-prefix]"
    exit 1
fi

YAML=./infra/cloud/cloud-vps.yaml
NAMESPACE=$1
IMAGE=$2
IMAGE_PULL_POLICY=$3
REDIS_HOST=$4
REDIS_PORT=$5
REDIS_PASSWORD=$6
REDIS_USERNAME=$7
REDIS_DB=$8
AUTH_REDIRECT_BASE_URI=$9
BROWSETERM_LOCAL_CALLBACK_URL=${10}
BROWSETERM_ALLOWED_HOSTS=${11}
CLOUD_INGRESS_HOST=${12}
EXPECTED_KUBE_CONTEXT=${13}
POSTGRES_HOST=${14:-postgres.data.svc.cluster.local}
POSTGRES_PORT=${15:-5432}
SNAPSHOT_REGISTRY_REPO_PREFIX=${16:-zim95/browseterm}

if [ -z "$EXPECTED_KUBE_CONTEXT" ]; then
    echo "ERROR: expected-kube-context is required for the VPS deploy script." >&2
    exit 1
fi
ACTUAL_KUBE_CONTEXT=$(kubectl config current-context)
if [ "$ACTUAL_KUBE_CONTEXT" != "$EXPECTED_KUBE_CONTEXT" ]; then
    echo "ERROR: current kube context is '$ACTUAL_KUBE_CONTEXT', expected '$EXPECTED_KUBE_CONTEXT'. Aborting." >&2
    exit 1
fi

export NAMESPACE=$NAMESPACE
export IMAGE=$IMAGE
export IMAGE_PULL_POLICY=$IMAGE_PULL_POLICY
export REDIS_HOST=$REDIS_HOST
export REDIS_PORT=$REDIS_PORT
export REDIS_PASSWORD=$REDIS_PASSWORD
export REDIS_USERNAME=$REDIS_USERNAME
export REDIS_DB=$REDIS_DB
export AUTH_REDIRECT_BASE_URI=$AUTH_REDIRECT_BASE_URI
export BROWSETERM_LOCAL_CALLBACK_URL=$BROWSETERM_LOCAL_CALLBACK_URL
export BROWSETERM_ALLOWED_HOSTS=$BROWSETERM_ALLOWED_HOSTS
export CLOUD_INGRESS_HOST=$CLOUD_INGRESS_HOST
export POSTGRES_HOST=$POSTGRES_HOST
export POSTGRES_PORT=$POSTGRES_PORT
export SNAPSHOT_REGISTRY_REPO_PREFIX=$SNAPSHOT_REGISTRY_REPO_PREFIX
envsubst < $YAML | kubectl apply -f -
