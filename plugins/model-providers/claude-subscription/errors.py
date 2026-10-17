"""Provider error type shared by every module."""


class ProviderError(RuntimeError):
    """Terminal client/protocol error; never a successful substitute response."""
