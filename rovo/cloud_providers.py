"""Feste Cloudanbieter; Datenverträge ohne Gerätewerkzeuge oder lokale Endpunkte."""

from urllib.parse import quote

PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "url": "https://api.openai.com/v1/responses",
        "models": "https://api.openai.com/v1/models",
    },
    "anthropic": {
        "name": "Anthropic · Claude",
        "url": "https://api.anthropic.com/v1/messages",
        "models": "https://api.anthropic.com/v1/models",
    },
    "google": {
        "name": "Google · Gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/",
        "models": "https://generativelanguage.googleapis.com/v1beta/models?pageSize=100",
    },
    "openrouter": {
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "models": "https://openrouter.ai/api/v1/models",
    },
    "mistral": {
        "name": "Mistral AI",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "models": "https://api.mistral.ai/v1/models",
    },
    "groq": {
        "name": "Groq",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "models": "https://api.groq.com/openai/v1/models",
    },
}


def profiles_for(value):
    """Auch frühere Dateien mit einem einzelnen OpenAI-Zugang lesen."""
    import copy

    profiles = copy.deepcopy(value.get("profiles", {}))
    provider = value.get("provider")
    if provider in PROVIDERS and provider not in profiles:
        profiles[provider] = {
            "api_key": value["api_key"],
            "model": value["model"],
            "models": [value["model"]],
        }
    return profiles


def authentication(provider, key):
    if provider == "anthropic":
        return {"headers": {"x-api-key": key, "anthropic-version": "2023-06-01"}}
    if provider == "google":
        return {"headers": {"x-goog-api-key": key}}
    return {"token": key}


def build_request(provider, model, text, prompt, schema):
    url = PROVIDERS[provider]["url"]
    if provider == "openai":
        body = {
            "model": model,
            "store": False,
            "instructions": prompt,
            "input": text,
            "max_output_tokens": 800,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "rovo_answer",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
    elif provider == "anthropic":
        body = {
            "model": model,
            "max_tokens": 800,
            "system": prompt,
            "messages": [{"role": "user", "content": text}],
            "output_config": {"format": {"type": "json_schema", "schema": schema}},
        }
    elif provider == "google":
        url += quote(model.removeprefix("models/"), safe="") + ":generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": prompt}]},
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {
                "maxOutputTokens": 800,
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        }
    else:
        body = {
            "model": model,
            "max_tokens": 800,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            "response_format": {"type": "json_object"},
        }
        if provider == "openrouter":
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "rovo_answer",
                    "strict": True,
                    "schema": schema,
                },
            }
            body["provider"] = {"require_parameters": True, "allow_fallbacks": False}
    return url, body


def response_text(provider, response):
    if provider == "openai":
        if response.get("status") != "completed":
            raise ValueError()
        return "".join(
            part["text"]
            for item in response["output"]
            if item.get("type") == "message"
            for part in item.get("content", [])
            if part.get("type") == "output_text"
        )
    if provider == "anthropic":
        if response.get("stop_reason") != "end_turn":
            raise ValueError()
        return "".join(
            part["text"] for part in response["content"] if part.get("type") == "text"
        )
    if provider == "google":
        candidate = response["candidates"][0]
        if candidate.get("finishReason") != "STOP":
            raise ValueError()
        return "".join(
            part["text"]
            for part in candidate["content"]["parts"]
            if "text" in part and not part.get("thought")
        )
    choice = response["choices"][0]
    if choice.get("finish_reason") != "stop" or choice["message"].get("tool_calls"):
        raise ValueError()
    return choice["message"]["content"]
