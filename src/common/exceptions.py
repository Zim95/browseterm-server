class ContainerMakerException(Exception):
    '''
    Exception for the container maker.
    '''
    pass


class ContainerDBException(Exception):
    '''
    Exception for the container database.
    '''
    pass


class PaymentGatewayException(Exception):
    '''
    Exception for the payment gateway.
    '''
    pass


class PaymentGatewayUnavailableException(Exception):
    '''
    Raised when payment-gateway can't be reached or the call times out.
    '''
    pass
