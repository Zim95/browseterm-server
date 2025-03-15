#!/bin/bash

# Check if enough arguments are provided
if [ $# -lt 2 ]; then
    echo "Usage: $0 <docker-username> <docker-repository>"
    exit 1
fi

# Read arguments
USERNAME=$1
REPOSITORY=$2
# Image details
IMAGE_NAME=browseterm-server-development
IMAGE_TAG=latest
DOCKERFILE=./infra/development/Dockerfile.development

# docker login
docker login -u $USERNAME

# Build image
docker image build --no-cache -t $IMAGE_NAME:$IMAGE_TAG -f $DOCKERFILE .

# Tag image
docker image tag $IMAGE_NAME:$IMAGE_TAG $REPOSITORY/$IMAGE_NAME:$IMAGE_TAG

# Push image
docker push $REPOSITORY/$IMAGE_NAME:$IMAGE_TAG
