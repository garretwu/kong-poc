.PHONY: help up down logs build test clean mock-run mock-test vllm-run vllm-test vllm-kong-test
.PHONY: rtdetr-run rtdetr-test rtdetr-build rtdetr-logs rtdetr-health rtdetr-push-test

# Colors for output
RED = \033[31m
GREEN = \033[32m
YELLOW = \033[33m
RESET = \033[0m

help:  ## Show this help message
	@echo ""
	@echo "Kong POC - Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | while read -r line; do \
		cmd=$${line%%:*}; \
		desc=$${line##*## }; \
		printf "  ${GREEN}%-20s${RESET} %s\n" "$$cmd" "$$desc"; \
	done
	@echo ""

up:  ## Start all services
	@echo "${YELLOW}Starting all services...${RESET}"
	docker compose up -d

down:  ## Stop all services
	@echo "${YELLOW}Stopping all services...${RESET}"
	docker compose down

logs:  ## Show logs for all services
	@echo "${YELLOW}Showing logs...${RESET}"
	docker compose logs -f

build:  ## Rebuild and start services
	@echo "${YELLOW}Rebuilding and starting services...${RESET}"
	docker compose build --no-cache && docker compose up -d

restart:  ## Restart all services
	@echo "${YELLOW}Restarting services...${RESET}"
	docker compose restart

clean:  ## Stop and remove all containers, networks
	@echo "${YELLOW}Cleaning up...${RESET}"
	docker compose down --volumes --remove-orphans

mock-run:  ## Run mock-llm service locally (not in Docker)
	@echo "${YELLOW}Starting mock-llm locally on port 8000...${RESET}"
	cd upstream/mock-llm && python -m uvicorn app:app --host 0.0.0.0 --port 8000

mock-test:  ## Run unit tests for mock-llm
	@echo "${YELLOW}Running unit tests...${RESET}"
	cd upstream/mock-llm && python -m pytest -v

vllm-run:  ## Run vllm service locally on port 8100
	@echo "${YELLOW}Starting vLLM locally on port 8100...${RESET}"
	bash -c "source /home/garywu/workspace/edge-vllm-demo/.venv/bin/activate && cd upstream/vllm && python -m uvicorn app:app --host 0.0.0.0 --port 8100"

vllm-test:  ## Run unit tests for vllm
	@echo "${YELLOW}Running vLLM unit tests...${RESET}"
	bash -c "source /home/garywu/workspace/edge-vllm-demo/.venv/bin/activate && cd upstream/vllm && python -m pytest -v"

test: mock-test  ## Run unit tests (alias)

install-deps:  ## Install Python dependencies for testing
	@echo "${YELLOW}Installing Python dependencies...${RESET}"
	cd upstream/mock-llm && pip install -r requirements.txt

health:  ## Check service health
	@echo "${YELLOW}Checking mock-llm (port 9000)...${RESET}"
	@curl -s http://localhost:9000/healthz && echo " ✓" || echo "${RED}✗ mock-llm not available${RESET}"
	@echo "${YELLOW}Checking Kong admin API...${RESET}"
	@curl -s http://localhost:8001/services | grep -q "llm-service" && \
		echo " ✓ Kong has llm-service configured" || \
		echo "${RED}✗ Kong not ready${RESET}"
	@echo "${YELLOW}Testing proxy endpoint...${RESET}"
	@curl -s -H "x-api-key: demo-key" http://localhost:8000/v1/chat/completions \
		-H "Content-Type: application/json" \
		-d '{"messages":[{"role":"user","content":"test"}]}' | grep -q "Echo: test" && \
		echo " ✓ Proxy working" || \
		echo "${RED}✗ Proxy test failed${RESET}"

vllm-kong-test:  ## Test vLLM through Kong proxy (streaming)
	@echo "${YELLOW}Testing vLLM through Kong on /v2/chat/completions...${RESET}"
	@curl -s -N -H "x-api-key: demo-key" http://localhost:8000/v2/chat/completions \
		-H "Content-Type: application/json" \
		-d '{"messages":[{"role":"user","content":"Tell me a short story."}],"stream":true}'

# ==================== RT-DETR Service ====================
rtdetr-run:  ## Run RT-DETR service locally (not in Docker)
	@echo "${YELLOW}Starting RT-DETR service locally on port 8081...${RESET}"
	@if [ ! -f "upstream/rt-detr/models/rt-detr.pt" ]; then \
		echo "${RED}Error: Model file not found at upstream/rt-detr/models/rt-detr.pt${RESET}"; \
		echo "Please download the model first:"; \
		echo "  mkdir -p upstream/rt-detr/models"; \
		echo "  wget -O upstream/rt-detr/models/rt-detr.pt <model-url>"; \
		exit 1; \
	fi
	cd upstream/rt-detr && python -m uvicorn app.main:app --host 0.0.0.0 --port 8081

rtdetr-test:  ## Run unit tests for RT-DETR
	@echo "${YELLOW}Running RT-DETR unit tests...${RESET}"
	cd upstream/rt-detr && python -m pytest -v

rtdetr-build:  ## Build RT-DETR Docker image
	@echo "${YELLOW}Building RT-DETR Docker image...${RESET}"
	docker build -t rtdetr-service ./upstream/rt-detr

rtdetr-logs:  ## Show RT-DETR service logs
	@echo "${YELLOW}Showing RT-DETR service logs...${RESET}"
	docker logs -f rt-detr-service

rtdetr-health:  ## Check RT-DETR service health
	@echo "${YELLOW}Checking RT-DETR service health...${RESET}"
	@curl -s http://localhost:8081/api/v1/video/health && echo " ✓" || \
		(echo "${RED}✗ RT-DETR not available on port 8081${RESET}" && \
		 echo "Try running 'make rtdetr-run' first")

rtdetr-kong-health:  ## Check RT-DETR through Kong proxy
	@echo "${YELLOW}Checking RT-DETR through Kong...${RESET}"
	@curl -s -H "X-API-Key: video-api-key-001" http://localhost:8000/api/v1/video/health && echo " ✓" || \
		echo "${RED}✗ RT-DETR through Kong not available${RESET}"

rtdetr-push-test:  ## Push test video to RTSP (requires ffmpeg and test.mp4)
	@echo "${YELLOW}Pushing test.mp4 to MediaMTX RTSP...${RESET}"
	@if [ ! -f "test.mp4" ]; then \
		echo "${RED}Error: test.mp4 not found. Please download a test video first.${RESET}"; \
		exit 1; \
	fi
	@echo "${YELLOW}Starting FFmpeg push (Ctrl+C to stop)...${RESET}"
	ffmpeg -re -i test.mp4 -c copy -f rtsp -rtsp_transport tcp rtsp://localhost:8554/camera

rtdetr-all-up:  ## Start all services (MediaMTX, Kong, RT-DETR)
	@echo "${YELLOW}Starting all services...${RESET}"
	docker compose up -d

rtdetr-all-down:  ## Stop all services
	@echo "${YELLOW}Stopping all services...${RESET}"
	docker compose down

rtdetr-all-logs:  ## Show logs for all services
	@echo "${YELLOW}Showing all service logs...${RESET}"
	docker compose logs -f

# ==================== Download Helpers ====================
download-model:  ## Download RT-DETR model
	@echo "${YELLOW}Downloading RT-DETR model...${RESET}"
	@mkdir -p upstream/rt-detr/models
	@wget -q -O upstream/rt-detr/models/rt-detr.pt \
		"https://github.com/ultralytics/assets/releases/download/v8.2.0/rtdetr-l.pt" && \
		echo "${GREEN}Model downloaded successfully!${RESET}" || \
		echo "${RED}Failed to download model. Please check your network connection.${RESET}"

download-test-video:  ## Download sample test video
	@echo "${YELLOW}Downloading test video...${RESET}"
	@wget -q -O test.mp4 \
		"https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4" && \
		echo "${GREEN}Test video downloaded!${RESET}" || \
		echo "${RED}Failed to download test video.${RESET}"
