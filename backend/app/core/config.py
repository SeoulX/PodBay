from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # API Settings
    app_name: str = "PodBay API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Kubernetes Settings
    kubeconfig_path: str = os.path.expanduser("~/.kube/config")
    default_context: Optional[str] = None
    
    # CORS Settings
    allowed_origins: list = ["*"]
    allowed_methods: list = ["*"]
    allowed_headers: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
