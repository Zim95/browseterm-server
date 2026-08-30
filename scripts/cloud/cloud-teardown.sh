#!/bin/bash

# Check if enough arguments are provided
if [ $# -lt 1 ]; then
    echo "Usage: $0 <namespace>"
    exit 1
fi

YAML=./infra/cloud/cloud.yaml
NAMESPACE=$1

# Delete namespace-scoped resources with the provided namespace. envsubst placeholders other
# than NAMESPACE don't affect `kubectl delete` (it only needs kind/name/namespace to match).
echo "Deleting namespace-scoped resources in namespace $NAMESPACE..."
NAMESPACE=$NAMESPACE envsubst < "$YAML" | kubectl delete -n "$NAMESPACE" -f -
