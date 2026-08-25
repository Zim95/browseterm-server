# standard library
import json
import os
import re


class ResourceUnitConverter:
    """
    Handles Kubernetes resource unit conversions and request derivation.
    Properly converts between units (e.g., 1Gi * 0.5 = 512Mi).
    """

    # Memory unit conversions to bytes
    MEMORY_UNITS = {
        '': 1,
        'Ki': 1024,
        'Mi': 1024 ** 2,
        'Gi': 1024 ** 3,
        'Ti': 1024 ** 4,
        'K': 1000,
        'M': 1000 ** 2,
        'G': 1000 ** 3,
        'T': 1000 ** 4,
    }

    # CPU unit conversions to millicores
    CPU_UNITS = {
        '': 1000,  # 1 core = 1000m
        'm': 1,    # millicores
    }

    @classmethod
    def parse_memory_to_bytes(cls, value: str) -> int:
        """Parse memory string (e.g., '1Gi', '512Mi') to bytes."""
        match = re.match(r'^(\d+(?:\.\d+)?)(Ki|Mi|Gi|Ti|K|M|G|T)?$', value)
        if not match:
            raise ValueError(f"Invalid memory format: {value}")
        num = float(match.group(1))
        unit = match.group(2) or ''
        return int(num * cls.MEMORY_UNITS[unit])

    @classmethod
    def bytes_to_memory_string(cls, bytes_val: int) -> str:
        """Convert bytes to human-readable memory string (Mi or Gi)."""
        if bytes_val >= cls.MEMORY_UNITS['Gi']:
            val = bytes_val / cls.MEMORY_UNITS['Gi']
            if val == int(val):
                return f"{int(val)}Gi"
            # Use Mi if Gi results in a non-integer
            val_mi = bytes_val / cls.MEMORY_UNITS['Mi']
            return f"{int(val_mi)}Mi"
        else:
            val = bytes_val / cls.MEMORY_UNITS['Mi']
            return f"{int(val)}Mi"

    @classmethod
    def parse_cpu_to_millicores(cls, value: str) -> int:
        """Parse CPU string (e.g., '1', '500m') to millicores."""
        match = re.match(r'^(\d+(?:\.\d+)?)(m)?$', value)
        if not match:
            raise ValueError(f"Invalid CPU format: {value}")
        num = float(match.group(1))
        unit = match.group(2) or ''
        return int(num * cls.CPU_UNITS[unit])

    @classmethod
    def millicores_to_cpu_string(cls, millicores: int) -> str:
        """Convert millicores to CPU string."""
        if millicores >= 1000 and millicores % 1000 == 0:
            return str(millicores // 1000)
        return f"{millicores}m"

    @classmethod
    def derive_memory_request(cls, limit: str, ratio: float) -> str:
        """
        Derive memory request from limit by applying a ratio.
        Example: 1Gi * 0.5 = 512Mi
        """
        try:
            bytes_val = cls.parse_memory_to_bytes(limit)
            derived_bytes = int(bytes_val * ratio)
            return cls.bytes_to_memory_string(derived_bytes)
        except ValueError:
            return limit

    @classmethod
    def derive_cpu_request(cls, limit: str, ratio: float) -> str:
        """
        Derive CPU request from limit by applying a ratio.
        Example: 1 * 0.1 = 100m
        """
        try:
            millicores = cls.parse_cpu_to_millicores(limit)
            derived_millicores = int(millicores * ratio)
            return cls.millicores_to_cpu_string(derived_millicores)
        except ValueError:
            return limit


def read_certs(env_var_key: str, path: str) -> bytes:
    """
    Read the certificates from environment.
    If not found read from path.
    Finally if not found we raise an error.
    :params:
        env_var_key: str
            The environment variable key to read the certificate from.
        path: str
            The path to read the certificate from if the environment variable is not found.
    :return:
        The certificate as bytes.
    """
    try:
        cert = os.environ.get(env_var_key)
        if cert is not None:
            cert = cert.encode('utf-8')
        if cert is None:
            cert = open(path, 'rb').read()
        return cert
    except FileNotFoundError as fnfe:
        raise FileNotFoundError(fnfe)


def read_cert_from_env_var(env_var_key: str) -> bytes:
    """
    Read the certificate from environment variable.
    If not found we raise an error.
    :params:
        env_var_key: str
            The environment variable key to read the certificate from.
    :return:
        The certificate as bytes.
    """
    try:
        cert = os.environ.get(env_var_key)
        if not cert:
            raise FileNotFoundError(f"Certificate not found in environment variable {env_var_key}")
        cert = cert.encode('utf-8')
        return cert
    except FileNotFoundError as fnfe:
        raise FileNotFoundError(fnfe)


def read_cert_from_file(file_path: str) -> bytes:
    """
    Read the certificate from a file path (mounted secret).
    :params:
        file_path: str
            The path to read the certificate from.
    :return:
        The certificate as bytes.
    :raises:
        FileNotFoundError: If the file does not exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Certificate file not found at {file_path}")
    with open(file_path, 'rb') as f:
        return f.read()


def clean_k8s_error_message(raw: str, fallback: str) -> str:
    """
    Turn a raw Kubernetes/gRPC exception string into something a user can actually read.

    A Kubernetes ApiException's str() embeds a JSON response body (e.g.
    '{"kind":"Status",...,"message":"pods \\"x\\" is forbidden: exceeded quota: ...",...}'),
    and it typically arrives here having been wrapped/re-raised several times across the
    gRPC boundary (container-maker's servicer, then this service's own except block), so the
    same "Reason: None" / HTTPHeaderDict noise repeats. Rather than show that raw text to a
    user, pull out the one field that's actually meaningful (the K8s message) and otherwise
    fall back to a clean generic message.
    :params:
        raw: str
            str(exception) from the failed k8s/gRPC call.
        fallback: str
            Message to use when no K8s message can be extracted.
    :return:
        A short, user-presentable error message.
    """
    start, end = raw.find('{'), raw.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            body = json.loads(raw[start:end + 1])
            message = body.get('message')
            if message:
                if 'exceeded quota' in message.lower():
                    return (
                        "You've reached your plan's resource limit. Hibernate or delete "
                        "another terminal to free up a slot, or upgrade your plan, then try again."
                    )
                return message
        except (json.JSONDecodeError, AttributeError):
            pass
    if 'exceeded quota' in raw.lower():
        return (
            "You've reached your plan's resource limit. Hibernate or delete another "
            "terminal to free up a slot, or upgrade your plan, then try again."
        )
    return fallback
