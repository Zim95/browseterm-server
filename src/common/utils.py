# standard library
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
