# Makefile para l10n-peru-ce
# Uso: make <target>

.PHONY: help up down restart logs psql shell deps deps-update test lint docs install-hooks fresh

DB ?= peru_dev
ODOO_EXEC := docker compose exec -T odoo /entrypoint.sh odoo

help: ## Listar targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ─── Stack ──────────────────────────────────────────────────────
up: ## Levantar Odoo + PG en background
	docker compose up -d
	@echo "→ http://localhost:$${ODOO_HTTP_PORT:-8169}"

down: ## Detener stack (preserva datos)
	docker compose down

restart: ## Reiniciar Odoo (tras editar odoo.conf o addons)
	docker compose restart odoo

logs: ## Tail logs de Odoo
	docker compose logs -f odoo

psql: ## psql shell a la BD activa
	docker compose exec db psql -U $${POSTGRES_USER:-odoo} -d $(DB)

shell: ## Bash shell dentro del container Odoo
	docker compose exec odoo bash

fresh: ## DESTRUCTIVO: borrar todo (BD + filestore) y empezar limpio
	docker compose down -v

# ─── Dependencias OCA ───────────────────────────────────────────
deps: ## Clonar repos OCA requeridos a oca-deps/ (branch 18.0)
	@./scripts/install_oca_deps.sh

deps-update: ## Actualizar repos OCA existentes
	@cd oca-deps && for d in */; do echo "→ $$d"; (cd $$d && git pull --ff-only); done

# ─── Módulos ────────────────────────────────────────────────────
install: ## Instalar/actualizar un módulo: make install MOD=l10n_pe_base_extras
	$(ODOO_EXEC) -d $(DB) -i $(MOD) --stop-after-init --no-http

update: ## Actualizar un módulo: make update MOD=l10n_pe_base_extras
	$(ODOO_EXEC) -d $(DB) -u $(MOD) --stop-after-init --no-http

test: ## Tests de un módulo: make test MOD=l10n_pe_base_extras
	$(ODOO_EXEC) -d $(DB) -i $(MOD) --test-enable --stop-after-init --no-http --test-tags=/$(MOD)

test-all: ## Tests de todos nuestros módulos
	@for m in addons/*/; do \
		MOD=$$(basename $$m); \
		echo "=== test $$MOD ==="; \
		$(MAKE) test MOD=$$MOD || exit 1; \
	done

# ─── Dev tooling ────────────────────────────────────────────────
install-hooks: ## Instalar pre-commit hooks (en venv local)
	pip install -r requirements-dev.txt
	pre-commit install

lint: ## Correr pre-commit en todo el repo
	pre-commit run --all-files

# ─── Docs ───────────────────────────────────────────────────────
docs: ## Servir docs en localhost:8000
	cd docs && mkdocs serve

docs-build: ## Build estático de docs en site/
	cd docs && mkdocs build
