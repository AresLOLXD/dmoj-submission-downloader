import logging
import pytest
from app.logging_config import configure_logging


@pytest.fixture(autouse=True)
def restore_root_log_level():
    original = logging.getLogger().level
    yield
    logging.getLogger().setLevel(original)


def test_configure_logging_sets_root_level_to_debug():
    configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_sets_root_level_to_info():
    configure_logging("INFO")
    assert logging.getLogger().level == logging.INFO
