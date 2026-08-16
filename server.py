from __future__ import annotations

import asyncio
import json
import os
import secrets
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any

import websockets
from websockets.server import WebSocketServerProtocol

from mahjong.game import MahjongGame
from mahjong.models import Meld, Suit, Tile


MAX_PLAYERS = 4


@dataclass
class OnlinePlayer:
    player_id: str
    username: str
    seat: int
    websocket: WebSocketServerProtocol | None
    is_ai: bool = False


@dataclass
class Room:
    code: str
    host_id: str
    players: dict[str, OnlinePlayer] = field(default_factory=dict)
    started: bool = False
    game: MahjongGame | None = None
    event_log: list[dict[str, Any]] = field(default_factory=list)

    def public_state(self) -> dict[str, Any]:
        players = sorted(self.players.values(), key=lambda player: player.seat)
        return {
            "code": self.code,
            "hostId": self.host_id,
            "started": self.started,
            "players": [
                {
                    "id": player.player_id,
                    "username": player.username,
                    "seat": player.seat,
                    "isHost": player.player_id == self.host_id,
                    "isAi": player.is_ai,
                }
                for player in players
            ],
        }


class MahjongLobbyServer:
    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}
        self.player_room: dict[str, str] = {}

    async def handle(self, websocket: WebSocketServerProtocol) -> None:
        player_id = secrets.token_hex(8)
        try:
            await self.send(websocket, "hello", {"playerId": player_id})
            async for raw_message in websocket:
                await self.handle_message(websocket, player_id, raw_message)
        except websockets.ConnectionClosed:
            pass
        finally:
            await self.disconnect(player_id)

    async def handle_message(self, websocket: WebSocketServerProtocol, player_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            await self.send_error(websocket, "消息不是有效 JSON。")
            return

        action = message.get("action")
        data = message.get("data") or {}

        if action == "create_room":
            await self.create_room(websocket, player_id, data)
        elif action == "join_room":
            await self.join_room(websocket, player_id, data)
        elif action == "leave_room":
            await self.disconnect(player_id)
        elif action == "start_game":
            await self.start_game(websocket, player_id)
        elif action == "game_action":
            await self.apply_game_action(websocket, player_id, data)
        else:
            await self.send_error(websocket, f"未知动作：{action}")

    async def create_room(self, websocket: WebSocketServerProtocol, player_id: str, data: dict[str, Any]) -> None:
        await self.disconnect(player_id)
        username = self.clean_username(data.get("username"))
        code = self.new_room_code()
        player = OnlinePlayer(player_id=player_id, username=username, seat=0, websocket=websocket)
        room = Room(code=code, host_id=player_id, players={player_id: player})
        self.rooms[code] = room
        self.player_room[player_id] = code
        await self.send(websocket, "room_created", {"room": room.public_state(), "playerId": player_id})
        await self.broadcast_room_state(room)

    async def join_room(self, websocket: WebSocketServerProtocol, player_id: str, data: dict[str, Any]) -> None:
        await self.disconnect(player_id)
        code = str(data.get("code", "")).strip().upper()
        username = self.clean_username(data.get("username"))
        room = self.rooms.get(code)
        if room is None:
            await self.send_error(websocket, "房间不存在。")
            return
        if room.started:
            await self.send_error(websocket, "牌局已经开始，暂时不能加入。")
            return
        self.remove_ai_players(room)
        if len(room.players) >= MAX_PLAYERS:
            await self.send_error(websocket, "房间已满。")
            return
        seat = self.first_free_seat(room)
        room.players[player_id] = OnlinePlayer(player_id=player_id, username=username, seat=seat, websocket=websocket)
        self.player_room[player_id] = code
        await self.send(websocket, "room_joined", {"room": room.public_state(), "playerId": player_id})
        await self.broadcast_room_state(room)

    async def start_game(self, websocket: WebSocketServerProtocol, player_id: str) -> None:
        room = self.room_for_player(player_id)
        if room is None:
            await self.send_error(websocket, "你还没有加入房间。")
            return
        if room.host_id != player_id:
            await self.send_error(websocket, "只有房主可以开始游戏。")
            return
        self.fill_ai_players(room)
        room.started = True
        room.game = MahjongGame()
        room.game.start()
        self.apply_room_players_to_game(room)
        self.prepare_ai_missing_suits(room)
        await self.broadcast(room, "game_started", {"room": room.public_state()})
        await self.run_ai_until_human_turn(room)
        await self.broadcast_game_state(room)

    async def apply_game_action(self, websocket: WebSocketServerProtocol, player_id: str, data: dict[str, Any]) -> None:
        room = self.room_for_player(player_id)
        if room is None or room.game is None:
            await self.send_error(websocket, "你还没有加入房间。")
            return
        player = room.players[player_id]
        game = room.game
        action_type = str(data.get("type", ""))

        try:
            if action_type == "set_missing":
                suit = Suit(str(data.get("suit")))
                game.players[player.seat].missing_suit = suit
                game.add_log(f"{player.username}定缺{suit.label}。")
            elif action_type == "draw":
                if not self.seat_needs_draw(game, player.seat):
                    await self.send_error(websocket, "现在不能摸牌。")
                    return
                game.draw_for(player.seat)
                game.add_log(f"{player.username}摸牌。")
            elif action_type == "discard":
                if game.current_index != player.seat:
                    await self.send_error(websocket, "还没轮到你出牌。")
                    return
                if self.seat_needs_draw(game, player.seat):
                    await self.send_error(websocket, "请先摸牌。")
                    return
                tile = self.find_tile(game.players[player.seat].hand, str(data.get("tile")))
                if tile is None:
                    await self.send_error(websocket, "这张牌不在你的手牌里。")
                    return
                game.discard(player.seat, tile)
            else:
                await self.send_error(websocket, f"未知游戏动作：{action_type}")
                return
        except ValueError as exc:
            await self.send_error(websocket, str(exc))
            return

        await self.run_ai_until_human_turn(room)
        await self.broadcast_game_state(room)

    async def disconnect(self, player_id: str) -> None:
        code = self.player_room.pop(player_id, None)
        if code is None:
            return
        room = self.rooms.get(code)
        if room is None:
            return
        room.players.pop(player_id, None)
        if not room.players:
            self.rooms.pop(code, None)
            return
        if room.host_id == player_id:
            new_host = min(room.players.values(), key=lambda player: player.seat)
            room.host_id = new_host.player_id
        await self.broadcast_room_state(room)

    def room_for_player(self, player_id: str) -> Room | None:
        code = self.player_room.get(player_id)
        if code is None:
            return None
        return self.rooms.get(code)

    async def broadcast_room_state(self, room: Room) -> None:
        await self.broadcast(room, "room_state", {"room": room.public_state()})

    async def broadcast_game_state(self, room: Room) -> None:
        if room.game is None:
            return
        stale_players: list[str] = []
        for player in list(room.players.values()):
            if player.websocket is None:
                continue
            try:
                await self.send(player.websocket, "game_state", self.personal_game_state(room, player))
            except websockets.ConnectionClosed:
                stale_players.append(player.player_id)
        for player_id in stale_players:
            await self.disconnect(player_id)

    async def broadcast(self, room: Room, event: str, data: dict[str, Any]) -> None:
        stale_players: list[str] = []
        for player in list(room.players.values()):
            if player.websocket is None:
                continue
            try:
                await self.send(player.websocket, event, data)
            except websockets.ConnectionClosed:
                stale_players.append(player.player_id)
        for player_id in stale_players:
            await self.disconnect(player_id)

    async def send_error(self, websocket: WebSocketServerProtocol, message: str) -> None:
        await self.send(websocket, "error", {"message": message})

    async def send(self, websocket: WebSocketServerProtocol, event: str, data: dict[str, Any]) -> None:
        await websocket.send(json.dumps({"event": event, "data": data}, ensure_ascii=False))

    def new_room_code(self) -> str:
        while True:
            code = secrets.token_hex(3).upper()
            if code not in self.rooms:
                return code

    def first_free_seat(self, room: Room) -> int:
        used = {player.seat for player in room.players.values()}
        for seat in range(MAX_PLAYERS):
            if seat not in used:
                return seat
        raise RuntimeError("room is full")

    def clean_username(self, value: Any) -> str:
        username = str(value or "").strip()
        return username[:10] or "玩家"

    def fill_ai_players(self, room: Room) -> None:
        ai_names = ["AI 小竹", "AI 清筒", "AI 万老板"]
        ai_index = 0
        while len(room.players) < MAX_PLAYERS:
            seat = self.first_free_seat(room)
            player_id = f"ai-{room.code}-{seat}"
            while player_id in room.players:
                player_id = f"ai-{room.code}-{seat}-{secrets.token_hex(2)}"
            room.players[player_id] = OnlinePlayer(
                player_id=player_id,
                username=ai_names[ai_index % len(ai_names)],
                seat=seat,
                websocket=None,
                is_ai=True,
            )
            ai_index += 1

    def remove_ai_players(self, room: Room) -> None:
        if room.started:
            return
        for player_id, player in list(room.players.items()):
            if player.is_ai:
                room.players.pop(player_id)

    def apply_room_players_to_game(self, room: Room) -> None:
        if room.game is None:
            return
        for player in room.players.values():
            room.game.players[player.seat].name = player.username

    def prepare_ai_missing_suits(self, room: Room) -> None:
        if room.game is None:
            return
        for player in room.players.values():
            game_player = room.game.players[player.seat]
            if player.is_ai and game_player.missing_suit is None:
                game_player.missing_suit = room.game.rules.choose_missing_suit(game_player)

    async def run_ai_until_human_turn(self, room: Room) -> None:
        if room.game is None:
            return
        while not room.game.round_over:
            current = self.player_for_seat(room, room.game.current_index)
            if current is None or not current.is_ai:
                break
            game_player = room.game.players[current.seat]
            if game_player.missing_suit is None:
                game_player.missing_suit = room.game.rules.choose_missing_suit(game_player)
                room.game.add_log(f"{current.username}定缺{game_player.missing_suit.label}。")
                continue
            if len(game_player.hand) % 3 == 1:
                room.game.draw_for(current.seat)
                room.game.add_log(f"{current.username}摸牌。")
                continue
            tile = room.game.choose_ai_discard(game_player)
            room.game.discard(current.seat, tile)
            if room.game.pending_claim is not None:
                room.game.pending_claim = None

    def personal_game_state(self, room: Room, viewer: OnlinePlayer) -> dict[str, Any]:
        game = room.game
        assert game is not None
        relative_players = []
        for offset in range(MAX_PLAYERS):
            seat = (viewer.seat + offset) % MAX_PLAYERS
            room_player = self.player_for_seat(room, seat)
            game_player = game.players[seat]
            relative_players.append(
                {
                    "seat": seat,
                    "relative": offset,
                    "username": room_player.username if room_player else game_player.name,
                    "isAi": bool(room_player and room_player.is_ai),
                    "handCount": len(game_player.hand),
                    "hand": [self.tile_to_dict(tile) for tile in game_player.hand] if seat == viewer.seat else [],
                    "discards": [self.tile_to_dict(tile) for tile in game_player.discards],
                    "melds": [self.meld_to_dict(meld) for meld in game_player.melds],
                    "missingSuit": game_player.missing_suit.value if game_player.missing_suit else None,
                    "score": game_player.score,
                    "won": game_player.won,
                }
            )
        return {
            "room": room.public_state(),
            "selfSeat": viewer.seat,
            "players": relative_players,
            "wallCount": len(game.wall),
            "currentRelative": (game.current_index - viewer.seat) % MAX_PLAYERS,
            "dealerRelative": (game.dealer_index - viewer.seat) % MAX_PLAYERS,
            "dice": list(game.dice),
            "lastDiscard": self.tile_to_dict(game.last_discard) if game.last_discard else None,
            "log": list(game.log[:20]),
            "roundOver": game.round_over,
            "needsDraw": self.seat_needs_draw(game, viewer.seat),
        }

    def player_for_seat(self, room: Room, seat: int) -> OnlinePlayer | None:
        return next((player for player in room.players.values() if player.seat == seat), None)

    def seat_needs_draw(self, game: MahjongGame, seat: int) -> bool:
        player = game.players[seat]
        return (
            not game.round_over
            and game.current_index == seat
            and game.pending_claim is None
            and player.missing_suit is not None
            and not player.won
            and len(player.hand) % 3 == 1
        )

    def find_tile(self, hand: list[Tile], tile_id: str) -> Tile | None:
        return next((tile for tile in hand if self.tile_id(tile) == tile_id), None)

    def tile_id(self, tile: Tile) -> str:
        return f"{tile.suit.value}-{tile.rank}-{tile.copy}"

    def tile_to_dict(self, tile: Tile) -> dict[str, Any]:
        return {"id": self.tile_id(tile), "suit": tile.suit.value, "rank": tile.rank, "copy": tile.copy}

    def meld_to_dict(self, meld: Meld) -> dict[str, Any]:
        return {"kind": meld.kind, "tile": self.tile_to_dict(meld.tile), "exposed": meld.exposed}


async def process_request(path: str, _headers: Any) -> tuple[HTTPStatus, list[tuple[str, str]], bytes] | None:
    upgrade = str(_headers.get("Upgrade", "")).lower()
    if upgrade == "websocket":
        return None
    if path in {"/", "/health"}:
        body = "Sichuan Mahjong WebSocket server is running.\n".encode("utf-8")
        return HTTPStatus.OK, [("Content-Type", "text/plain; charset=utf-8")], body
    return None


async def main() -> None:
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "8000"))
    server = MahjongLobbyServer()
    async with websockets.serve(server.handle, host, port, process_request=process_request):
        print(f"Sichuan Mahjong server listening on {host}:{port}")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
