'''
P12 (see ~/browseterm/p.md's "P12" section): a small, dependency-free parser for the Kubernetes
resource-quantity strings containers.cpu_limit/memory_limit/storage_limit are stored as (e.g.
"1", "500m", "2Gi"). Cloud deliberately does not depend on the `kubernetes` client library at
all (P06 moved every such dependency to browseterm-server-local - see that repo's Dockerfile/
pyproject.toml and this repo's README's "Architecture correction" section) so `kubernetes.utils.
quantity.parse_quantity`, which Local already uses for the same strings, isn't reachable from
here without reintroducing exactly the dependency P06 removed. This reimplements just the subset
those two container fields actually use.

devices.total_cpu/allocated_cpu/used_cpu are plain integer CPU **cores** (see
browseterm-desktop/desktop/device_info.py: `total_cpu = hw.ncpu`, no fractional units), while a
container's cpu_limit can be sub-core ("500m"). parse_cpu_cores rounds a sub-core request UP to
the nearest whole core for reservation/validation purposes - conservative (never lets accounting
under-count real usage), consistent with the plan's own acknowledgment (section 9) that these are
"fast counters" meant to be periodically reconciled against real Kubernetes state, not an exact
ledger.
'''
import math
import re

_MEMORY_SUFFIXES = {
    "Ki": 1024, "Mi": 1024 ** 2, "Gi": 1024 ** 3, "Ti": 1024 ** 4,
    "K": 1000, "M": 1000 ** 2, "G": 1000 ** 3, "T": 1000 ** 4,
}

_QUANTITY_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]*)\s*$")


class InvalidQuantityError(ValueError):
    pass


def _split(value: str) -> tuple[float, str]:
    match = _QUANTITY_RE.match(value or "")
    if not match:
        raise InvalidQuantityError(f"Invalid resource quantity: {value!r}")
    number, suffix = match.groups()
    return float(number), suffix


def parse_cpu_cores(value: str) -> int:
    '''"1" -> 1, "0.5" -> 1 (rounded up), "500m" -> 1, "2000m" -> 2. Whole cores, rounded up.'''
    number, suffix = _split(value)
    if suffix == "m":
        cores = number / 1000.0
    elif suffix == "":
        cores = number
    else:
        raise InvalidQuantityError(f"Invalid CPU quantity: {value!r}")
    return math.ceil(cores)


def parse_memory_bytes(value: str) -> int:
    '''"2Gi" -> 2147483648, "512Mi" -> 536870912, "1000000" -> 1000000 (plain bytes).'''
    number, suffix = _split(value)
    if suffix == "":
        return math.ceil(number)
    if suffix not in _MEMORY_SUFFIXES:
        raise InvalidQuantityError(f"Invalid memory/storage quantity: {value!r}")
    return math.ceil(number * _MEMORY_SUFFIXES[suffix])
