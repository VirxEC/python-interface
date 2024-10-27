from typing import Optional

from rlbot import flat


def fill_desired_game_state(
        balls: dict[int, flat.DesiredBallState] = {},
        cars: dict[int, flat.DesiredCarState] = {},
        game_info: Optional[flat.DesiredGameInfoState] = None,
        commands: list[flat.ConsoleCommand] = [],
) -> flat.DesiredGameState:
    """
    # Converts the dictionaries to a DesiredGameState by
    # filling in the blanks with empty states that do nothing.
    """

    game_state = flat.DesiredGameState(
        game_info_state=game_info, console_commands=commands
    )

    if balls:
        max_entry = max(balls.keys())
        game_state.ball_states = [
            balls.get(i, flat.DesiredBallState()) for i in range(max_entry + 1)
        ]

    if cars:
        max_entry = max(cars.keys())
        game_state.car_states = [
            cars.get(i, flat.DesiredCarState()) for i in range(max_entry + 1)
        ]

    return game_state
