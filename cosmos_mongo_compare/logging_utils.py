from __future__ import annotations

import logging
import sys


def build_logger(main_log_path: str) -> logging.Logger:
    logger = logging.getLogger("cosmos_mongo_compare")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    handlers: list[logging.Handler] = []
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    handlers.append(stream)

    file_handler = logging.FileHandler(main_log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    handlers.append(file_handler)

    for h in list(logger.handlers):
        try:
            h.close()
        except Exception:
            pass
    logger.handlers.clear()
    for h in handlers:
        logger.addHandler(h)
    return logger
