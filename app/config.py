"""
Centralized Còiguration
Uses pydantic-settings for validated environment variables
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Setting(BaseSettings):
    
    #LLM configuration
    deepseek_api_key: str
    deepseek_base_url: str
    primary_model: str = "deepseek-chat"
    fallback_model: str = "deepseek-chat"
    
    #LangSmith
    langsmith_tracing: bool = True
    langsmith_api_key: str = ""
    langsmith_project: str = ""   
    
    #Application
    app_env: str = "development"
    log_level: str = "INFO"
    rate_limit: str = "20/minute"
    cache_ttl_seconds: int = 300
    max_retries: int = 3 
    
    model_config = SettingsConfigDict(env_file='.env',extra='ignore')
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"
@lru_cache
def get_settings() -> Setting:
    """cached settings instance - loaded once, reused everywhere"""
    return Setting()