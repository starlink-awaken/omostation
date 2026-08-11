"""Recursively immutable JSON-compatible values."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import cast

from pydantic import JsonValue


class FrozenDict(Mapping[str, "ImmutableJson"]):
    """A read-only mapping whose values are recursively frozen."""

    __slots__ = ("_data",)

    def __init__(self, values: Mapping[str, ImmutableJson]) -> None:
        self._data = MappingProxyType(dict(values))

    def __getitem__(self, key: str) -> ImmutableJson:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"FrozenDict({dict(self._data)!r})"


type ImmutableJson = str | int | float | bool | None | tuple["ImmutableJson", ...] | FrozenDict


def freeze_json(value: JsonValue) -> ImmutableJson:
    """Copy a JSON value into mappings and sequences that cannot mutate."""
    if isinstance(value, dict):
        mapping = cast(dict[str, JsonValue], value)
        return FrozenDict({key: freeze_json(item) for key, item in mapping.items()})
    if isinstance(value, list):
        sequence = cast(list[JsonValue], value)
        return tuple(freeze_json(item) for item in sequence)
    return value


def freeze_mapping(value: Mapping[str, JsonValue]) -> FrozenDict:
    return FrozenDict({key: freeze_json(item) for key, item in value.items()})


def thaw_json(value: ImmutableJson) -> JsonValue:
    """Return a detached JSON container for Pydantic serialization."""
    if isinstance(value, FrozenDict):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value
