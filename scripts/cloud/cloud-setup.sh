#!/bin/bash

# Requires three Secrets to already exist in the target namespace (same pattern as
# browseterm-db-credentials - not created by this script):
#   browseterm-db-credentials      keys: DB_USERNAME, DB_PASSWORD, DB_DATABASE
#   browseterm-internal-api-token  key:  CLOUD_INTERNAL_API_TOKEN
#   browseterm-oauth-credentials   keys: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
#                                        GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET  (P07)
# e.g.: kubectl create secret generic browseterm-internal-api-token \
#         --from-literal=CLOUD_INTERNAL_API_TOKEN="$(openssl rand -hex 32)" -n <namespace>

# Check if enough arguments are provided
if [ $# -lt 11 ]; then
    echo "Usage: $0 <namespace> <repo-name> <redis-host> <redis-port> <redis-password> <redis-username> <redis-db> <auth-redirect-base-uri> <local-callback-url> <allowed-hosts> <cloud-ingress-host> [postgres-host] [postgres-port] [snapshot-registry-repo-prefix] [expected-kube-context]"
    exit 1
fi

YAML=./infra/cloud/cloud.yaml
NAMESPACE=$1
REPO_NAME=$2
REDIS_HOST=$3
REDIS_PORT=$4
REDIS_PASSWORD=$5
REDIS_USERNAME=$6
REDIS_DB=$7
AUTH_REDIRECT_BASE_URI=$8
BROWSETERM_LOCAL_CALLBACK_URL=$9
BROWSETERM_ALLOWED_HOSTS=${10}
CLOUD_INGRESS_HOST=${11}
POSTGRES_HOST=${12:-browseterm-db-service}
POSTGRES_PORT=${13:-5432}
# P20: the real Docker Hub Organization snapshot repos get pushed under - see cloud.yaml's own
# comment at this env var. Defaults to "browseterm" (matching src/common/config.py's own
# default and the actual Docker Hub org created for this), but overridable per-deployment.
SNAPSHOT_REGISTRY_REPO_PREFIX=${14:-browseterm}
# P23 (~/browseterm/p.md's "P23" section, plan section 22: "Every script checks kube context
# before applying"): this project runs two separate k3d clusters (Cloud/Local) reachable from
# the same host - applying against the wrong one is a real, previously-unguarded mistake class
# (this exact script's own manifest change caused a live incident during P20 for an unrelated
# reason - a context guard wouldn't have caught THAT bug, but it closes off a different, real
# way to apply the wrong thing to the wrong cluster). Optional (empty = no check) so this
# doesn't break an existing call site not yet passing it.
EXPECTED_KUBE_CONTEXT=${15:-}
if [ -n "$EXPECTED_KUBE_CONTEXT" ]; then
    ACTUAL_KUBE_CONTEXT=$(kubectl config current-context)
    if [ "$ACTUAL_KUBE_CONTEXT" != "$EXPECTED_KUBE_CONTEXT" ]; then
        echo "ERROR: current kube context is '$ACTUAL_KUBE_CONTEXT', expected '$EXPECTED_KUBE_CONTEXT'. Aborting." >&2
        exit 1
    fi
fi

export NAMESPACE=$NAMESPACE
export REPO_NAME=$REPO_NAME
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
