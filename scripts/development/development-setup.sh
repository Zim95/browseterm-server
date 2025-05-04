#!/bin/bash

# Check if enough arguments are provided
if [ $# -lt 3 ]; then
    echo "Usage: $0 <namespace> <absolute-path-to-current-working-directory> <repo-name>"
    exit 1
fi

YAML=./infra/development/development.yaml
NAMESPACE=$1
HOSTPATH=$2
REPO_NAME=$3

export NAMESPACE=$NAMESPACE
export HOSTPATH=$HOSTPATH
export REPO_NAME=$REPO_NAME
envsubst < $YAML | kubectl apply -f -
