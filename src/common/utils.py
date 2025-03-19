# third-party
import grpc

# standard library
import os


def read_certs(env_var_key: str, path: str) -> str:
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
        The certificate as a string.
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
