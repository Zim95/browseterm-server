include env.mk


# Cloud control plane (this repo is Cloud-only as of P06 - see README.md).
build:
	./scripts/cloud/cloud-build.sh $(USER_NAME) $(REPO_NAME)

setup:
	./scripts/cloud/cloud-setup.sh \
		$(NAMESPACE) \
		$(REPO_NAME) \
		$(REDIS_HOST) \
		$(REDIS_PORT) \
		$(REDIS_PASSWORD) \
		$(REDIS_USERNAME) \
		$(REDIS_DB) \
		$(AUTH_REDIRECT_BASE_URI) \
		$(BROWSETERM_LOCAL_CALLBACK_URL) \
		$(BROWSETERM_ALLOWED_HOSTS) \
		$(CLOUD_INGRESS_HOST) \
		$(POSTGRES_HOST) \
		$(POSTGRES_PORT) \
		$(SNAPSHOT_REGISTRY_REPO_PREFIX)

teardown:
	./scripts/cloud/cloud-teardown.sh $(NAMESPACE)

.PHONY: build setup teardown
