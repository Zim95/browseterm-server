# builtins
import abc


class Handler:
    """
    Handler abstract class. Receives request data.
    Has a handle method which is an abstract class method.

    Author: Namah Shrestha
    """

    def __init__(self, request_params: dict) -> None:
        """
        Initialize the request params.
        :params:
            request_params: dict: Request parameters parsed by the controller.
        :returns: None

        Author: Namah Shrestha
        """
        self.request_params: dict = request_params

    @abc.abstractclassmethod
    def handle(self) -> dict | None:
        """
        Abstract handle logic to be implemented by child classes.
        :params: None.
        :returns: The response of the request or None.

        Author: Namah Shrestha
        """
        # TODO: Add async logging of request params here
        pass
