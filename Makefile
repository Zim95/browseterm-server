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
		$(POSTGRES_HOST) \
		$(POSTGRES_PORT)

teardown:
	./scripts/cloud/cloud-teardown.sh $(NAMESPACE)

.PHONY: build setup teardown
