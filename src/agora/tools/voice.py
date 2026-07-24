from __future__ import annotations

import logging
from typing import Any

from agora.tools.base import (
    JSONDict,
    SurfaceContract,
    SurfaceContractError,
    SurfaceIngressKind,
    ToolContext,
    _mcp_surface_contract,
    _surface_payload,
)

_log = logging.getLogger(__name__)


def tool_voice_speak(params: JSONDict, ctx: ToolContext) -> JSONDict:
    """MCP handler for voice/speak — synthesize and play text as speech."""
    surface: SurfaceContract | None = None
    try:
        from organs.D_Voice.interfaces.voice_io import (
            VoiceConfig,  # type: ignore[import-not-found]
        )
        from organs.D_Voice.tts.tts_provider import (
            TTSProviderFactory,  # type: ignore[import-not-found]
        )
    except ImportError:
        return {"error": "D-Voice TTS not available", "success": False}

    try:
        surface = _mcp_surface_contract(
            params,
            operation="voice/speak",
            default_kind=SurfaceIngressKind.OBSERVABILITY,
        )
        surface.require(SurfaceIngressKind.SOVEREIGN_CONTROL, operation="voice/speak")
    except SurfaceContractError as exc:
        payload: dict[str, Any] = (
            _surface_payload(surface) if surface is not None else {}
        )
        error = str(exc)
        if (
            surface is not None
            and surface.ingress_kind is not SurfaceIngressKind.SOVEREIGN_CONTROL
        ):
            error = f"{error}; cockpit control_plane is required"
        return {"error": error, "success": False, **payload}

    try:
        provider_type = params.get("provider", "elevenlabs")
        config = VoiceConfig(
            provider_type=provider_type, metadata=params.get("config", {})
        )
        factory = TTSProviderFactory()
        tts = factory.create(provider_type, config)
        text = params.get("text", "")
        audio = tts.synthesize(text)
        if audio:
            tts.stream_audio(audio)
        return {
            "success": True,
            "provider": provider_type,
            "text_length": len(text),
            **_surface_payload(surface),
        }
    except Exception as exc:  # defensive fallback
        _log.error("[MCPToolRegistry] voice/speak error: %s", exc)
        return {"error": str(exc), "success": False, **_surface_payload(surface)}


def tool_voice_session_info(params: JSONDict, ctx: ToolContext) -> JSONDict:
    """MCP handler for voice/session_info — return current voice session state."""
    surface: SurfaceContract | None = None
    try:
        surface = _mcp_surface_contract(
            params,
            operation="voice/session_info",
            default_kind=SurfaceIngressKind.OBSERVABILITY,
        )
        surface.require(
            SurfaceIngressKind.OBSERVABILITY,
            SurfaceIngressKind.SOVEREIGN_CONTROL,
            operation="voice/session_info",
        )
    except SurfaceContractError as exc:
        payload: dict[str, Any] = (
            _surface_payload(surface) if surface is not None else {}
        )
        return {"error": str(exc), "success": False, **payload}

    try:
        from organs.D_Voice.voice_session_manager import (
            VoiceSessionManager,  # type: ignore[import-not-found]
        )
    except ImportError:
        return {
            "error": "VoiceSessionManager not available",
            "success": False,
            **_surface_payload(surface),
        }

    try:
        session = VoiceSessionManager()
        return {
            "success": True,
            "authoritative": False,
            "truth_owner": "D-Execution",
            **session.get_session_info(),
            **_surface_payload(surface),
        }
    except Exception as exc:  # defensive fallback
        return {"error": str(exc), "success": False, **_surface_payload(surface)}


def tool_voice_intent_digest(params: JSONDict, ctx: ToolContext) -> JSONDict:
    """MCP handler for voice/intent_digest — convert transcribed text to intent."""
    surface: SurfaceContract | None = None
    try:
        from organs.D_Voice.interfaces.voice_io import VoiceResult
        from organs.D_Voice.voice_intent_digestor import (
            VoiceIntentDigestor,  # type: ignore[import-not-found]
        )
    except ImportError:
        return {"error": "VoiceIntentDigestor not available", "success": False}

    try:
        surface = _mcp_surface_contract(
            params,
            operation="voice/intent_digest",
            default_kind=SurfaceIngressKind.PERCEPTION,
        )
        surface.require(
            SurfaceIngressKind.PERCEPTION,
            SurfaceIngressKind.SOVEREIGN_CONTROL,
            operation="voice/intent_digest",
        )
    except SurfaceContractError as exc:
        payload: dict[str, Any] = (
            _surface_payload(surface) if surface is not None else {}
        )
        return {"error": str(exc), "success": False, **payload}

    try:
        text = params.get("text", "")
        result = VoiceResult(text=text, confidence=params.get("confidence", 1.0))
        digestor = VoiceIntentDigestor()
        intent_data = digestor.digest(result)
        return {
            "success": True,
            **intent_data,
            "surface": intent_data.get("surface", surface.to_dict()),
        }
    except Exception as exc:  # defensive fallback
        _log.error("[MCPToolRegistry] voice/intent_digest error: %s", exc)
        return {"error": str(exc), "success": False, **_surface_payload(surface)}
