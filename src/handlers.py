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

        Author: Namah Shrestha
        """
        self.request_params: dict = request_params

    @abc.abstractclassmethod
    def handle(self) -> dict | None:
        """
        Abstract handle logic to be implemented by child classes.

        Author: Namah Shrestha
        """
        pass


class PingHandler(Handler):
    """
    Simple Ping Handler. For test.
    Accepts request parameters.
    Echoes back request parameters and runtime environment.

    Author: Namah Shrestha
    """
    def __init__(self, request_params: dict) -> None:
        """
        Initialize request parameters.

        Author: Namah Shrestha
        """
        super().__init__(request_params)
    
    def handle(self) -> dict | None:
        """
        Return request params for test.

        Author: Namah Shrestha
        """
        return {
            "request_params": self.request_params,
        }


class ImageOptionsHandler(Handler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)
    
    def handle(self) -> dict | None:
        return [
            {
                "id": "asdfghjkl",
                "value": "zim95/ssh_ubuntu:latest",
                "label": "ubuntu",
            }
        ]