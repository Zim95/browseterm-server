'''
Device Agent -> Cloud CommandResult reporting over plain HTTP (added 2026-09-26), NOT the Device
Control gRPC stream - see src/control/command_result_ops.py's module docstring for the full
reasoning (that stream drops every ~30-90s in practice; this synchronous request/response call
never had that problem, matching request_hibernate/get_save_status's existing pattern).

Device Agent still ALSO reports over the stream unchanged, for compatibility with older agent
builds during a rollout - apply_terminal_command_result is idempotent per command_id, so receiving
the same result twice, from two different transports, is harmless (duplicate delivery is expected
and safe, same as every other command-driven path in this migration).
'''
import json

from fastapi import Request
from fastapi.responses import JSONResponse

from src.cloud.device_handlers import authenticate_device
from src.control.command_result_ops import apply_terminal_command_result
from src.common.logging_setup import get_logger

logger = get_logger("device_command_result_handlers")

_VALID_STATUSES = {"succeeded", "failed"}


def _not_found() -> JSONResponse:
    return JSONResponse(content={"error": "Not found"}, status_code=404)


@authenticate_device
async def report_command_result(request: Request) -> JSONResponse:
    '''
    POST /devices/{device_id}/commands/{command_id}/result

    Bearer device-token gated (src.cloud.device_handlers.authenticate_device). Body:
    {"status": "succeeded"|"failed", "result": {...}|null, "error_code": str|null,
    "error_message": str|null, "placement_generation": int}.

    Reuses the exact same command row lookup/staleness/dedup logic servicer.py's stream-based
    _handle_command_result already uses (apply_terminal_command_result) - this is a new transport
    for an existing, already-safe operation, not new behavior.
    '''
    device_id = request.path_params["device_id"]
    if device_id != request.state.device_id:
        return _not_found()
    command_id = request.path_params["command_id"]
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(content={"error": "Invalid JSON body"}, status_code=400)

    status = body.get("status")
    if status not in _VALID_STATUSES:
        return JSONResponse(content={"error": f"Invalid status: {status}"}, status_code=400)
    placement_generation = body.get("placement_generation")
    if not isinstance(placement_generation, int):
        return JSONResponse(content={"error": "placement_generation is required"}, status_code=400)
    result = body.get("result")

    try:
        result_json = json.dumps(result) if result is not None else None
        await apply_terminal_command_result(
            device_id, command_id, status, result_json,
            body.get("error_code"), body.get("error_message"), placement_generation,
        )
        return JSONResponse(content={"ok": True})
    except Exception:
        logger.error("command result report failed", exc_info=True, extra={"command_id": command_id, "device_id": device_id})
        return JSONResponse(content={"error": "Error reporting command result"}, status_code=500)
