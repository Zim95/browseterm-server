#!/bin/bash

# Check if enough arguments are provided
if [ $# -lt 1 ]; then
    echo "Usage: $0 <namespace>"
    exit 1
fi

YAML=./infra/development/development.yaml
NAMESPACE=$1

# Delete namespace-scoped resources with the provided namespace
echo "Deleting namespace-scoped resources in namespace $NAMESPACE..."
envsubst < "$YAML" | kubectl delete -n "$NAMESPACE" -f -
