# browseterm-server
Browseterm server

# Cloning the repository


# Dev Setup - Kubernetes
NOTE: This setup is a little different on windows. Please use WSL in windows.
    Basically, the script files wont work on windows and therefore, you need to manually setup.
    The developer of this repository hates working with windows.

1. To Develop inside kubernetes, you need to first install Docker Desktop and follow this guideline: `https://docs.docker.com/desktop/features/kubernetes/`.

2. Once `kubectl` is setup and you have the `docker-desktop` cluster ready. We can proceed further.

3. Clone this repository.
    ```
    git clone https://github.com/namahshrestha/browseterm-server.git
    ```
    This will clone the repository into a folder called `browseterm-server`. Go into the folder.
    ```
    cd browseterm-server
    ```

4. First of all, make sure `./infra/development/entrypoint-development.sh` is an executable.
    ```
    chmod +x ./infra/k8s/development/entrypoint-development.sh
    ```

4. Create an `env.mk` file with the following variables:
    ```
    REPO_NAME=<your-dockerhub-username>
    USER_NAME=<your-dockerhub-username>
    NAMESPACE=<your-namespace>
    HOST_DIR=<your-working-directory>
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
    In your text editor outside the pod (in your local machine - working directory), create a new file and save it as `test.js`. Check if that file is present in the pod.
    ```
    ls
    ```
    You should see the `test.js` file.
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
