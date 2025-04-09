# third party
import grpc


class GRPCUtils:
    '''
    A utility class for GRPC connections.
    Creates a secure or insecure channel to a GRPC server.

    TODO: Add connection pooling.
    '''
    def __init__(
        self,
        host: str,
        port: int,
        stub_class: any,
        secure: bool = True,
        client_key: bytes | None = None,
        client_cert: bytes | None = None,
        ca_cert: bytes | None = None
    ) -> None:
        '''
        Initialize the GRPCUtils object.
        :params:
            host: str
                The host of the GRPC server.
            port: int
                The port of the GRPC server.
            stub_class: grpc.ClientCallableClass
                The stub class to call the GRPC server rpcs.
            secure: bool
                Whether the GRPC connection is secure.
            client_key: str
                The GRPC server's certificate key.
            client_cert: str
                The GRPC server's certificate.
            ca_cert: str
                The GRPC server's CA certificate.
        '''
        self.host: str = host
        self.port: int = port
        self.stub_class: any = stub_class
        self.secure: bool = secure

        # certificates
        self.client_key: bytes = client_key
        self.client_cert: bytes = client_cert
        self.ca_cert: bytes = ca_cert

        self._channel: grpc.Channel | None = None
        self._stub: any | None = None

    @property
    def channel(self) -> grpc.Channel:
        '''
        Get the GRPC channel.
        '''
        if self._channel is not None:
            return self._channel
        if not self.secure:
            self._channel = grpc.insecure_channel(f"{self.host}:{self.port}")
            return self._channel
        if not any([self.client_key, self.client_cert, self.ca_cert]):
            raise ValueError("Client key, client cert, and CA cert must be provided if secure is True")
        credentials: grpc.ServerCredentials = grpc.ssl_channel_credentials(
            root_certificates=self.ca_cert,
            private_key=self.client_key,
            certificate_chain=self.client_cert
        )
        self._channel = grpc.secure_channel(f"{self.host}:{self.port}", credentials)
        return self._channel

    @property
    def stub(self) -> any:
        '''
        Get the GRPC stub.
        '''
        if self._stub is not None:
            return self._stub
        self._stub = self.stub_class(channel=self.channel)
        return self._stub
