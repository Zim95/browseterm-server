include env.mk


# Development
dev_build:
	./scripts/development/development-build.sh $(USER_NAME) $(REPO_NAME)

dev_setup:
	./scripts/development/development-setup.sh \
		$(NAMESPACE) \
		$(HOST_DIR) \
		$(REPO_NAME) \
		$(CONTAINER_MAKER_DEVELOPMENT_HOST) \
		$(CONTAINER_MAKER_DEVELOPMENT_PORT) \
		$(CONTAINER_MAKER_CERTS_SECRET_NAME) \
		$(CERT_MANAGER_CRON_JOB_NAME) \
		$(AUTH_REDIRECT_BASE_URI) \
		$(GOOGLE_CLIENT_ID) \
		$(GOOGLE_CLIENT_SECRET) \
		$(GITHUB_CLIENT_ID) \
		$(GITHUB_CLIENT_SECRET) \
		$(REDIS_HOST) \
		$(REDIS_PORT) \
		$(REDIS_PASSWORD) \
		$(REDIS_USERNAME) \
		$(REDIS_DB) \
		$(POSTGRES_HOST) \
		$(POSTGRES_PORT) \
		$(POSTGRES_USER) \
		$(POSTGRES_PASSWORD) \
		$(POSTGRES_DB)

dev_teardown:
	./scripts/development/development-teardown.sh $(NAMESPACE)

# Production
prod_build:
	./scripts/deployment/deployment-build.sh $(USER_NAME) $(REPO_NAME)

prod_setup:
	./scripts/deployment/deployment-setup.sh \
		$(NAMESPACE) \
		$(REPO_NAME) \
		$(CONTAINER_MAKER_HOST) \
		$(CONTAINER_MAKER_PORT) \
		$(CONTAINER_MAKER_CERTS_SECRET_NAME) \
		$(CERT_MANAGER_CRON_JOB_NAME) \
		$(AUTH_REDIRECT_BASE_URI) \
		$(GOOGLE_CLIENT_ID) \
		$(GOOGLE_CLIENT_SECRET) \
		$(GITHUB_CLIENT_ID) \
		$(GITHUB_CLIENT_SECRET) \
		$(REDIS_HOST) \
		$(REDIS_PORT) \
		$(REDIS_PASSWORD) \
		$(REDIS_USERNAME) \
		$(REDIS_DB) \
		$(POSTGRES_HOST) \
		$(POSTGRES_PORT) \
		$(POSTGRES_USER) \
		$(POSTGRES_PASSWORD) \
		$(POSTGRES_DB)

prod_teardown:
	./scripts/deployment/deployment-teardown.sh $(NAMESPACE)

.PHONY: dev_build dev_setup dev_teardown prod_build prod_setup prod_teardown
