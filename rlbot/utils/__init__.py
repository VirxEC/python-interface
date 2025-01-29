from typing import Optional

from rlbot import flat


def fill_desired_game_state(
    balls: dict[int, flat.DesiredBallState] = {},
    cars: dict[int, flat.DesiredCarState] = {},
    match_info: Optional[flat.DesiredMatchInfo] = None,
    commands: list[str] = [],
) -> flat.DesiredGameState:
    """
    Converts the dictionaries to a DesiredGameState by
    filling in the blanks with empty states that do nothing.
    """

    game_state = flat.DesiredGameState(
        match_info=match_info,
        console_commands=[flat.ConsoleCommand(cmd) for cmd in commands],
    )

    if balls:
        max_entry = max(balls.keys())
        default_ball = flat.DesiredBallState()
        game_state.ball_states = [
            balls.get(i, default_ball) for i in range(max_entry + 1)
        ]

    if cars:
        max_entry = max(cars.keys())
        default_car = flat.DesiredCarState()
        game_state.car_states = [cars.get(i, default_car) for i in range(max_entry + 1)]

    return game_state
