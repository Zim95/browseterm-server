#!/bin/bash

# Requires two Secrets to already exist in the target namespace (same pattern as
# browseterm-db-credentials - not created by this script):
#   browseterm-db-credentials      keys: DB_USERNAME, DB_PASSWORD, DB_DATABASE
#   browseterm-internal-api-token  key:  CLOUD_INTERNAL_API_TOKEN
# e.g.: kubectl create secret generic browseterm-internal-api-token \
#         --from-literal=CLOUD_INTERNAL_API_TOKEN="$(openssl rand -hex 32)" -n <namespace>

# Check if enough arguments are provided
if [ $# -lt 7 ]; then
    echo "Usage: $0 <namespace> <repo-name> <redis-host> <redis-port> <redis-password> <redis-username> <redis-db> [postgres-host] [postgres-port]"
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
POSTGRES_HOST=${8:-browseterm-db-service}
POSTGRES_PORT=${9:-5432}

export NAMESPACE=$NAMESPACE
export REPO_NAME=$REPO_NAME
export REDIS_HOST=$REDIS_HOST
export REDIS_PORT=$REDIS_PORT
export REDIS_PASSWORD=$REDIS_PASSWORD
export REDIS_USERNAME=$REDIS_USERNAME
export REDIS_DB=$REDIS_DB
export POSTGRES_HOST=$POSTGRES_HOST
export POSTGRES_PORT=$POSTGRES_PORT
envsubst < $YAML | kubectl apply -f -
