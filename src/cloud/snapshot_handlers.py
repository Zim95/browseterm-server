'''
Cloud snapshot allocation API (P16 - see ~/browseterm/p.md's "P16" section, plan section 5.5).

`snapshot_job` (browseterm_workload) will call this to allocate a container_snapshots row for a
save attempt, instead of writing to Postgres directly (that migration itself is P17's job, not
this one - see that section for why). Same trusted-SYSTEM-caller pattern as P09/P14 (no user_id -
snapshot_job knows only a container_id, never a user_id, matching how it's actually invoked
today: container-maker passes CONTAINER_ID and REQUEST_ID as Job env vars, nothing user-scoped).

Algorithm exactly matches the plan's own numbered steps (section 5.5):
  1. request arrives with request_id
  2. look for existing (container_id, request_id) - if found, reuse it (idempotent retry)
  3. if absent, read/increment containers.next_snapshot_sequence
  4. create a Pending container_snapshots row with that sequence
"Gaps in version numbers after crashes are acceptable" - so step 3 is a plain read-then-write, not
a hard transactional compare-and-swap. Deliberately not over-engineered past what the plan asks
for.
'''
import asyncio
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse

from browseterm_db.operations.all_operations import ContainerOps, SnapshotOps
from browseterm_db.common.snapshot_version import format_snapshot_version

from src.cloud.config import DB_CONFIG, CLOUD_INTERNAL_API_TOKEN, SNAPSHOT_REGISTRY_REPO_PREFIX
from src.common.logging_setup import get_logger

logger = get_logger("cloud_snapshot_handlers")


def _internal_auth_ok(request: Request) -> bool:
    return request.headers.get("X-Internal-Service-Token") == CLOUD_INTERNAL_API_TOKEN


async def allocate_snapshot(request: Request) -> JSONResponse:
    '''
    POST /internal/containers/{container_id}/snapshots/allocate

    Body: {"request_id": "..."}. Returns {"snapshot": {...}} - either the existing row for this
    (container_id, request_id) if one already exists (idempotent retry - plan step 2), or a newly
    allocated Pending row (plan steps 3-4).
    '''
    if not _internal_auth_ok(request):
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    try:
        container_id = request.path_params["container_id"]
        body = await request.json()
        request_id = body.get("request_id")
        if not request_id:
            return JSONResponse(content={"error": "request_id is required"}, status_code=400)

        snapshot_ops = SnapshotOps(DB_CONFIG)

        # Step 2: an existing attempt for this exact request_id is reused as-is, regardless of
        # its current status - the caller (snapshot_job) decides what to do with a Pending/
        # Running/Succeeded/Failed row it gets back; this endpoint's job is only to make sure a
        # retried request never allocates a second version for the same attempt.
        existing = await asyncio.to_thread(snapshot_ops.find_one, {"container_id": container_id, "request_id": request_id})
        if existing.data:
            return JSONResponse(content={"snapshot": existing.data})

        container_ops = ContainerOps(DB_CONFIG)
        container_result = await asyncio.to_thread(container_ops.find_one, {"id": container_id})
        if not container_result.data:
            return JSONResponse(content={"error": "Container not found"}, status_code=404)
        container = container_result.data

        # Steps 3-4: allocate the next sequence, then create the row. A plain read-then-write -
        # see the module docstring for why this doesn't need to be a hard atomic CAS.
        sequence = container["next_snapshot_sequence"]
        increment_result = await asyncio.to_thread(
            container_ops.update, {"id": container_id}, {"next_snapshot_sequence": sequence + 1}
        )
        if not increment_result.success:
            logger.error("failed to increment next_snapshot_sequence", extra={"error": increment_result.error})
            return JSONResponse(content={"error": "Error allocating snapshot version"}, status_code=500)

        image_repository = f"{SNAPSHOT_REGISTRY_REPO_PREFIX}/{container['user_id']}_{container_id}"
        insert_result = await asyncio.to_thread(snapshot_ops.insert, {
            "container_id": container_id,
            "version_sequence": sequence,
            "version": format_snapshot_version(sequence),
            "image_repository": image_repository,
            "request_id": request_id,
        })
        if not insert_result.success:
            logger.error("failed to create snapshot row", extra={"error": insert_result.error})
            return JSONResponse(content={"error": "Error allocating snapshot version"}, status_code=500)

        return JSONResponse(content={"snapshot": insert_result.data}, status_code=201)
    except Exception:
        logger.error("snapshot allocation failed", exc_info=True)
        return JSONResponse(content={"error": "Error allocating snapshot version"}, status_code=500)


# SnapshotStatus/SaveStatus share the exact same string values (Pending/Running/Succeeded/Failed)
# by design - see browseterm_db's container_snapshots.py/containers.py - so a snapshot status is
# also always a valid containers.save_status, no translation table needed.
_TERMINAL_SNAPSHOT_STATUSES = {"Succeeded", "Failed"}


async def report_snapshot_result(request: Request) -> JSONResponse:
    '''
    POST /internal/containers/{container_id}/snapshots/{snapshot_id}/report

    P17 (see ~/browseterm/p.md's "P17" section, plan section 13). Body: {"status": "Running"|
    "Succeeded"|"Failed", "image_reference"?, "registry_digest"?, "error_detail"?}. `snapshot_job`
    calls this at each stage of a save attempt instead of writing to Postgres directly.

    Updates BOTH rows a save attempt touches:
    - The `container_snapshots` row itself (status/error_detail/image_reference/registry_digest,
      `completed_at` stamped once the status reaches a terminal one).
    - The owning `containers` row's save-flow fields (`save_status`/`save_error`), the same
      fields the pre-P17 direct-DB `update_save_status` always touched - the frontend's SSE feed
      (P10) is driven by the `containers` table's own NOTIFY trigger, not `container_snapshots`,
      so this has to keep updating `containers` for the UI to see anything.

    `saved_image`/`last_saved_at` on the `containers` row are ONLY set when `status == "Succeeded"`
    - plan section 13 is explicit: "On failure, saved_image must remain unchanged."
    '''
    if not _internal_auth_ok(request):
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    try:
        container_id = request.path_params["container_id"]
        snapshot_id = request.path_params["snapshot_id"]
        body = await request.json()
        status = body.get("status")
        if status not in {"Running", "Succeeded", "Failed"}:
            return JSONResponse(content={"error": f"Invalid status: {status}"}, status_code=400)
        image_reference = body.get("image_reference")
        registry_digest = body.get("registry_digest")
        error_detail = body.get("error_detail")

        snapshot_ops = SnapshotOps(DB_CONFIG)
        snapshot_update: dict = {"status": status, "error_detail": error_detail}
        if image_reference is not None:
            snapshot_update["image_reference"] = image_reference
        if registry_digest is not None:
            snapshot_update["registry_digest"] = registry_digest
        if status in _TERMINAL_SNAPSHOT_STATUSES:
            snapshot_update["completed_at"] = datetime.now(timezone.utc)
        snapshot_result = await asyncio.to_thread(
            snapshot_ops.update, {"id": snapshot_id, "container_id": container_id}, snapshot_update
        )
        if not snapshot_result.success:
            logger.error("failed to update snapshot row", extra={"error": snapshot_result.error})
            return JSONResponse(content={"error": "Error reporting snapshot result"}, status_code=500)

        container_ops = ContainerOps(DB_CONFIG)
        container_update: dict = {"save_status": status, "save_error": error_detail}
        if status == "Succeeded" and image_reference:
            container_update["saved_image"] = image_reference
            container_update["last_saved_at"] = datetime.now(timezone.utc)
        container_result = await asyncio.to_thread(container_ops.update, {"id": container_id}, container_update)
        if not container_result.success:
            logger.error("failed to update container save state", extra={"error": container_result.error})
            return JSONResponse(content={"error": "Error reporting snapshot result"}, status_code=500)

        return JSONResponse(content={"ok": True})
    except Exception:
        logger.error("snapshot result report failed", exc_info=True)
        return JSONResponse(content={"error": "Error reporting snapshot result"}, status_code=500)
