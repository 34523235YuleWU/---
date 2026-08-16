from __future__ import annotations

from collections import Counter

from .models import Meld, Player, Suit, Tile


class SichuanRules:
    """Core Sichuan Mahjong rules used by the program."""

    def make_wall(self) -> list[Tile]:
        return [
            Tile(suit=suit, rank=rank, copy=copy)
            for suit in Suit
            for rank in range(1, 10)
            for copy in range(4)
        ]

    def choose_missing_suit(self, player: Player) -> Suit:
        counts = Counter(tile.suit for tile in player.hand)
        return min(Suit, key=lambda suit: (counts[suit], suit.value))

    def can_discard(self, player: Player, tile: Tile) -> bool:
        return tile in player.legal_discards()

    def can_win(self, player: Player, extra_tile: Tile | None = None) -> bool:
        hand = list(player.hand)
        if extra_tile is not None:
            hand.append(extra_tile)
        if len(hand) % 3 != 2:
            return False
        if player.missing_suit and any(tile.suit is player.missing_suit for tile in hand):
            return False
        return self.is_seven_pairs(hand) or self.is_standard_hand(hand)

    def can_peng(self, player: Player, tile: Tile) -> bool:
        return not player.won and tile.suit is not player.missing_suit and player.count_tile(tile) >= 2

    def can_gang_from_discard(self, player: Player, tile: Tile) -> bool:
        return not player.won and tile.suit is not player.missing_suit and player.count_tile(tile) >= 3

    def concealed_gang_tile(self, player: Player) -> Tile | None:
        counts = Counter(tile.key for tile in player.hand)
        gang_key = next((key for key, count in counts.items() if count == 4), None)
        if gang_key is None:
            return None
        return next(tile for tile in player.hand if tile.key == gang_key)

    def fan_names(self, player: Player) -> list[str]:
        names: list[str] = []
        if self.is_seven_pairs(player.hand):
            names.append("七对")
        if self.is_all_triplets(player):
            names.append("碰碰胡")
        if self.is_pure_suit(player):
            names.append("清一色")
        return names or ["平胡"]

    def fan_score(self, player: Player) -> int:
        names = self.fan_names(player)
        if names == ["平胡"]:
            return 1
        return 2 ** len(names)

    def is_seven_pairs(self, hand: list[Tile]) -> bool:
        if len(hand) != 14:
            return False
        counts = Counter(tile.key for tile in hand)
        return all(count in (2, 4) for count in counts.values())

    def is_all_triplets(self, player: Player) -> bool:
        if any(meld.kind not in {"peng", "ming_gang", "an_gang"} for meld in player.melds):
            return False
        counts = Counter(tile.key for tile in player.hand)
        pair_count = 0
        for count in counts.values():
            if count == 2:
                pair_count += 1
            elif count not in (0, 3):
                return False
        return pair_count == 1

    def is_pure_suit(self, player: Player) -> bool:
        suits = {tile.suit for tile in player.hand}
        suits.update(meld.tile.suit for meld in player.melds)
        return len(suits) == 1

    def is_standard_hand(self, hand: list[Tile]) -> bool:
        counts_by_suit = {suit: [0] * 10 for suit in Suit}
        for tile in hand:
            counts_by_suit[tile.suit][tile.rank] += 1

        for suit in Suit:
            for rank in range(1, 10):
                if counts_by_suit[suit][rank] < 2:
                    continue
                counts_by_suit[suit][rank] -= 2
                if all(self._can_form_melds(counts[:]) for counts in counts_by_suit.values()):
                    counts_by_suit[suit][rank] += 2
                    return True
                counts_by_suit[suit][rank] += 2
        return False

    def _can_form_melds(self, counts: list[int]) -> bool:
        for rank in range(1, 10):
            while counts[rank] > 0:
                if counts[rank] >= 3:
                    counts[rank] -= 3
                elif rank <= 7 and counts[rank + 1] > 0 and counts[rank + 2] > 0:
                    counts[rank] -= 1
                    counts[rank + 1] -= 1
                    counts[rank + 2] -= 1
                else:
                    return False
        return True

    def make_peng(self, player: Player, tile: Tile) -> None:
        self._remove_same_tiles(player, tile, 2)
        player.melds.append(Meld("peng", tile))

    def make_ming_gang(self, player: Player, tile: Tile) -> None:
        self._remove_same_tiles(player, tile, 3)
        player.melds.append(Meld("ming_gang", tile))

    def make_an_gang(self, player: Player, tile: Tile) -> None:
        self._remove_same_tiles(player, tile, 4)
        player.melds.append(Meld("an_gang", tile, exposed=False))

    def _remove_same_tiles(self, player: Player, tile: Tile, amount: int) -> None:
        removed = 0
        for item in list(player.hand):
            if item.key == tile.key and removed < amount:
                player.hand.remove(item)
                removed += 1
