__version__ = "5.0.0-beta.9"


RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[32;%dm"
BOLD_SEQ = "\033[1m"


def _get_color(color: int) -> str:
    return COLOR_SEQ % (30 + color)


BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = (
    _get_color(i) for i in range(8)
)

RELEASE_NOTES = {
    "5.0.0-beta.9": """
    Rename the `initialize_agent` method to `initialize`
    Update to new sockets spec
    """,
    "5.0.0-beta.8": """
    Fix spelling errors in interface
    """,
    "5.0.0-beta.7": """
    Fix spelling error in spec
    """,
    "5.0.0-beta.6": """
    Update to new sockets spec
    """,
    "5.0.0-beta.5": """
    Better `handle_match_communication` API
    """,
    "5.0.0-beta.4": """
    Better state setting API
    """,
    "5.0.0-beta.3": """
    Ensure bots don't fall behind the most recent GameTickPacket, without threading
    Add `team_color` static method to the rendering manager
    """,
    "5.0.0-beta.2": """
    Ensure bots don't fall behind the most recent GameTickPacket.
    """,
    "5.0.0-beta.1": """
    Initial iteration of the Python interface for RLBot.
    """,
}

RELEASE_BANNER = f"""
\x1b[32;1m
           ______ _     ______       _
     10100 | ___ \\ |    | ___ \\     | |   00101
    110011 | |_/ / |    | |_/ / ___ | |_  110011
  00110110 |    /| |    | ___ \\/ _ \\| __| 01101100
    010010 | |\\ \\| |____| |_/ / (_) | |_  010010
     10010 \\_| \\_\\_____/\\____/ \\___/ \\__| 01001
{RESET_SEQ}

"""


def get_current_release_notes():
    if __version__ in RELEASE_NOTES:
        return RELEASE_NOTES[__version__]
    return ""


def get_help_text():
    return (
        f"{RED+BOLD_SEQ}Trouble?{RESET_SEQ} Ask on Discord at {CYAN}https://discord.gg/5cNbXgG{RESET_SEQ} "
        f"or report an issue at {CYAN}https://github.com/RLBot/RLBot/issues{RESET_SEQ}"
    )


def print_current_release_notes():
    print(RELEASE_BANNER)
    print(f"Version {__version__}")
    print(get_current_release_notes())
    print(get_help_text())
    print("")
