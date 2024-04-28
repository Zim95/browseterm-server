# module
import src.handlers.base_handler as bh
import src.auth as auth


class ImageOptionsHandler(bh.Handler):
    """
    Return all the available image options.

    Author: Namah Shrestha
    """

    @auth.auth_required
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
