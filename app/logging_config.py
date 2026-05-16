import logging


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(levelname)-8s %(asctime)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger().setLevel(level)
