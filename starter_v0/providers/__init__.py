from providers.openai_provider import OpenAIProvider
from providers.openrouter_provider import OpenRouterProvider
from providers.anthropic_provider import AnthropicProvider
from providers.gemini_provider import GeminiProvider
from providers.groq_provider import GroqProvider
from providers.cerebras_provider import CerebrasProvider


def make_provider(name: str):
    if name == "openai":
        return OpenAIProvider()
    if name == "openrouter":
        return OpenRouterProvider()
    if name == "anthropic":
        return AnthropicProvider()
    if name == "gemini":
        return GeminiProvider()
    if name == "groq":
        return GroqProvider()
    if name == "cerebras":
        return CerebrasProvider()
    raise ValueError(f"Unknown provider: {name}")
