# module
import src.handlers.base_handler as bh


class ImageOptionsHandler(bh.Handler):
    """
    Return all the available image options.

    Author: Namah Shrestha
    """

    def handle(self) -> dict | None:
        """
        Return the available images for browseterm.

        Author: Namah Shrestha
        """
        return [
            {
                "id": "asdfghjkl",
                "value": "zim95/ssh_ubuntu:latest",
                "label": "ubuntu",
            }
        ]
