from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class RssSource:
    name: str
    url: str


RSS_SOURCES: list[RssSource] = [
    RssSource("OpenAI Blog", "https://openai.com/news/rss.xml"),
    RssSource("Hugging Face Blog", "https://huggingface.co/blog/feed.xml"),
    RssSource("Papers with Code", "https://paperswithcode.com/rss/latest"),
    RssSource("LangChain Blog", "https://blog.langchain.dev/rss/"),
    RssSource("Ollama Blog", "https://ollama.com/blog/rss.xml"),
    RssSource("Together AI Blog", "https://www.together.ai/blog/rss.xml"),
    RssSource("Cloudflare AI Blog", "https://blog.cloudflare.com/tag/ai/rss/"),
]

TRUSTED_RSS_SOURCES = {
    "OpenAI Blog",
    "Hugging Face Blog",
    "Papers with Code",
    "LangChain Blog",
    "Ollama Blog",
    "Together AI Blog",
    "Cloudflare AI Blog",
}


GITHUB_SEARCH_ENDPOINT = "https://api.github.com/search/repositories"
GITHUB_DEFAULT_QUERY = "language:Python topic:artificial-intelligence pushed:>={date}"


# Low-cost fallback keyword filter for local test mode.
POSITIVE_KEYWORDS = {
    "agent",
    "tool",
    "reasoning",
    "model",
    "open source",
    "benchmark",
    "inference",
    "quantization",
    "deployment",
    "github",
    "framework",
    "llm",
    "multimodal",
    "release",
    "announcing",
    "paper",
    "research",
    "benchmark",
    "inference",
    "agentic",
    "tool-calling",
    "code generation",
    "evaluation",
}

NEGATIVE_KEYWORDS = {
    "promo",
    "sale",
    "discount",
    "sponsored",
    "giveaway",
    "marketing",
}


def github_query_for_recent(days: int = 7) -> str:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    return GITHUB_DEFAULT_QUERY.format(date=since)
