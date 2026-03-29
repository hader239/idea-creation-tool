from agents import ModelRetrySettings, WebSearchTool, retry_policies

web_search = WebSearchTool(search_context_size="high")

retry_settings = ModelRetrySettings(
    max_retries=5,
    backoff={
        "initial_delay": 1.0,
        "max_delay": 120.0,
        "multiplier": 2.0,
        "jitter": True,
    },
    policy=retry_policies.any(
        retry_policies.provider_suggested(),
        retry_policies.retry_after(),
        retry_policies.http_status([429, 500, 502, 503]),
    ),
)
