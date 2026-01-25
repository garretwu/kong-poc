# Scheduler Design (Gateway to InferenceFE)

## 1. Goals and Non-Goals

### Goals
- Provide load-aware request scheduling between Kong and inference backends.
- Keep existing API shapes stable for clients.
- Support both video analysis (RT-DETR) and LLM APIs.
- Offer bounded queuing and clear overload behavior.
- Preserve streaming behavior for LLM SSE responses.

### Non-Goals
- Proxy WebSocket connections. WebSocket traffic remains direct to RT-DETR.
- Implement a persistent job queue or distributed state.
- Replace Kong plugins (auth, rate limiting, CORS).

## 2. Current Architecture Context

Existing services and routes:
- Kong routes HTTP APIs for RT-DETR (`/api/v1/video/*`) and LLMs (`/v1/chat/completions`, `/v2/chat/completions`).
- RT-DETR provides the control API and WebSocket stream for results.
- Mock LLM and vLLM expose OpenAI-compatible chat endpoints.

## 3. Scheduler Placement and Data Flow

```
Clients -> Kong -> Scheduler -> RT-DETR / Mock LLM / vLLM
                   |                |
                   +-- metrics ------+

WebSocket: Clients -> Kong -> RT-DETR (direct, not scheduled)
```

The Scheduler is a stateless HTTP service that receives requests from Kong and forwards them to appropriate backends based on load signals. WebSocket traffic is not proxied by the Scheduler.

Two deployment options:
- Direct scheduling: Scheduler routes directly to RT-DETR, Mock LLM, and vLLM using collected metrics.
- InferenceFE layer: introduce a thin inference frontend that normalizes request/response shapes, exposes unified metrics, and sits between Scheduler and backends.

## 4. Load Signals and Metrics

### RT-DETR
- Active sessions count (from session registry).
- Optional: frame processing latency and GPU utilization.

### LLM
- Inflight requests (per backend).
- Queue depth and average response time.
- Optional: token throughput and TTFT (time to first token).

### Collection Strategy
- Prefer pull-based metrics endpoints per backend (simple JSON).
- Cache metrics in the Scheduler with a short TTL (e.g., 1-5 seconds).
- If metrics are missing or stale, fall back to static weights or round-robin.

## 5. Scheduling Policy

### High-level strategy
- Use weighted least-loaded routing with per-backend capacity scores.
- Enforce a bounded queue for each backend to prevent unbounded latency.

### RT-DETR scheduling
- Primary limiter: maximum concurrent sessions.
- Secondary: average processing latency when available.

### LLM scheduling
- Primary limiter: inflight requests per backend.
- Secondary: average TTFT or recent latency.

### Overload behavior
- If all backends are over capacity, return 429 or 503.
- Optional short queue with a maximum wait time (e.g., 2-5 seconds).

## 6. Interface Contracts

### Ingress (from Kong)
- Preserve existing request paths and payloads.
- Expect API key verification to be handled by Kong.
- Pass through request headers and query parameters.

### Egress (to backends)
- Forward requests to selected backend without schema changes.
- For streaming responses, proxy SSE as-is.

### Response codes
- 200 for successful routing.
- 429/503 for overload.
- 502 for upstream failures.

## 7. Failure Modes and Backpressure

- Metrics endpoint unavailable: degrade to static routing.
- Backend timeout: mark backend unhealthy for a cool-down period.
- Queue overflow: reject with 429/503 and include retry-after.

## 8. Kong Integration

### Routing changes
- Kong routes `/api/v1/video/*`, `/v1/chat/completions`, `/v2/chat/completions` to Scheduler.
- WebSocket route `/ws` remains pointed to RT-DETR directly.

### Plugins
- Keep key-auth, rate-limiting, and CORS on Kong.
- Scheduler trusts Kong-authenticated requests.

## 9. Backend Integration Details

### RT-DETR
- Optional metrics endpoint for `active_sessions`, `avg_latency_ms`, `gpu_util`.
- Scheduler uses active session count to decide admission.

### Mock LLM
- Scheduler proxies and preserves SSE streaming.
- If no metrics, use static low capacity weight.

### vLLM
- Scheduler routes based on inflight and latency.
- Prefer vLLM if healthy and capacity available.

## 10. Observability and SLOs

- Emit scheduler decision logs (backend chosen, queue time, request id).
- Export metrics: queue depth, reject count, upstream latency, routing distribution.
- Suggested SLOs:
  - RT-DETR API p95 latency for start requests.
  - LLM TTFT p95 for streaming.

## 11. Deployment and Config

### Config
- Backend list with weights and capacity limits.
- Queue size and timeout.
- Health check interval and TTL.

### Deployment
- Add Scheduler to docker-compose as a new service.
- Optional: add InferenceFE service if normalization/metrics are needed.
- Update Kong declarative config to route through Scheduler.

## 12. Rollout Plan

- Phase 1: Shadow mode (log decisions without enforcing).
- Phase 2: Enforce capacity with conservative thresholds.
- Phase 3: Tune thresholds and enable queueing.

## 13. Security and Access Control

- Scheduler only accepts traffic from Kong network.
- No direct external exposure.
- Forward request id for traceability.

## 14. Open Questions

- Decide whether to introduce an InferenceFE layer or schedule directly to backends.
- Which metrics are feasible to expose from RT-DETR and vLLM?
- Preferred overload behavior: reject vs. short queue?
- Should the Scheduler handle per-tenant fairness or priority classes?
