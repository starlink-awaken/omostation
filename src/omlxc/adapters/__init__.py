"""Infrastructure adapters for local inference backends."""

from .lmstudio import LmsLoadOptions, LmsPlatform, LmStudioAdapter
from .ollama import OllamaAdapter
from .omlx_app import OmlxAppAdapter
from .process import ProcessOutput
from .tailscale import (
    AuthorizedHttpEndpoint,
    AuthorizedSshTarget,
    TailscaleAdapter,
    TailscaleErrorCode,
    TailscaleFailure,
    TailscaleNodePolicy,
    TailscaleNodeSnapshot,
    TailscaleSnapshot,
)

__all__ = [
    "LmStudioAdapter",
    "LmsLoadOptions",
    "LmsPlatform",
    "OllamaAdapter",
    "OmlxAppAdapter",
    "ProcessOutput",
    "AuthorizedHttpEndpoint",
    "AuthorizedSshTarget",
    "TailscaleAdapter",
    "TailscaleErrorCode",
    "TailscaleFailure",
    "TailscaleNodePolicy",
    "TailscaleNodeSnapshot",
    "TailscaleSnapshot",
]
