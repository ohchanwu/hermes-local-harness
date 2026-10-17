"""Translation between Hermes chat-completion shapes and runtime/MCP shapes."""
import copy
import re
from types import SimpleNamespace

from .errors import ProviderError


def convert_tools(tools):
    """Convert the caller's function tools to MCP declarations."""
    if tools is None:
        return []
    if not isinstance(tools, list):
        raise ProviderError("tools must be a list of functions")
    converted, names = [], set()
    for tool in tools:
        if not isinstance(tool, dict) or tool.get("type") != "function" or set(tool) != {"type", "function"}:
            raise ProviderError("only function tools are supported")
        fn = tool["function"]
        if not isinstance(fn, dict) or set(fn) - {"name", "description", "parameters", "strict"}:
            raise ProviderError("unsupported function declaration")
        name = fn.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", name) or name in names:
            raise ProviderError("invalid or duplicate function name")
        schema = fn.get("parameters")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ProviderError("MCP function input must be an object schema")
        if not isinstance(fn.get("description", ""), str):
            raise ProviderError("function description must be text")
        names.add(name)
        converted.append({"name": name, "description": fn.get("description", ""), "inputSchema": copy.deepcopy(schema)})
    return converted


class Record(SimpleNamespace):
    """Small attribute/model_dump-compatible ChatCompletion wire objects."""
    def model_dump(self, *, exclude_none=False, **kwargs):
        def plain(value):
            if isinstance(value, Record):
                return {k: plain(v) for k, v in vars(value).items() if not exclude_none or v is not None}
            if isinstance(value, list):
                return [plain(v) for v in value]
            return value
        return plain(self)


def record(value):
    if isinstance(value, dict):
        return Record(**{k: record(v) for k, v in value.items()})
    if isinstance(value, list):
        return [record(v) for v in value]
    return value


def usage(value):
    keys = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    if not isinstance(value, dict) or not all(type(value.get(k, 0)) is int and value.get(k, 0) >= 0 for k in keys):
        raise ProviderError("invalid runtime usage")
    if not all(k in value for k in ("input_tokens", "output_tokens")):
        return None  # unavailable, not zero
    prompt = sum(value.get(k, 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return {"prompt_tokens": prompt, "completion_tokens": value["output_tokens"],
            "total_tokens": prompt + value["output_tokens"], "prompt_tokens_details": {
                "cached_tokens": value.get("cache_read_input_tokens", 0),
                "cache_write_tokens": value.get("cache_creation_input_tokens", 0)}}
