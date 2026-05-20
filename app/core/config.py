"""
项目配置模块。

加载优先级: 环境变量 > .env 文件 > 代码默认值

重要：load_dotenv() 必须在最前面调用，
因为 CrewAI/litellm 直接从 os.environ 读取 API Key，
而 pydantic-settings 只把 .env 读入自己的字段，不会写回 os.environ。
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """项目配置对象。"""

    app_name: str = "Agent Hub"
    app_env: str = "dev"
    api_prefix: str = "/api/v1"

    # ── LLM 配置 ────────────────────────────────────────────
    # CrewAI 底层使用 litellm，原生支持多厂商前缀:
    #   DeepSeek:  "deepseek/deepseek-chat"      需设置 DEEPSEEK_API_KEY
    #   Qwen:      "dashscope/qwen-plus"         需设置 DASHSCOPE_API_KEY
    #   OpenAI:    "openai/gpt-4o-mini"          需设置 OPENAI_API_KEY
    crewai_llm: str = "dashscope/qwen-plus"

    # ── API Keys（load_dotenv 已将 .env 导入 os.environ）──
    # 这里声明字段是为了让 pydantic 做校验和类型提示，
    # litellm/crewai 实际从 os.environ 读取。
    deepseek_api_key: str = ""
    deepseek_api_base: str = ""
    dashscope_api_key: str = ""
    dashscope_api_base: str = ""
    openai_api_key: str = ""
    openai_api_base: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
