from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Telegram
    telegram_bot_token: str = ""
    summary_chat_id: int = 0
    summary_chat_name: str = ""
    target_chat_id: str = ""
    declaration: str = ""
    additional_prompt: str = ""

    # AI providers
    google_api_key: str | None = None
    openai_api_key: str | None = None
    openai_gpt_model: str = "gpt-5"
    summary_model: str = "gemini-3-flash-preview"
    default_gemini_model: str = "gemini-3.1-pro-preview"
    default_gemini_fast_model: str = "gemini-3.1-flash-lite-preview"

    # AWS
    region_name: str = "us-east-1"
    s3_bucket_name: str = "tg-searcher-prod"
    dynamo_table_name: str = "tg-searcher-prod"

    # Config paths
    prompt_yaml_path: str = "conf/prompt.yaml"

    @property
    def target_chat_id_full(self) -> str:
        if self.target_chat_id.startswith("-100"):
            return self.target_chat_id
        return f"-100{self.target_chat_id}"


settings = Settings()
