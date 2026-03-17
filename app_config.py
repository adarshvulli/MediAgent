from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_maps_api_key: str | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None
    base_url: str = "http://localhost:8000"
    hf_model_path: str = "Qwen/Qwen3-Embedding-0.6B"
    send_whatsapp: bool = False
    whatsapp_country_code: str = "+1"
    mock_calls: bool = True
    database_url: str = "sqlite:///./app.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = ""


settings = Settings()
