__version__ = "5.0.0"


RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[32;%dm"
BOLD_SEQ = "\033[1m"


def _get_color(color):
    return COLOR_SEQ % (30 + color)


BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = (
    _get_color(i) for i in range(8)
)

RELEASE_NOTES = {
    "5.0.0": """
    Initial iteration of the Python interface for RLBot.
    """
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
