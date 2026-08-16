from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Suit(str, Enum):
    WAN = "wan"
    TIAO = "tiao"
    TONG = "tong"

    @property
    def label(self) -> str:
        return {"wan": "万", "tiao": "条", "tong": "筒"}[self.value]


@dataclass(frozen=True, order=True)
class Tile:
    suit: Suit
    rank: int
    copy: int = 0

    @property
    def key(self) -> tuple[Suit, int]:
        return (self.suit, self.rank)

    @property
    def label(self) -> str:
        if self.suit is Suit.WAN:
            nums = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
            return f"{nums[self.rank]}万"
        if self.suit is Suit.TIAO:
            return f"{self.rank}条"
        return f"{self.rank}筒"


@dataclass
class Meld:
    kind: str
    tile: Tile
    exposed: bool = True

    @property
    def label(self) -> str:
        names = {"peng": "碰", "ming_gang": "明杠", "an_gang": "暗杠"}
        return f"{names.get(self.kind, self.kind)} {self.tile.label}"


@dataclass
class Player:
    name: str
    is_human: bool = False
    hand: list[Tile] = field(default_factory=list)
    discards: list[Tile] = field(default_factory=list)
    melds: list[Meld] = field(default_factory=list)
    missing_suit: Suit | None = None
    score: int = 0
    won: bool = False

    def sort_hand(self) -> None:
        self.hand.sort(key=lambda tile: (list(Suit).index(tile.suit), tile.rank, tile.copy))

    def receive(self, tile: Tile) -> None:
        self.hand.append(tile)
        self.sort_hand()

    def remove_tile(self, tile: Tile) -> Tile:
        self.hand.remove(tile)
        return tile

    def count_tile(self, tile: Tile) -> int:
        return sum(1 for item in self.hand if item.key == tile.key)

    def has_missing_tiles(self) -> bool:
        return self.missing_suit is not None and any(tile.suit is self.missing_suit for tile in self.hand)

    def legal_discards(self) -> list[Tile]:
        if self.missing_suit is None:
            return []
        missing_tiles = [tile for tile in self.hand if tile.suit is self.missing_suit]
        return missing_tiles or list(self.hand)
