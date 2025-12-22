#!/bin/bash

# Production entrypoint - run the application directly
poetry run uvicorn app:app --host 0.0.0.0 --port 9999
