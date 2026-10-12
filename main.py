import logging
from datetime import datetime

import colorlog

from src import const, game

FULL_NAME = "Plants vs. Zombies Python Edition"
VERSION = "v0.0.1-dev"

LOG_LEVEL = logging.DEBUG
FILE_LOGGING = False

CONSOLE_LOG_FORMAT = colorlog.ColoredFormatter(
    "%(datetime_log_color)s[%(asctime)s]%(reset)s"
    "%(module_log_color)s[%(module)s]%(reset)s"
    "%(log_color)s[%(levelname)s]%(reset)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "red",
    },
    secondary_log_colors={
        "datetime": {
            "DEBUG": "green",
            "INFO": "green",
            "WARNING": "green",
            "ERROR": "green",
            "CRITICAL": "green",
        },
        "module": {
            "DEBUG": "purple",
            "INFO": "purple",
            "WARNING": "purple",
            "ERROR": "purple",
            "CRITICAL": "purple",
        },
    },
)
FILE_LOG_FORMAT = logging.Formatter(
    "[%(asctime)s][%(module)s][%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
FILE_LOG_DIRECTORY = const.PROJECT_ROOT / "logs"
FILE_LOG_PATH = FILE_LOG_DIRECTORY / (datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".log")


def main() -> None:
    logger = logging.getLogger()
    logger.setLevel(LOG_LEVEL)
    logger.handlers.clear()
    logger.propagate = False

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(CONSOLE_LOG_FORMAT)
    logger.addHandler(console_handler)

    if FILE_LOGGING:
        logging.debug(f"File logging is enabled. Log file will be created at: {FILE_LOG_PATH}")
        FILE_LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(FILE_LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(FILE_LOG_FORMAT)
        logger.addHandler(file_handler)

    logging.info(" ______ ___ ___ _______                  ")
    logging.info("|   __ \\   |   |__     |    .-----.--.--.")
    logging.info("|    __/   |   |     __|    |  _  |  |  |")
    logging.info("|___|   \\_____/|_______|    |   __|___  |")
    logging.info("                            |__|  |_____|")
    logging.info("{} v{}".format(FULL_NAME, VERSION))
    logging.info("Powered By Github@Potato4096")

    # 初始化并运行游戏；依赖经 GameContext 显式注入下游
    game.Game().run()


if __name__ == "__main__":
    main()
