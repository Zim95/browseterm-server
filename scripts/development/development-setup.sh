#!/bin/bash

# Check if enough arguments are provided
if [ $# -lt 3 ]; then
    echo "Usage: $0 <namespace> <absolute-path-to-current-working-directory> <repo-name> <google-client-id> <google-client-secret> <github-client-id> <github-client-secret> <redis-host> <redis-port> <redis-password> <redis-username> <redis-db> <postgres-host> <postgres-port> <postgres-user> <postgres-password> <postgres-db>"
    exit 1
fi

YAML=./infra/development/development.yaml
NAMESPACE=$1
HOSTPATH=$2
REPO_NAME=$3
AUTH_REDIRECT_BASE_URI=$4
GOOGLE_CLIENT_ID=$5
GOOGLE_CLIENT_SECRET=$6
GITHUB_CLIENT_ID=$7
GITHUB_CLIENT_SECRET=$8
REDIS_HOST=$9
REDIS_PORT=${10}
REDIS_PASSWORD=${11}
REDIS_USERNAME=${12}
REDIS_DB=${13}
POSTGRES_HOST=${14}
POSTGRES_PORT=${15}
POSTGRES_USER=${16}
POSTGRES_PASSWORD=${17}
POSTGRES_DB=${18}

export NAMESPACE=$NAMESPACE
export HOSTPATH=$HOSTPATH
export REPO_NAME=$REPO_NAME
export AUTH_REDIRECT_BASE_URI=$AUTH_REDIRECT_BASE_URI
export GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID
export GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET
export GITHUB_CLIENT_ID=$GITHUB_CLIENT_ID
export GITHUB_CLIENT_SECRET=$GITHUB_CLIENT_SECRET
export REDIS_HOST=$REDIS_HOST
export REDIS_PORT=$REDIS_PORT
export REDIS_PASSWORD=$REDIS_PASSWORD
export REDIS_USERNAME=$REDIS_USERNAME
export REDIS_DB=$REDIS_DB
export POSTGRES_HOST=$POSTGRES_HOST
export POSTGRES_PORT=$POSTGRES_PORT
export POSTGRES_USER=$POSTGRES_USER
export POSTGRES_PASSWORD=$POSTGRES_PASSWORD
export POSTGRES_DB=$POSTGRES_DB
envsubst < $YAML | kubectl apply -f -
