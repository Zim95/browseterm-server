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
