# module
import src.handlers.base_handler as bh


class PingHandler(bh.Handler):
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
