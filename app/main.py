"""
Prodction-Ready FastAPI + Langgraph Application

wires together:
- Securty pipline (input sanitization, PII masking)
- Response caching 
- Rate limiting (slowapi)
- LangGraph agent (with retries + fallback)
- Structured logging + mestrics
- Langsmith tracing
- Health checks
"""
import time
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded 
from langsmith import traceable
from dotenv import load_dotenv

from app.config import get_settings
from app.models import ChatRequest, ChatResponse, HealthResponse, MetricsResponse, ErrorResponse
from app.security import SecurityPipeline
from app.cache import ResponseCache
from app.monitoring import get_logger, MetricsCollector, RequestTimer
from app.agent import ProductionAgent

load_dotenv()

settings = get_settings()
security : SecurityPipeline = None
cache: ResponseCache = None
metrics: MetricsCollector = None
agent: ProductionAgent = None
logger = get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize all components on startup, clean up on shutdown
    """
    global security, cache, metrics, agent
    
    logger.info("Starting production API...",extra={"extra_data":{
        "enviroment" : settings.app_env,
        "primary_model" : settings.primary_model,
        "tracing_enabled" : settings.langsmith_tracing
    }})
    
    security = SecurityPipeline()
    cache = ResponseCache(ttl_seconds=settings.cache_ttl_seconds)
    metrics = MetricsCollector()
    agent = ProductionAgent()
    
    logger.info("All components initalized. Ready to serve requests.")
    
    yield
    
    logger.info("Shutting down...", extra = {"extra_data": metrics.stats})
    
#======= Rate Limit Setup ===============    
limiter = Limiter(key_func=get_remote_address)

#====== FastAPI App =================
app = FastAPI(
    title="Production LangGraph API",
    description="A prodction-ready chat api with security, caching, and observability",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter


async def rate_limit_handler(request : Request, exc : RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded errors"""
    
    logger.warning("Rate limit exceeded",
                   extra ={"extra_data" : {
                       "client_ip" : get_remote_address(request),
                       "path": request.url.path,
                       "method": request.method
                   }}
            )
    return JSONResponse(
        status_code=429,
        content={
            "error" : "rate_limit_exceeded",
            "message" : "Too many requests, Please try again later.",
            "path": request.url.path,
        },
        headers={"Retry-After" : "60"}
    )
    
app.add_exception_handler(
    RateLimitExceeded,
    rate_limit_handler,
)

@app.post("/chat", response_model=ChatResponse)
@limiter.limit(get_settings().rate_limit)
@traceable(name="chat_endpoint")
async def chat(request: Request, body: ChatRequest):
    """
    Main chat endpoint.
    
    Flow:
    1.Security check (injection + PII masking)
    2.Cache lookup
    3.LangGraph agent invoke (if cache miss)
    4.Output validation
    5.Cache store
    6.Return response
    """
    
    with RequestTimer() as timer:
        security_notes = []
        
        is_allowed, cleaned_message, notes = security.check_input(body.message)
        security_notes.extend(notes)
        
        if not is_allowed:
            logger.warning("Request bloced by security", extra = {"extra_data": {
                "reason": notes,
                "thread_id": body.thread_id
            }})
            metrics.record_request(latency_ms=0, error=True)
            raise HTTPException(
                status_code=400,
                detail="Your message was blocked by our security filters."
            )
        cached_response = cache.get(cleaned_message)
        if cached_response:
            metrics.record_request(latency_ms=0,cache_hit=True)
            logger.info("cache hit", extra = {"extra_data": {
                "thread_id": body.thread_id
            }})
            return ChatResponse(
                response=cached_response,
                thread_id=body.thread_id,
                model_used='cached',
                cached=True,
                security_note=security_notes,
                processing_time_ms=0,
            )
        try:
            result = agent.invoke(cleaned_message)
        except Exception as e:
            logger.error(f"Agent invocation failed: {e}", extra={"extra_data":{
                "thread_id": body.thread_id,
                "error": str(e)
            }})
            metrics.record_request(latency_ms=0,error=True)
            raise HTTPException(
                status_code=500,
                detail="An error occurred while processing your request."
            )
        response_text = result["response"]
        model_used = result["model_used"]
        
        validation_response, output_warnings = security.check_output(response_text)
        security_notes.extend(output_warnings)
        
        cache.set(cleaned_message,validation_response)
        
    input_tokens = int(len(cleaned_message.split())*1.3)            
    output_tokens = int(len(validation_response.split())*1.3)            
    timeout = round(timer.elapsed_ms,2)
    metrics.record_request(
        latency_ms=timeout,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_hit=False
    )
    logger.info("Request complete", extra = {"extra_data":{
        "thread_id" : body.thread_id,
        "model_used" : model_used,
        "lantency_ms" : timeout
    }})
    return ChatResponse(
        response=validation_response,
        thread_id=body.thread_id,
        model_used=model_used,
        cached=False,
        security_note= security_notes,
        processing_time_ms=timeout
    )
@app.get("/health", response_model=HealthResponse)
async def health():
    """
    Health check for Docker/Kubernetes
    """
    settings = get_settings()
    
    checks = {
        "agent": agent is not None,
        "security": security is not None,
        "cache": cache is not None
    }
    
    all_healthy = all(checks.values())
    
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        environment=settings.app_env,
        checks=checks  
    )
@app.get("/metrics",response_model=MetricsResponse)
async def get_metrics():
    """Metrics for monitoring dashboards"""
    summary = metrics.stats
    return MetricsResponse(**summary)

@app.get("/cache/stats")
async def cache_stats():
    """
    Cache performance statistics.
    """
    return cache.stats