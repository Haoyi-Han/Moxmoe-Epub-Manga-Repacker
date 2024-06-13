# Declare variables
PYTHON = python
NUITKA = -m nuitka3
PRODUCT_NAME = "Moxmoe Repacker"
PROGRAM_NAME = "moxmoe-repacker"
WORK_DIR = ./
BUILD_DIR = ./build
BUILD_SYS ?= "poetry"
ICON_DIR = ./favicon.ico
FLAGS = --show-scons --show-memory --show-progress --onefile --nofollow-imports --follow-import-to=moe_utils --output-filename=$(PROGRAM_NAME) --output-dir=$(BUILD_DIR) --enable-plugin="upx"
MAIN_SCRIPT = ./main.py

# Check System Environment
ifeq ($(OS), Windows_NT)
	SHELL := pwsh.exe
	.SHELLFLAGS := -NoProfile -WorkingDirectory $(WORK_DIR) -Command
else
	SHELL := /bin/sh
endif

# Define Banner
VERSION := $(cat .version)
define ANNOUNCE_BODY

  __  __                                ____                       _             
 |  \/  | _____  ___ __ ___   ___   ___|  _ \ ___ _ __   __ _  ___| | _____ _ __ 
 | |\/| |/ _ \ \/ / '_ ` _ \ / _ \ / _ \ |_) / _ \ '_ \ / _` |/ __| |/ / _ \ '__|
 | |  | | (_) >  <| | | | | | (_) |  __/  _ <  __/ |_) | (_| | (__|   <  __/ |   
 |_|  |_|\___/_/\_\_| |_| |_|\___/ \___|_| \_\___| .__/ \__,_|\___|_|\_\___|_|   
                                                 |_|                             


Moxmoe Repacker Makefile $(VERSION)
================================================================

endef
export ANNOUNCE_BODY

# Declare phony targets
.PHONY: help build clean

help: ## Show this help message
ifeq ($(OS), Windows_NT)
	@./make.ps1 help
else
	@echo "$$ANNOUNCE_BODY"
	@printf "\033[36m%-30s %s\033[0m\n" "help" "Show this help message."
	@printf "\033[36m%-30s %s\033[0m\n" "build [BUILD_SYS=poetry, pixi]" "Build python project to one-file executable."
	@printf "\033[36m%-30s %s\033[0m\n" "clean" "Clean build directory."
endif

build: ## Build python project to one-file executable
ifeq ($(OS), Windows_NT)
	@./make.ps1 build -e $(BUILD_SYS)
else
	$(BUILD_SYS) run $(PYTHON) $(NUITKA) $(FLAGS) $(MAIN_SCRIPT)
endif
	
clean: ## Clean build directory
ifeq ($(OS), Windows_NT)
	./make.ps1 clean
else
	@rm -rf $(BUILD_DIR)/*
endif