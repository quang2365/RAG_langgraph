# Production LangGraph Chat API

A production-oriented chat API built with **FastAPI**, **LangGraph**, and the **DeepSeek API**. It provides a simple HTTP interface to an LLM agent, with input/output safeguards, in-memory response caching, rate limiting, structured logs, basic metrics, and optional LangSmith tracing.

**Course link:** [Link Course](https://www.youtube.com/watch?v=mHxLXzYjQRE&t=10277s)

## Features

- Asynchronous FastAPI application with interactive OpenAPI documentation.
- LangGraph-based agent that calls a DeepSeek-compatible chat model.
- Input filtering for common prompt-injection patterns and basic PII masking.
- Output checks for basic PII masking and selected unsafe content patterns.
- In-memory response cache with configurable time-to-live.
- Per-client rate limiting.
- Health, request metrics, and cache statistics endpoints.
- JSON-formatted application logs and optional LangSmith tracing.
- Docker, Docker Compose, and Render deployment configuration.

## Technology stack

- Python 3.12
- FastAPI and Uvicorn
- LangGraph, LangChain, and `langchain-openai`
- DeepSeek API (through its OpenAI-compatible endpoint)
- Pydantic Settings
- SlowAPI
- uv for dependency management

## Getting started

### Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- A DeepSeek API key

### 1. Configure environment variables

Create a local environment file from the example:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Set `DEEPSEEK_API_KEY` in `.env`. LangSmith tracing is optional; leave it disabled for local use unless you also configure your LangSmith credentials.

### 2. Install dependencies

```bash
uv sync --frozen --no-dev --no-install-project
```

### 3. Start the API

```bash
uv run --no-sync uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The service will be available at `http://127.0.0.1:8000`.

## API

Interactive API documentation is available at:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

### `POST /chat`

Send a message to the agent:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"What is LangGraph?\",\"thread_id\":\"demo\"}"
```

Example response:

```json
{
  "response": "LangGraph is a framework for building stateful, multi-step applications with language models.",
  "thread_id": "demo",
  "model_used": "primary",
  "cached": false,
  "processing_time_ms": 824.31,
  "security_note": [],
  "timestamp": "2026-01-01T12:00:00+00:00"
}
```

The `thread_id` is returned with the response and included in logs. The current agent does not use it to store or restore conversation history; each request is processed as a standalone message.

Possible errors include `400` when an input is blocked by security filters, `429` when the rate limit is exceeded, and `500` when the agent cannot process a request.

### Other endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Reports application health and component initialization status. |
| `GET` | `/metrics` | Returns process-local request, latency, token-estimate, and cache metrics. |
| `GET` | `/cache/stats` | Returns in-memory cache hit, miss, and entry statistics. |

## Configuration

Settings are read from environment variables and, for local development, from `.env`.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | Yes | — | API key for the DeepSeek-compatible model endpoint. |
| `DEEPSEEK_BASE_URL` | Yes | — | Model API base URL; for DeepSeek, use `https://api.deepseek.com`. |
| `PRIMARY_MODEL` | No | `deepseek-chat` | Primary model name. |
| `FALLBACK_MODEL` | No | `deepseek-chat` | Defined as a setting, but not currently used by the agent; its fallback client uses `PRIMARY_MODEL`. |
| `APP_ENV` | No | `development` | Application environment label. |
| `LOG_LEVEL` | No | `INFO` | Logging-level setting; the current logger is initialized at `INFO`. |
| `RATE_LIMIT` | No | `20/minute` | Per-client request limit, in SlowAPI format. |
| `CACHE_TTL_SECONDS` | No | `300` | Cache entry lifetime in seconds. |
| `MAX_RETRIES` | No | `3` | Controls whether the workflow takes its fallback branch after a primary call fails; it does not retry the primary call. |
| `LANGSMITH_TRACING` | No | `true` | Enables/disables LangSmith tracing. |
| `LANGSMITH_API_KEY` | No | — | LangSmith API key; required when tracing is enabled. |
| `LANGSMITH_PROJECT` | No | — | LangSmith project name for traces. |

> **Note:** The cache and metrics are held in process memory. They are not shared across multiple workers or instances and are reset when the process restarts. The current agent configuration also uses the primary model for both LLM clients; configure and verify distinct fallback behavior before relying on it for high availability.

## Run tests

```bash
uv run --no-sync pytest
```

## Run with Docker Compose

Make sure `.env` is configured, then run:

```bash
docker compose -f Docker-compose.yml up --build
```

The API is exposed on port `8000`. Stop the services with `Ctrl+C`; add `-d` to run Compose in the background.

To build and run the image directly:

```bash
docker build -t production-langgraph-api .
docker run --rm --env-file .env -p 8000:8000 production-langgraph-api
```

## Deploy to Render

The repository includes a [Render Blueprint](./render.yaml) that defines a Python web service and uses `/health` as its health-check path.

1. Push this repository to a Git provider supported by Render.
2. In Render, create a new Blueprint deployment and select the repository.
3. Set the secret environment variable `DEEPSEEK_API_KEY`.
4. Because tracing is enabled by the Blueprint, set `LANGSMITH_API_KEY` as well, or disable `LANGSMITH_TRACING` if you do not want to use LangSmith.
5. Deploy the service and open its generated URL. The API documentation is available at `/docs`.

The Blueprint also sets the model, environment, rate-limit, cache, retry, and LangSmith project settings. Keep API keys in Render's environment-variable settings; do not commit secrets to the repository.

## Project structure

```text
.
├── app/
│   ├── agent.py       # LangGraph agent and model calls
│   ├── cache.py       # TTL response cache
│   ├── config.py      # Environment-based settings
│   ├── main.py        # FastAPI application and routes
│   ├── models.py      # Request and response schemas
│   ├── monitoring.py  # JSON logging, metrics, and request timing
│   └── security.py    # Input/output checks and PII masking
├── tests/
│   ├── test_api.py
│   ├── test_cache.py
│   └── test_security.py
├── .env.example
├── Docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── render.yaml
└── uv.lock
```