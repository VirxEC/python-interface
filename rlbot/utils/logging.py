import logging
import os
import sys

DEFAULT_LOGGER_NAME = "rlbot"
DEFAULT_LOGGER = None  # Set later

match os.environ.get("RLBOT_LOG_LEVEL"):
    case "debug":
        LOGGING_LEVEL = logging.DEBUG
    case "info":
        LOGGING_LEVEL = logging.INFO
    case "warn":
        LOGGING_LEVEL = logging.WARNING
    case "error":
        LOGGING_LEVEL = logging.ERROR
    case "critical":
        LOGGING_LEVEL = logging.CRITICAL
    case _:
        LOGGING_LEVEL = logging.INFO

logging.getLogger().setLevel(logging.NOTSET)


class CustomFormatter(logging.Formatter):
    GREY = "\x1b[38;20m"
    LIGHT_BLUE = "\x1b[94;20m"
    YELLOW = "\x1b[33;20m"
    GREEN = "\x1b[32;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"
    SECTIONS = [
        "%(asctime)s " + RESET,
        "%(levelname)8s:" + RESET + GREEN + "%(name)12s" + RESET,
        "[%(filename)16s:%(lineno)3s - %(funcName)25s() ]" + RESET + " ",
        "%(message)s" + RESET,
    ]

    FORMATS = {
        logging.DEBUG: [GREY, GREY, GREY, GREY],
        logging.INFO: [GREY, LIGHT_BLUE, GREY, LIGHT_BLUE],
        logging.WARNING: [YELLOW, YELLOW, YELLOW, YELLOW],
        logging.ERROR: [RED, RED, RED, RED],
        logging.CRITICAL: [RED, BOLD_RED, RED, BOLD_RED],
    }

    def format(self, record: logging.LogRecord) -> str:
        colors = self.FORMATS[record.levelno]

        log_fmt = ""
        for color, section in zip(colors, self.SECTIONS):
            log_fmt += color + section

        formatter = logging.Formatter(log_fmt, datefmt="%H:%M:%S")
        return formatter.format(record)


def check_color():
    from rlbot.utils.os_detector import CURRENT_OS, OS

    if CURRENT_OS == OS.WINDOWS:
        import os

        os.system("color")


def get_logger(logger_name: str) -> logging.Logger:
    if logger_name == DEFAULT_LOGGER_NAME:
        if DEFAULT_LOGGER is not None:
            return DEFAULT_LOGGER
        check_color()

    logger = logging.getLogger(logger_name)
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setFormatter(CustomFormatter())
        ch.setLevel(LOGGING_LEVEL)
        logger.addHandler(ch)
    logging.getLogger().handlers = []

    logger.debug("creating logger for %s", sys._getframe().f_back)
    return logger


DEFAULT_LOGGER = get_logger(DEFAULT_LOGGER_NAME)
