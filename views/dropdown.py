from __future__ import annotations  # https://stackoverflow.com/a/50768146/8387076

from typing import Any, Callable, Coroutine, NoReturn, Optional, Self

import discord.ui
import uuid6
from discord import Interaction


class Dropdown(discord.ui.Select):
    """
    A Dropdown menu.
    """

    def __init__(self, callback_func: Callable[[Self, discord.Interaction], Coroutine[Any, Any, None]],
                 options: list[discord.SelectOption], original_interaction: Optional[discord.Interaction] = None,
                 *, min_values: int = 1, max_values: Optional[int] = None,
                 placeholder: Optional[str] = None, disabled: bool = False, custom_id: Optional[str] = None,
                 row: Optional[int] = None) -> None:
        """
        Initializes the dropdown menu.

        Parameters
        ----------
        callback_func : Callable[[Self, discord.Interaction], Coroutine[Any, Any, None]]
            The function that will be called when the user chooses options from the dropdown. Must be a coroutine.
            An instance of this class will also be passed so that the selected values can be retrieved easily.
        options : list[discord.SelectOption]
            The list of options to be shown in the dropdown. Pre-chosen options should have the default set to True.
            Cannot have more than 25 items due to Discord limitation.
        original_interaction: discord.Interaction | None
            An instance of the original interaction. If not None, the callback will be issued iff the original user
            who started the interaction is same as the person who is responding to this dropdown.
        min_values : int = 1
            The minimum number of option that the user can choose. Default: 1.
        max_values : int | None = None
            The maximum number of option that the user can choose.
        placeholder : str | None = None
            The placeholder text to be shown on the Dropdown.
        disabled: bool = False
            Whether the Dropdown is disabled.
        custom_id: str | None = None
            The custom ID of the Dropdown. If not passed, an ID is automatically generated.
        row: int | None = None
            The row where the dropdown will be placed. Has to ∈ [0, 4], i.e. zero-indexed.

        Raises
        ------
        ValueError
            If the there are more than 25 options provided, or the row number ∉ [0, 4].

        Notes
        -----
          - `original_interaction` parameter will be made a compulsory parameter in the near future. TODO
          - IMPORTANT: The interaction passed in on_submit_callback has already been responded to, so use followup.
        """

        if len(options) > 25:
            raise ValueError('One Dropdown cannot have more than 25 options!')

        if row and (row < 0 or row > 4):
            raise ValueError('`row` has to ∈ [0, 4] (both included)!')

        super().__init__(min_values=min_values,
                         max_values=len(options) if max_values is None else max_values,
                         options=options, placeholder=placeholder, disabled=disabled,
                         custom_id=uuid6.uuid7().hex if custom_id is None else custom_id, row=row)

        self._callback_func = callback_func
        self._original_interaction = original_interaction

    # ---------------------------------------------------------------------------------------------------------------

    async def callback(self, interaction: discord.Interaction) -> NoReturn:
        await interaction.response.defer()
        await self._callback_func(self, interaction)

    # ---------------------------------------------------------------------------------------------------------------

    def regenerate_self(self) -> Self:
        """
        Create a copy of self, with the options list edited such that the currently selected \
        values become the default values.
        """
        if len(self.values) == 0:
            return self

        modified_options: list[discord.SelectOption] = []
        for option in self.options:
            modified_options.append(discord.SelectOption(label=option.label, value=option.value,
                                                         description=option.description,
                                                         default=option.value in self.values))

        return Dropdown(self._callback_func, modified_options, min_values=self.min_values, max_values=self.max_values)

    # ---------------------------------------------------------------------------------------------------------------

    async def interaction_check(self, interaction: Interaction) -> bool:
        if not self._original_interaction:  # For compatibility, will be removed in the future TODO
            return True

        if self._original_interaction.user.id == interaction.user.id:
            return True
        else:
            await interaction.response.send_message(':warning: I respond only to the user who executed '
                                                    'the original command.', ephemeral=True)
            return False
