# End-to-End Test Plan

## Scope
- Kong routing and auth
- RT-DETR control API + WebSocket results
- Mock LLM and vLLM chat completions (streaming and non-streaming)

## Preconditions
- Docker and Docker Compose installed
- GPU optional (if using RT-DETR/vLLM with GPU)
- Model file present at `models/rt-detr.pt`
- RTSP source available (sample `BigBuckBunny.mp4`)

## Environment Setup
1. Start services
   - `docker-compose up -d`
2. Start RTSP stream (local)
   - `ffmpeg -re -stream_loop -1 -i BigBuckBunny.mp4 -c copy -f rtsp -rtsp_transport tcp rtsp://localhost:8554/camera`

## Test Cases

### 1) Kong health and routing
- Call `GET http://localhost:8000/api/v1/video/health` with `apikey: video-api-key-001`
- Expect 200 and JSON fields: `status`, `model_loaded`, `gpu_available`, `uptime_seconds`

### 2) Start video analysis session
- `POST /api/v1/video/start` with body:
  - `stream_url: rtsp://mediamtx:8554/camera`
  - `enable_drawing: true`
- Expect 200 with `session_id` and `status` = `running` or `pending`

### 3) WebSocket results
- Connect to `ws://localhost:8000/ws/stream/{session_id}`
- Expect `stream_info` followed by `frame_result` messages
- Validate `frame_result` fields: `frame_index`, `detections`, optional `annotated_frame`

### 4) Stop analysis session
- `POST /api/v1/video/stop` with `session_id`
- Expect 200 and `status` = `stopped`

### 5) Session listing
- `GET /api/v1/video/sessions`
- Expect list with session entries and updated status

### 6) Mock LLM non-streaming
- `POST /v1/chat/completions` with `stream: false`
- Expect 200 and JSON object `chat.completion`

### 7) Mock LLM streaming
- `POST /v1/chat/completions` with `stream: true`
- Expect `text/event-stream` and final `[DONE]`

### 8) vLLM non-streaming (if enabled)
- `POST /v2/chat/completions`
- Expect 200 and `chat.completion`

## Negative/Edge Cases
- Invalid API key returns 401/403
- Invalid RTSP URL returns 400/422
- Start with unreachable stream URL returns error
- WebSocket disconnect does not crash session

## Observability
- Check Kong logs for routing
- Check RT-DETR logs for stream connect/disconnect
- Check Mock LLM logs for request handling

## Cleanup
- Stop RTSP push (ffmpeg)
- `docker-compose down`
