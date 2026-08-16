from __future__ import annotations

import random
from dataclasses import dataclass

from .models import Player, Suit, Tile
from .rules import SichuanRules


@dataclass
class Claim:
    from_index: int
    tile: Tile
    can_hu: bool
    can_peng: bool
    can_gang: bool


class MahjongGame:
    def __init__(self, rules: SichuanRules | None = None) -> None:
        self.rules = rules or SichuanRules()
        self.players = [
            Player("你", is_human=True),
            Player("下家"),
            Player("对家"),
            Player("上家"),
        ]
        self.wall: list[Tile] = []
        self.current_index = 0
        self.pending_claim: Claim | None = None
        self.last_discard: Tile | None = None
        self.dealer_index = 0
        self.dice: tuple[int, int] = (1, 1)
        self.log: list[str] = []
        self.round_over = True

    @property
    def current_player(self) -> Player:
        return self.players[self.current_index]

    def start(self) -> None:
        self.wall = self.rules.make_wall()
        random.shuffle(self.wall)
        for player in self.players:
            player.hand.clear()
            player.discards.clear()
            player.melds.clear()
            player.missing_suit = None
            player.score = 0
            player.won = False
        self.log.clear()
        self.pending_claim = None
        self.last_discard = None
        self.round_over = False
        self.dice = (random.randint(1, 6), random.randint(1, 6))
        self.dealer_index = (sum(self.dice) - 1) % len(self.players)
        self.current_index = self.dealer_index

        for _ in range(13):
            for player in self.players:
                player.receive(self.wall.pop())
        for player in self.players[1:]:
            player.missing_suit = self.rules.choose_missing_suit(player)
        self.add_log(
            f"掷骰子：{self.dice[0]} + {self.dice[1]} = {sum(self.dice)}，"
            f"{self.players[self.dealer_index].name}坐庄。"
        )
        self.add_log("新局开始。请选择定缺。")

    def set_human_missing_suit(self, suit: Suit) -> None:
        self.players[0].missing_suit = suit
        self.add_log(f"你定缺{suit.label}。")
        for player in self.players[1:]:
            self.add_log(f"{player.name}定缺{player.missing_suit.label}。")

    def draw_for(self, index: int) -> Tile | None:
        if not self.wall:
            self.end_round("牌墙摸完，流局。")
            return None
        tile = self.wall.pop()
        self.players[index].receive(tile)
        return tile

    def human_needs_draw(self) -> bool:
        human = self.players[0]
        return (
            not self.round_over
            and self.current_index == 0
            and self.pending_claim is None
            and human.missing_suit is not None
            and not human.won
            and len(human.hand) % 3 == 1
        )

    def human_draw(self) -> Tile | None:
        if not self.human_needs_draw():
            return None
        tile = self.draw_for(0)
        if tile is not None:
            self.add_log(f"你摸牌。")
        return tile

    def human_discard(self, tile: Tile) -> None:
        if self.current_index != 0 or self.players[0].won:
            return
        if self.human_needs_draw():
            raise ValueError("请先摸牌。")
        self.discard(0, tile)

    def discard(self, index: int, tile: Tile) -> None:
        player = self.players[index]
        if not self.rules.can_discard(player, tile):
            raise ValueError("有缺门牌时必须先打缺门。")
        player.remove_tile(tile)
        player.discards.append(tile)
        self.last_discard = tile
        self.add_log(f"{player.name}打出 {tile.label}。")
        self.resolve_claims(index, tile)

    def resolve_claims(self, from_index: int, tile: Tile) -> None:
        if from_index != 0:
            human = self.players[0]
            claim = Claim(
                from_index=from_index,
                tile=tile,
                can_hu=self.rules.can_win(human, tile),
                can_peng=self.rules.can_peng(human, tile),
                can_gang=self.rules.can_gang_from_discard(human, tile),
            )
            if claim.can_hu or claim.can_peng or claim.can_gang:
                self.pending_claim = claim
                return

        ai_winner = self.find_ai_winner(from_index, tile)
        if ai_winner is not None:
            self.win(ai_winner, tile, from_index)
            self.advance_after(from_index)
            return

        ai_meld = self.find_ai_meld(from_index, tile)
        if ai_meld is not None:
            self.ai_claim_meld(ai_meld, from_index, tile)
            return

        self.advance_after(from_index)

    def human_hu(self) -> None:
        if self.pending_claim is not None and self.pending_claim.can_hu:
            claim = self.pending_claim
            self.pending_claim = None
            self.win(0, claim.tile, claim.from_index)
            self.advance_after(0)
        elif self.rules.can_win(self.players[0]):
            self.win(0, None, 0)
            self.advance_after(0)

    def human_peng(self) -> None:
        if self.pending_claim is None or not self.pending_claim.can_peng:
            return
        claim = self.pending_claim
        self.pending_claim = None
        self.players[claim.from_index].discards.pop()
        self.rules.make_peng(self.players[0], claim.tile)
        self.current_index = 0
        self.add_log(f"你碰 {claim.tile.label}。")

    def human_gang(self) -> None:
        if self.pending_claim is not None and self.pending_claim.can_gang:
            claim = self.pending_claim
            self.pending_claim = None
            self.players[claim.from_index].discards.pop()
            self.rules.make_ming_gang(self.players[0], claim.tile)
            self.settle_gang(0, claim.from_index, concealed=False)
            self.draw_for(0)
            self.add_log(f"你明杠 {claim.tile.label}。")
            return

        tile = self.rules.concealed_gang_tile(self.players[0])
        if tile is not None:
            self.rules.make_an_gang(self.players[0], tile)
            self.settle_gang(0, 0, concealed=True)
            self.draw_for(0)
            self.add_log(f"你暗杠 {tile.label}。")

    def pass_claim(self) -> None:
        if self.pending_claim is None:
            return
        from_index = self.pending_claim.from_index
        self.pending_claim = None
        self.advance_after(from_index)

    def advance_after(self, from_index: int) -> None:
        if self.round_over:
            return
        active = [index for index, player in enumerate(self.players) if not player.won]
        if len(active) <= 1:
            self.end_round("血战到底结束。")
            return
        index = from_index
        while True:
            index = (index + 1) % len(self.players)
            if not self.players[index].won:
                break
        self.current_index = index
        if index == 0:
            self.add_log("轮到你摸牌。")
            return
        drawn = self.draw_for(index)
        if drawn is not None:
            self.add_log(f"{self.players[index].name}摸牌。")

    def run_ai_until_human(self) -> None:
        while self.run_one_ai_action():
            pass

    def run_one_ai_action(self) -> bool:
        if self.round_over or self.pending_claim is not None or self.current_index == 0:
            return False

        player = self.current_player
        if len(player.hand) % 3 == 1:
            drawn = self.draw_for(self.current_index)
            if drawn is not None:
                self.add_log(f"{player.name}摸牌。")
            return True

        if self.rules.can_win(player):
            self.win(self.current_index, None, self.current_index)
            self.advance_after(self.current_index)
            return True

        gang_tile = self.rules.concealed_gang_tile(player)
        if gang_tile is not None and random.random() < 0.3:
            self.rules.make_an_gang(player, gang_tile)
            self.settle_gang(self.current_index, self.current_index, concealed=True)
            self.draw_for(self.current_index)
            self.add_log(f"{player.name}暗杠 {gang_tile.label}。")
            return True

        self.discard(self.current_index, self.choose_ai_discard(player))
        return True

    def choose_ai_discard(self, player: Player) -> Tile:
        legal = player.legal_discards()
        return max(legal, key=lambda tile: self.discard_score(player, tile))

    def discard_score(self, player: Player, tile: Tile) -> float:
        if tile.suit is player.missing_suit:
            return 100 + tile.rank
        same_count = player.count_tile(tile)
        score = 20 - same_count * 8
        ranks = {item.rank for item in player.hand if item.suit is tile.suit}
        if tile.rank - 1 in ranks:
            score -= 5
        if tile.rank + 1 in ranks:
            score -= 5
        if tile.rank in (1, 9):
            score += 3
        return score + random.random()

    def find_ai_winner(self, from_index: int, tile: Tile) -> int | None:
        for index in self.next_indexes(from_index):
            if index != 0 and self.rules.can_win(self.players[index], tile):
                return index
        return None

    def find_ai_meld(self, from_index: int, tile: Tile) -> int | None:
        for index in self.next_indexes(from_index):
            if index == 0:
                continue
            player = self.players[index]
            if self.rules.can_gang_from_discard(player, tile) and random.random() < 0.45:
                return index
            if self.rules.can_peng(player, tile) and random.random() < 0.25:
                return index
        return None

    def ai_claim_meld(self, index: int, from_index: int, tile: Tile) -> None:
        player = self.players[index]
        self.players[from_index].discards.pop()
        if self.rules.can_gang_from_discard(player, tile) and random.random() < 0.5:
            self.rules.make_ming_gang(player, tile)
            self.settle_gang(index, from_index, concealed=False)
            self.draw_for(index)
            self.add_log(f"{player.name}明杠 {tile.label}。")
        else:
            self.rules.make_peng(player, tile)
            self.add_log(f"{player.name}碰 {tile.label}。")
        self.current_index = index

    def next_indexes(self, from_index: int) -> list[int]:
        return [(from_index + offset) % 4 for offset in range(1, 4) if not self.players[(from_index + offset) % 4].won]

    def win(self, winner_index: int, tile: Tile | None, from_index: int) -> None:
        winner = self.players[winner_index]
        if tile is not None and from_index != winner_index:
            winner.receive(tile)
        score = self.rules.fan_score(winner)
        names = "、".join(self.rules.fan_names(winner))
        if from_index == winner_index or tile is None:
            for index, player in enumerate(self.players):
                if index != winner_index and not player.won:
                    player.score -= score
                    winner.score += score
            self.add_log(f"{winner.name}自摸：{names}，每家 {score} 分。")
        else:
            self.players[from_index].score -= score
            winner.score += score
            self.add_log(f"{winner.name}胡 {tile.label}：{names}，{self.players[from_index].name}付 {score} 分。")
        winner.won = True

    def settle_gang(self, winner_index: int, from_index: int, concealed: bool) -> None:
        winner = self.players[winner_index]
        if concealed:
            value = 2
            for index, player in enumerate(self.players):
                if index != winner_index and not player.won:
                    player.score -= value
                    winner.score += value
        else:
            value = 3
            self.players[from_index].score -= value
            winner.score += value

    def end_round(self, reason: str) -> None:
        self.round_over = True
        self.add_log(reason)

    def add_log(self, text: str) -> None:
        self.log.insert(0, text)
        del self.log[80:]
