# adguard-tray: unofficial tray GUI for adguardvpn-cli
# Run `make` (or `make help`) to see all targets.

SHELL        := /usr/bin/env bash
.SHELLFLAGS  := -eu -o pipefail -c
.DEFAULT_GOAL := help

APP          := adguard-tray
VERSION      := $(shell sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)
BIN          := dist/$(APP)
PREFIX       ?= $(HOME)/.local
TARGET       := $(PREFIX)/bin/$(APP)
DESKTOP_APP  := $(HOME)/.local/share/applications/$(APP).desktop
DESKTOP_AUTO := $(HOME)/.config/autostart/$(APP).desktop
ARCHIVE      := $(APP)-$(VERSION)-linux-x86_64.tar.gz
SOURCES      := $(shell find adguard_tray -name '*.py') run.py pyproject.toml

# --- colours (disabled when NO_COLOR is set or output is not a terminal) -----
ifeq ($(NO_COLOR)$(shell [ -t 1 ] && echo tty),tty)
  B := \033[1m
  D := \033[2m
  R := \033[31m
  G := \033[32m
  Y := \033[33m
  C := \033[36m
  N := \033[0m
endif

info = @printf "$(C)▸$(N) %s\n" "$(1)"
ok   = @printf "$(G)✔$(N) %s\n" "$(1)"
warn = @printf "$(Y)!$(N) %s\n" "$(1)"

##@ Общее

.PHONY: help
help: ## Показать эту справку
	@printf "\n$(B)$(APP)$(N) $(D)v$(VERSION)$(N): неофициальный трей-клиент для adguardvpn-cli\n"
	@printf "\nИспользование: $(C)make$(N) $(Y)<цель>$(N)\n"
	@awk 'BEGIN {FS = ":.*##"} \
		/^##@/ { printf "\n$(B)%s$(N)\n", substr($$0, 5) } \
		/^[a-zA-Z_-]+:.*?##/ { printf "  $(C)%-14s$(N) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@printf "\nБыстрый старт: $(C)make build install autostart$(N)\n\n"

.PHONY: doctor
doctor: ## Проверить, что всё нужное установлено
	@fail=0; \
	check() { if eval "$$2" >/dev/null 2>&1; then printf "  $(G)✔$(N) %s\n" "$$1"; \
	          else printf "  $(R)✘$(N) %s $(D)%s$(N)\n" "$$1" "$$3"; fail=1; fi; }; \
	check "adguardvpn-cli"        "command -v adguardvpn-cli"        "→ https://github.com/AdguardTeam/AdGuardVPNCLI"; \
	check "uv (для сборки)"       "command -v uv"                    "→ curl -LsSf https://astral.sh/uv/install.sh | sh"; \
	check "libxcb-cursor0 (Qt)"   "{ ldconfig -p 2>/dev/null || /sbin/ldconfig -p; } | grep -q libxcb-cursor.so.0" "→ sudo apt install libxcb-cursor0"; \
	check "sudo без пароля"       "sudo -n -l $$(command -v adguardvpn-cli)" "→ иначе будет окно pkexec (см. README)"; \
	check "pkexec (fallback)"     "command -v pkexec"                "→ sudo apt install pkexec"; \
	check "$(APP) установлен"     "test -x $(TARGET)"                "→ make install"; \
	check "автозапуск включён"    "test -f $(DESKTOP_AUTO)"          "→ make autostart"; \
	echo; [ $$fail -eq 0 ] && printf "$(G)Всё готово$(N)\n" || printf "$(Y)Есть что доустановить (см. выше)$(N)\n"

##@ Разработка

.PHONY: deps
deps: ## Установить зависимости в .venv (uv sync)
	$(call info,uv sync)
	@uv sync --quiet
	$(call ok,зависимости установлены)

.PHONY: run
run: deps ## Запустить из исходников
	$(call info,запуск $(APP) из исходников (Ctrl+C для выхода))
	@uv run $(APP)

.PHONY: test
test: deps ## Прогнать тесты
	$(call info,pytest)
	@uv run pytest -q

##@ Сборка и установка

.PHONY: build
build: $(BIN) ## Собрать один бинарник dist/adguard-tray

$(BIN): $(SOURCES) uv.lock
	@$(MAKE) --no-print-directory test
	$(call info,сборка бинарника PyInstaller…)
	@uv run pyinstaller --noconfirm --clean --onefile --windowed --log-level WARN \
		--name $(APP) --exclude-module tkinter run.py
	@printf "$(G)✔$(N) готово: $(BIN) (%s)\n" "$$(du -h $(BIN) | cut -f1)"

.PHONY: install
install: $(BIN) ## Установить в ~/.local/bin и добавить в меню приложений
	$(call info,установка в $(TARGET))
	@install -Dm755 $(BIN) $(TARGET)
	@mkdir -p $(dir $(DESKTOP_APP))
	@$(call desktop_entry,$(TARGET)) > $(DESKTOP_APP)
	$(call ok,установлено; запуск: $(APP) или через меню приложений)
	@case ":$$PATH:" in *":$(PREFIX)/bin:"*) ;; *) printf "$(Y)!$(N) $(PREFIX)/bin нет в PATH\n";; esac

.PHONY: autostart
autostart: ## Включить автозапуск при входе (сразу в трей)
	@test -x $(TARGET) || printf "$(Y)!$(N) $(TARGET) не найден: сначала make install\n"
	@mkdir -p $(dir $(DESKTOP_AUTO))
	@$(call desktop_entry,$(TARGET) --hidden) > $(DESKTOP_AUTO)
	$(call ok,автозапуск включён)

.PHONY: no-autostart
no-autostart: ## Выключить автозапуск
	@rm -f $(DESKTOP_AUTO)
	$(call ok,автозапуск выключен)

.PHONY: uninstall
uninstall: no-autostart ## Удалить бинарник и пункт меню (конфиг остаётся)
	@pkill -x $(APP) 2>/dev/null && printf "$(C)▸$(N) запущенный $(APP) остановлен\n" || true
	@rm -f $(TARGET) $(DESKTOP_APP)
	$(call ok,удалено; конфиг: ~/.config/$(APP)/)

.PHONY: dist
dist: $(BIN) ## Собрать архив для GitHub Releases
	$(call info,упаковка $(ARCHIVE))
	@tar -czf $(ARCHIVE) --transform 's,^,$(APP)-$(VERSION)/,' \
		-C dist $(APP) -C .. LICENSE README.md README.en.md THIRD_PARTY.md
	@sha256sum $(ARCHIVE) > $(ARCHIVE).sha256
	$(call ok,$(ARCHIVE) + .sha256)

.PHONY: release
release: ## Поставить тег v<версия> и запустить сборку релиза на GitHub
	@git diff --quiet && git diff --cached --quiet || { printf "$(R)✘$(N) есть незакоммиченные изменения\n"; exit 1; }
	@git rev-parse -q --verify refs/tags/v$(VERSION) >/dev/null && { printf "$(R)✘$(N) тег v$(VERSION) уже есть: поднимите version в pyproject.toml\n"; exit 1; } || true
	$(call info,тег v$(VERSION) → origin)
	@git tag -a v$(VERSION) -m "v$(VERSION)"
	@git push origin HEAD v$(VERSION)
	$(call ok,GitHub Actions соберёт релиз: $(shell git remote get-url origin | sed -E 's#git@github.com:#https://github.com/#; s#\.git$$##')/actions)

.PHONY: clean
clean: ## Удалить артефакты сборки
	@rm -rf build dist *.spec .pytest_cache $(APP)-*.tar.gz*
	@find . -name __pycache__ -not -path './.venv/*' -exec rm -rf {} +
	$(call ok,чисто)

# --- helpers ------------------------------------------------------------------
desktop_entry = printf '%s\n' '[Desktop Entry]' 'Type=Application' 'Name=AdGuard VPN Tray' 'Comment=Unofficial tray GUI for adguardvpn-cli' 'Exec=$(1)' 'Icon=network-vpn' 'Terminal=false' 'Categories=Network;' 'StartupNotify=false'
