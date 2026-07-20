# browseterm-server
Browseterm server. This is the main backend server. Talks to the following services:
1. Container Maker - To manage containers.
2. Cert Manager - To create certificates.
3. Payment Service - To make payments.
4. Database Service - To make database requests.
5. Kafka Service - To send events for future storage.

# Cloning the repository
```
git clone --recurse-submodules https://github.com/namahshrestha/browseterm-server.git
```
This will clone the repository into a folder called `browseterm-server`. Go into the folder.
```
cd browseterm-server
```
In case you have already cloned the repository, you can update the submodules with the following command:
```
git submodule update --init --recursive
```

# Dev Setup - Kubernetes
NOTE: This setup is a little different on windows. Please use WSL in windows.
    Basically, the script files wont work on windows and therefore, you need to manually setup.
    The developer of this repository hates working with windows.

1. To Develop inside kubernetes, you need to first install Docker Desktop and follow this guideline: `https://docs.docker.com/desktop/features/kubernetes/`.

2. Once `kubectl` is setup and you have the `docker-desktop` cluster ready. We can proceed further.

3. Clone this repository. Follow the guide.

4. First of all, make sure `./infra/development/entrypoint-development.sh` is an executable.
    ```
    chmod +x ./infra/development/entrypoint-development.sh
    ```

4. Create an `env.mk` file with the following variables:
    ```
    REPO_NAME=zim95
    USER_NAME=zim95
    NAMESPACE=browseterm
    HOST_DIR=/Users/namahshrestha/test/browseterm/browseterm-server

    # CONTAINER MAKER CONFIG
    CONTAINER_MAKER_DEVELOPMENT_HOST=container-maker-development-service
    CONTAINER_MAKER_DEVELOPMENT_PORT=50052
    CONTAINER_MAKER_HOST=container-maker-service
    CONTAINER_MAKER_PORT=50052
    CONTAINER_MAKER_CERTS_SECRET_NAME=container-maker-development-service-certs

    # GOOGLE CREDENTIALS
    AUTH_REDIRECT_BASE_URI=http://localhost:9999
    GOOGLE_CLIENT_ID=<your-google-client-id>
    GOOGLE_CLIENT_SECRET=<your-google-client-secret>
    GITHUB_CLIENT_ID=<your-github-client-id>
    GITHUB_CLIENT_SECRET=<your-github-client-secret>

    # REDIS CREDENTIALS
    REDIS_HOST=browseterm-redis-service
    REDIS_PORT=6379	
    REDIS_PASSWORD=test123
    REDIS_USERNAME=namah
    REDIS_DB=0

    # POSTGRES CREDENTIALS
    POSTGRES_HOST=browseterm-pg-service
    POSTGRES_PORT=5432
    POSTGRES_USER=namah
    POSTGRES_PASSWORD=test123
    POSTGRES_DB=browseterm

    # OTHER ENVs
    CERT_MANAGER_CRON_JOB_NAME=cert-manager
    SOCKET_SSH_WSS_URL=ws://socketssh.local:8000
    INGRESS_HOST=browseterm.local.com
    SOCKET_SSH_HOST=socket-ssh.local.com
    ```

5. Run the development build script, if not already done.
    ```
    make dev_build
    ```
    This will build the docker image required for k8s development.

6. Run the development setup script.
    ```
    make dev_setup
    ```
    This will setup the development environment.

7. Get inside the pod:
    First check the pod status:
    ```
    kubectl get pods -n <your-namespace>  --watch
    ```
    You should see the pod being created and then it will be running.
    ```
    NAME                                            READY   STATUS    RESTARTS   AGE
    browseterm-server-development-f8cd46fd4-cl4ht   1/1     Running   0          9s
    ```
    Once the pod is running, get inside the pod:
    ```
    kubectl exec -it browseterm-server-development-f8cd46fd4-cl4ht -n <your-namespace> -- bash
    ```
    Now you are inside the pod.

8. Now we test if your local working directory is mounted to the pod.
    In your text editor outside the pod (in your local machine - working directory), create a new file and save it as `test.txt`. Check if that file is present in the pod.
    ```
    ls
    ```
    You should see the `test.txt` file.
    This means that your local working directory is mounted to the pod. You can make changes in your working directory and they will be reflected in the pod.
    You are free to develop the code and test the workings.

9. Now, we need to activate teh virtual env once we are inside the container.
    ```
    source $(poetry env info --path)/bin/activate
    ```

10. Install all dependencies with poetry.
    ```
    poetry install
    ```

11. Once done you can run the teardown script.
    ```
    make dev_teardown
    ```

NOTE: To run anything inside the shell, activate the virtualenv. But to run anything as a container command, we need to use `poetry run`.


# Working with dependencies
1. Adding dependencies:
    ```
    poetry add dependency
    ```

2. Adding dependencies with specific versions:
    - Add the dependency with version in the `pyproject.toml` file.
    - Then run `poetry update`.

3. Removing a dependency
    - `poetry remove <package>`


# Running tests
This repo has two separate test suites: frontend (JavaScript) and backend (Python).

## Frontend tests (Jest)
These are self-contained unit tests for the static JS. They run under the jsdom environment with the browser boundaries mocked (`fetch`, `EventSource`), so no live services are needed.
```
npm install
npx jest tests/frontend
```
Or use the configured script (equivalent to `jest`):
```
npm test
```

## Backend tests (unittest)
These are integration tests under `tests/integration/` (e.g. `containers/`, `authentication/`, `status_listener/`). They are NOT standalone unit tests: they require live dependencies (Postgres, Redis, and in some cases the running services / cluster) to be up before running them.
```
poetry install
poetry run python -m unittest discover -s tests/integration -p "test_*.py"
```
