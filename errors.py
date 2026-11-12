COG_UNAVAILABLE_MESSAGE: str = 'The bot is updating right now. Full availability is back soon, please try again in a moment.'
"""Message shown to users when a command cannot be processed because a required cog is (re)loading."""


class CogUnavailableError(Exception):
    """
    Raised when a cog is accessed while it is not loaded, e.g. during a reload.

    This module is not an extension and therefore never reloaded, so the error handlers in main.py can always rely on it.
    """

    def __init__(self, cog_name: str) -> None:
        super().__init__(f'Cog {cog_name} is not available')
        self.cog_name: str = cog_name
