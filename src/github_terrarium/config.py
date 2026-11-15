"""Explicit configuration boundaries."""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")


@dataclass(frozen=True)
class Config:
    login: str
    repository: str


def load_config(file: Path, repository: str) -> Config:
    with file.open("rb") as stream:
        raw = tomllib.load(stream)
    if set(raw) != {"login"}:
        raise ValueError("Configuration must contain only login")
    login = raw["login"]
    if not isinstance(login, str) or not LOGIN.fullmatch(login):
        raise ValueError("Invalid GitHub login")
    parts = repository.split("/")
    if (
        len(parts) != 2
        or not LOGIN.fullmatch(parts[0])
        or not REPOSITORY.fullmatch(parts[1])
        or parts[1] in {".", ".."}
    ):
        raise ValueError("Repository must be explicit owner/name")
    return Config(login, repository)
