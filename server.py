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
            await self.forward_game_action(websocket, player_id, data)
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
        await self.broadcast(room, "game_started", {"room": room.public_state()})

    async def forward_game_action(self, websocket: WebSocketServerProtocol, player_id: str, data: dict[str, Any]) -> None:
        room = self.room_for_player(player_id)
        if room is None:
            await self.send_error(websocket, "你还没有加入房间。")
            return
        player = room.players[player_id]
        event = {"playerId": player_id, "seat": player.seat, "username": player.username, "action": data}
        room.event_log.append(event)
        del room.event_log[:-80]
        await self.broadcast(room, "game_action", event)

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


async def process_request(path: str, _headers: Any) -> tuple[HTTPStatus, list[tuple[str, str]], bytes] | None:
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
