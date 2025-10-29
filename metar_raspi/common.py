"""Shared global methods."""

import json
import logging

import metar_raspi.config as cfg

IDENT_CHARS = [
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "I",
    "J",
    "K",
    "L",
    "M",
    "N",
    "O",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
    "Z",
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
]

logger = logging.getLogger()
logger.setLevel(cfg.log_level)
if cfg.log_file is not None:
    log_file = logging.FileHandler(cfg.log_file)
    log_file.setLevel(cfg.log_level)
    logger.addHandler(log_file)


def ident_to_station(idents: list[int]) -> str:
    """Converts 'ident' ints to station string."""
    return "".join([IDENT_CHARS[num] for num in idents])


def station_to_ident(station: str) -> list[int]:
    """Converts station string to 'ident' ints."""
    ret = []
    for char in station:
        if char.isalpha():
            ret.append(ord(char) - 65)
        elif char.isdigit():
            ret.append(ord(char) - 22)
    return ret


SESSION_PATH = cfg.LOC / "session.json"


def load_session() -> dict:
    """Returns available session dict."""
    try:
        session: dict = json.load(SESSION_PATH.open())
    except FileNotFoundError:
        return {}
    return session


def save_session(data: dict) -> None:
    """Save the session dict to disk."""
    json.dump(data, SESSION_PATH.open("w"))
