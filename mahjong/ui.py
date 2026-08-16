from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

try:
    import winsound
except ImportError:  # pragma: no cover - non-Windows fallback.
    winsound = None

from .game import MahjongGame
from .models import Meld, Suit, Tile
from .online import OnlineClient


@dataclass(frozen=True)
class TableTheme:
    felt: str = "#0f6b53"
    felt_dark: str = "#084233"
    rail: str = "#5a321e"
    rail_light: str = "#8b5634"
    panel: str = "#123d34"
    tile_face: str = "#fff8e8"
    tile_edge: str = "#d6bd85"
    tile_shadow: str = "#8c6c34"
    disabled_tile: str = "#cfc6ad"
    text_light: str = "#fff4d4"
    text_dim: str = "#c8dacd"
    accent: str = "#d8452e"
    gold: str = "#f0c44f"


class MahjongApp:
    def __init__(self) -> None:
        self.game = MahjongGame()
        self.theme = TableTheme()
        self.root = tk.Tk()
        self.root.title("单机川麻")
        self.root.geometry("1280x820")
        self.root.minsize(1040, 700)
        self.status_var = tk.StringVar(value="点击“新开一局”开始。")
        self.username_var = tk.StringVar(value="")
        self.server_url_var = tk.StringVar(value="wss://yulewu-de-ma-jiang.onrender.com")
        self.room_code_var = tk.StringVar(value="")
        self.login_frame: tk.Frame | None = None
        self.online_frame: tk.Frame | None = None
        self.online_status_var = tk.StringVar(value="")
        self.online_room_code_var = tk.StringVar(value="未加入房间")
        self.online_players_var = tk.StringVar(value="")
        self.online_client: OnlineClient | None = None
        self.online_player_id = ""
        self.online_room: dict[str, object] | None = None
        self.online_in_game = False
        self.online_needs_draw = False
        self.online_wall_count: int | None = None
        self.action_buttons: dict[str, ttk.Button] = {}
        self.missing_buttons: dict[Suit, ttk.Button] = {}
        self.tile_images: dict[tuple[str, str | int, str, bool], tk.PhotoImage] = {}
        self.back_images: dict[str, tk.PhotoImage] = {}
        self.discard_sound_path = Path(__file__).resolve().parents[1] / "assets" / "sounds" / "discard.wav"
        self.ai_job: str | None = None
        self.load_tile_images()
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        self.show_login()

    def run(self) -> None:
        self.root.mainloop()

    def load_tile_images(self) -> None:
        asset_dir = Path(__file__).resolve().parents[1] / "assets" / "tiles_runtime"
        for suit in Suit:
            for rank in range(1, 10):
                large = tk.PhotoImage(file=asset_dir / f"{suit.value}_{rank}_large.png")
                small = tk.PhotoImage(file=asset_dir / f"{suit.value}_{rank}_small.png")
                self.tile_images[(suit.value, rank, "large", False)] = large
                self.tile_images[(suit.value, rank, "large", True)] = large
                self.tile_images[(suit.value, rank, "small", False)] = small
                self.tile_images[(suit.value, rank, "small", True)] = small
        self.back_images["large"] = tk.PhotoImage(file=asset_dir / "back_large.png")
        self.back_images["small"] = tk.PhotoImage(file=asset_dir / "back_small.png")

    def show_login(self) -> None:
        self.clear_root()
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Action.TButton", padding=(14, 8), font=("Microsoft YaHei UI", 10, "bold"))

        self.root.configure(bg="#17221d")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.login_frame = tk.Frame(self.root, bg="#17221d")
        self.login_frame.grid(row=0, column=0, sticky="nsew")
        self.login_frame.columnconfigure(0, weight=1)
        self.login_frame.rowconfigure(0, weight=1)

        card = tk.Frame(self.login_frame, bg="#f2e6ce", padx=34, pady=30)
        card.grid(row=0, column=0)
        tk.Label(card, text="单机川麻", bg="#f2e6ce", fg="#17221d", font=("Microsoft YaHei UI", 26, "bold")).pack(anchor=tk.W)
        tk.Label(card, text="创建角色，选择单机或联机", bg="#f2e6ce", fg="#5a604f", font=("Microsoft YaHei UI", 11)).pack(anchor=tk.W, pady=(4, 24))

        tk.Label(card, text="用户名", bg="#f2e6ce", fg="#1f251f", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor=tk.W)
        name_entry = ttk.Entry(card, textvariable=self.username_var, width=28, font=("Microsoft YaHei UI", 12))
        name_entry.pack(fill=tk.X, pady=(6, 14))
        name_entry.bind("<Return>", lambda _event: self.create_single_player_role())

        ttk.Button(card, text="单机进入", style="Action.TButton", command=self.create_single_player_role).pack(fill=tk.X, pady=(0, 14))

        tk.Label(card, text="联机服务器", bg="#f2e6ce", fg="#1f251f", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor=tk.W)
        ttk.Entry(card, textvariable=self.server_url_var, width=36, font=("Microsoft YaHei UI", 10)).pack(fill=tk.X, pady=(6, 10))

        online_buttons = tk.Frame(card, bg="#f2e6ce")
        online_buttons.pack(fill=tk.X)
        ttk.Button(online_buttons, text="创建联机房间", command=self.create_online_room).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(online_buttons, text="加入房间", command=self.join_online_room).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        tk.Label(card, text="房间号", bg="#f2e6ce", fg="#1f251f", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor=tk.W, pady=(14, 0))
        ttk.Entry(card, textvariable=self.room_code_var, width=20, font=("Microsoft YaHei UI", 12)).pack(fill=tk.X, pady=(6, 0))

        tips = "联机创建后，把房间号发给朋友；开始时空位会自动补 AI。"
        tk.Label(card, text=tips, bg="#f2e6ce", fg="#6d634f", font=("Microsoft YaHei UI", 9)).pack(anchor=tk.W, pady=(18, 0))
        name_entry.focus_set()

    def valid_username(self) -> str | None:
        username = self.username_var.get().strip()
        if not username:
            messagebox.showwarning("需要用户名", "请先输入一个用户名。")
            return None
        if len(username) > 10:
            messagebox.showwarning("名字太长", "用户名最多 10 个字。")
            return None
        return username

    def create_single_player_role(self) -> None:
        username = self.valid_username()
        if username is None:
            return
        self.close_online_client()
        self.game = MahjongGame()
        self.game.players[0].name = username
        self._build_ui()
        self.status_var.set(f"欢迎，{username}。点击“新开一局”开始。")
        self.refresh()

    def create_online_room(self) -> None:
        username = self.valid_username()
        if username is None:
            return
        self.connect_online("create_room", {"username": username})

    def join_online_room(self) -> None:
        username = self.valid_username()
        if username is None:
            return
        code = self.room_code_var.get().strip().upper()
        if not code:
            messagebox.showwarning("需要房间号", "请输入朋友发给你的房间号。")
            return
        self.connect_online("join_room", {"username": username, "code": code})

    def connect_online(self, action: str, data: dict[str, str]) -> None:
        url = self.server_url_var.get().strip()
        if not url.startswith(("ws://", "wss://")):
            messagebox.showwarning("服务器地址不对", "联机服务器地址需要以 ws:// 或 wss:// 开头。")
            return
        self.close_online_client()
        try:
            self.online_client = OnlineClient(url, action, data, self.queue_online_event, self.queue_online_error)
        except RuntimeError as exc:
            messagebox.showerror("缺少联机依赖", str(exc))
            return
        self.online_status_var.set("正在连接服务器...")
        self.show_online_lobby()
        self.online_client.start()

    def show_online_lobby(self) -> None:
        if self.login_frame is not None:
            self.login_frame.destroy()
            self.login_frame = None

        self.root.configure(bg="#17221d")
        self.online_frame = tk.Frame(self.root, bg="#17221d")
        self.online_frame.grid(row=0, column=0, sticky="nsew")
        self.online_frame.columnconfigure(0, weight=1)
        self.online_frame.rowconfigure(0, weight=1)

        card = tk.Frame(self.online_frame, bg="#f2e6ce", padx=34, pady=30)
        card.grid(row=0, column=0)
        tk.Label(card, text="联机房间", bg="#f2e6ce", fg="#17221d", font=("Microsoft YaHei UI", 24, "bold")).pack(anchor=tk.W)
        tk.Label(card, textvariable=self.online_status_var, bg="#f2e6ce", fg="#5a604f", font=("Microsoft YaHei UI", 10)).pack(anchor=tk.W, pady=(4, 18))
        tk.Label(card, textvariable=self.online_room_code_var, bg="#f2e6ce", fg="#7a251f", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor=tk.W)
        tk.Label(card, text="玩家列表", bg="#f2e6ce", fg="#1f251f", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor=tk.W, pady=(20, 6))
        tk.Label(card, textvariable=self.online_players_var, bg="#fff8e8", fg="#263028", justify=tk.LEFT, width=34, height=8, anchor=tk.NW, padx=10, pady=10).pack(fill=tk.X)
        ttk.Button(card, text="开始游戏", style="Action.TButton", command=self.start_online_game).pack(fill=tk.X, pady=(18, 8))
        ttk.Button(card, text="返回登录", command=self.leave_online_lobby).pack(fill=tk.X)

    def queue_online_event(self, event: str, data: dict[str, object]) -> None:
        self.root.after(0, lambda: self.handle_online_event(event, data))

    def queue_online_error(self, message: str) -> None:
        self.root.after(0, lambda: self.handle_online_error(message))

    def handle_online_event(self, event: str, data: dict[str, object]) -> None:
        if event == "hello":
            self.online_player_id = str(data.get("playerId", ""))
            self.online_status_var.set("已连接服务器。")
            return
        if event in {"room_created", "room_joined", "room_state"}:
            if "playerId" in data:
                self.online_player_id = str(data.get("playerId"))
            room = data.get("room")
            if isinstance(room, dict):
                self.online_room = room
                self.refresh_online_room()
            return
        if event == "game_started":
            room = data.get("room")
            if isinstance(room, dict):
                self.online_room = room
                self.refresh_online_room()
            return
        if event == "game_state":
            self.apply_online_game_state(data)
            return
        if event == "error":
            self.handle_online_error(str(data.get("message", "服务器返回错误。")))

    def handle_online_error(self, message: str) -> None:
        self.online_status_var.set(message)
        messagebox.showerror("联机错误", message)

    def refresh_online_room(self) -> None:
        if self.online_room is None:
            return
        code = str(self.online_room.get("code", ""))
        self.online_room_code_var.set(f"房间号：{code}")
        players = self.online_room.get("players", [])
        lines: list[str] = []
        if isinstance(players, list):
            for player in players:
                if not isinstance(player, dict):
                    continue
                seat = int(player.get("seat", 0)) + 1
                name = str(player.get("username", "玩家"))
                marks = []
                if player.get("isHost"):
                    marks.append("房主")
                if player.get("isAi"):
                    marks.append("AI")
                suffix = f"（{'，'.join(marks)}）" if marks else ""
                lines.append(f"{seat}号位  {name}{suffix}")
        self.online_players_var.set("\n".join(lines) or "等待玩家加入...")
        self.online_status_var.set("把房间号发给朋友，房主可以开始游戏。")

    def start_online_game(self) -> None:
        if self.online_client is None:
            return
        self.online_client.send("start_game", {})

    def apply_online_game_state(self, state: dict[str, object]) -> None:
        first_state = not self.online_in_game
        self.online_in_game = True
        self.online_needs_draw = bool(state.get("needsDraw"))
        self.online_wall_count = int(state.get("wallCount", 0))
        self.game.round_over = bool(state.get("roundOver"))
        self.game.current_index = int(state.get("currentRelative", 0))
        self.game.dealer_index = int(state.get("dealerRelative", 0))
        dice = state.get("dice", [1, 1])
        if isinstance(dice, list) and len(dice) == 2:
            self.game.dice = (int(dice[0]), int(dice[1]))
        self.game.wall = [Tile(Suit.WAN, 1, 0)] * self.online_wall_count
        self.game.log = [str(item) for item in state.get("log", [])] if isinstance(state.get("log"), list) else []

        players = state.get("players", [])
        if isinstance(players, list):
            for index, player_state in enumerate(players[:4]):
                if not isinstance(player_state, dict):
                    continue
                player = self.game.players[index]
                player.name = str(player_state.get("username", "玩家"))
                player.score = int(player_state.get("score", 0))
                player.won = bool(player_state.get("won"))
                missing = player_state.get("missingSuit")
                player.missing_suit = Suit(str(missing)) if missing else None
                player.discards = [self.tile_from_dict(tile) for tile in player_state.get("discards", []) if isinstance(tile, dict)]
                player.melds = [self.meld_from_dict(meld) for meld in player_state.get("melds", []) if isinstance(meld, dict)]
                if index == 0:
                    player.hand = [self.tile_from_dict(tile) for tile in player_state.get("hand", []) if isinstance(tile, dict)]
                    player.sort_hand()
                else:
                    count = int(player_state.get("handCount", 0))
                    player.hand = [Tile(Suit.WAN, 1, copy) for copy in range(count)]

        last = state.get("lastDiscard")
        self.game.last_discard = self.tile_from_dict(last) if isinstance(last, dict) else None

        if first_state:
            self._build_ui()
        room = state.get("room")
        code = ""
        if isinstance(room, dict):
            self.online_room = room
            code = str(room.get("code", ""))
        self.status_var.set(self.online_status_text(code))
        self.refresh()

    def tile_from_dict(self, data: dict[str, object]) -> Tile:
        return Tile(Suit(str(data.get("suit"))), int(data.get("rank", 1)), int(data.get("copy", 0)))

    def meld_from_dict(self, data: dict[str, object]) -> Meld:
        tile_data = data.get("tile")
        tile = self.tile_from_dict(tile_data) if isinstance(tile_data, dict) else Tile(Suit.WAN, 1, 0)
        return Meld(str(data.get("kind", "peng")), tile, bool(data.get("exposed", True)))

    def online_status_text(self, code: str) -> str:
        if self.game.round_over:
            return f"联机房间 {code} 本局结束。"
        if self.game.current_index != 0:
            return f"联机房间 {code}：等待 {self.game.players[self.game.current_index].name} 操作。"
        if self.game.players[0].missing_suit is None:
            return f"联机房间 {code}：请选择定缺。"
        if self.online_needs_draw:
            return f"联机房间 {code}：轮到你摸牌。"
        return f"联机房间 {code}：轮到你出牌。"

    def leave_online_lobby(self) -> None:
        self.close_online_client()
        if self.online_frame is not None:
            self.online_frame.destroy()
            self.online_frame = None
        self.show_login()

    def close_online_client(self) -> None:
        if self.online_client is not None:
            self.online_client.close()
            self.online_client = None

    def close_app(self) -> None:
        self.close_online_client()
        self.root.destroy()

    def return_to_start(self) -> None:
        if self.ai_job is not None:
            self.root.after_cancel(self.ai_job)
            self.ai_job = None
        self.close_online_client()
        self.game = MahjongGame()
        self.status_var.set("点击“新开一局”开始。")
        self.online_in_game = False
        self.online_needs_draw = False
        self.online_wall_count = None
        self.online_room = None
        self.online_player_id = ""
        self.online_status_var.set("")
        self.online_room_code_var.set("未加入房间")
        self.online_players_var.set("")
        self.show_login()

    def clear_root(self) -> None:
        for child in self.root.winfo_children():
            child.destroy()
        self.login_frame = None
        self.online_frame = None
        for index in range(4):
            self.root.columnconfigure(index, weight=0)
            self.root.rowconfigure(index, weight=0)

    def _build_ui(self) -> None:
        self.clear_root()
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Action.TButton", padding=(14, 8), font=("Microsoft YaHei UI", 10, "bold"))

        self.root.configure(bg="#1d251f")
        for index in range(2):
            self.root.columnconfigure(index, weight=0)
        self.root.rowconfigure(0, weight=0)
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=0)
        self.root.rowconfigure(1, weight=1)

        toolbar = tk.Frame(self.root, bg="#20271f", padx=14, pady=10)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        tk.Label(
            toolbar,
            text="单机川麻",
            bg="#20271f",
            fg="#fff4d4",
            font=("Microsoft YaHei UI", 20, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            toolbar,
            textvariable=self.status_var,
            bg="#20271f",
            fg="#d8e9df",
            font=("Microsoft YaHei UI", 10),
        ).pack(side=tk.LEFT, padx=18)
        ttk.Button(toolbar, text="新开一局", style="Action.TButton", command=self.new_game).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(toolbar, text="规则", style="Action.TButton", command=self.show_rules).pack(side=tk.RIGHT)
        ttk.Button(toolbar, text="返回开始", style="Action.TButton", command=self.return_to_start).pack(side=tk.RIGHT, padx=(0, 8))

        table_frame = tk.Frame(self.root, bg="#1d251f")
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(table_frame, bg="#1d251f", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _event: self.refresh())

        side = tk.Frame(self.root, width=280, bg="#f2e6ce", padx=12, pady=12)
        side.grid(row=1, column=1, sticky="ns")
        side.grid_propagate(False)

        tk.Label(side, text="定缺", bg="#f2e6ce", fg="#1f251f", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor=tk.W)
        missing_row = tk.Frame(side, bg="#f2e6ce")
        missing_row.pack(fill=tk.X, pady=(6, 16))
        for suit in Suit:
            button = ttk.Button(missing_row, text=f"缺{suit.label}", command=lambda s=suit: self.set_missing(s))
            button.pack(side=tk.LEFT, padx=(0, 6))
            self.missing_buttons[suit] = button

        tk.Label(side, text="操作", bg="#f2e6ce", fg="#1f251f", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor=tk.W)
        action_grid = tk.Frame(side, bg="#f2e6ce")
        action_grid.pack(fill=tk.X, pady=(6, 16))
        actions = [
            ("draw", "摸牌", self.human_draw),
            ("hu", "胡", self.human_hu),
            ("peng", "碰", self.human_peng),
            ("gang", "杠", self.human_gang),
            ("pass", "过", self.pass_claim),
        ]
        for offset, (key, text, command) in enumerate(actions):
            button = ttk.Button(action_grid, text=text, command=command)
            button.grid(row=offset // 2, column=offset % 2, sticky="ew", padx=3, pady=3)
            action_grid.columnconfigure(offset % 2, weight=1)
            self.action_buttons[key] = button

        tk.Label(side, text="分数", bg="#f2e6ce", fg="#1f251f", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor=tk.W)
        self.score_label = tk.Label(side, text="", bg="#f2e6ce", fg="#263028", justify=tk.LEFT, font=("Microsoft YaHei UI", 10))
        self.score_label.pack(anchor=tk.W, fill=tk.X, pady=(6, 16))

        tk.Label(side, text="牌局记录", bg="#f2e6ce", fg="#1f251f", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor=tk.W)
        self.log_box = tk.Listbox(
            side,
            width=32,
            height=26,
            bd=0,
            highlightthickness=1,
            highlightbackground="#d2bf9a",
            bg="#fff8e8",
            fg="#2c332c",
            font=("Microsoft YaHei UI", 9),
        )
        self.log_box.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        self.refresh()

    def new_game(self) -> None:
        if self.online_in_game:
            self.status_var.set("联机房间由服务器发牌，不能本地新开一局。")
            return
        if self.ai_job is not None:
            self.root.after_cancel(self.ai_job)
            self.ai_job = None
        self.game.start()
        self.status_var.set("请选择定缺。定缺后点击“摸牌”。")
        self.refresh()

    def set_missing(self, suit: Suit) -> None:
        if self.online_in_game:
            if self.online_client is not None:
                self.online_client.send("game_action", {"type": "set_missing", "suit": suit.value})
            return
        if self.game.round_over:
            return
        self.game.set_human_missing_suit(suit)
        self.continue_after_user_action()

    def human_draw(self) -> None:
        if self.online_in_game:
            if self.online_client is not None:
                self.online_client.send("game_action", {"type": "draw"})
            return
        tile = self.game.human_draw()
        if tile is None:
            self.status_var.set("现在不能摸牌。")
        else:
            self.status_var.set("已摸牌，请打一张。")
        self.refresh()

    def discard_tile(self, tile: Tile) -> None:
        if self.online_in_game:
            if self.online_client is not None:
                self.online_client.send("game_action", {"type": "discard", "tile": self.tile_id(tile)})
            return
        if self.game.players[0].missing_suit is None:
            self.status_var.set("请先定缺。")
            return
        if self.game.pending_claim is not None:
            self.status_var.set("请先处理胡、碰、杠或过。")
            return
        try:
            self.game.human_discard(tile)
        except ValueError as exc:
            self.status_var.set(str(exc))
            self.refresh()
            return
        self.play_discard_sound()
        self.continue_after_user_action()

    def human_hu(self) -> None:
        self.game.human_hu()
        self.continue_after_user_action()

    def human_peng(self) -> None:
        self.game.human_peng()
        self.status_var.set("碰牌后请打一张。")
        self.refresh()

    def human_gang(self) -> None:
        self.game.human_gang()
        self.continue_after_user_action()

    def pass_claim(self) -> None:
        self.game.pass_claim()
        self.continue_after_user_action()

    def continue_after_user_action(self) -> None:
        self.update_status_after_turn()
        self.refresh()
        self.schedule_ai()

    def schedule_ai(self) -> None:
        if self.ai_job is not None:
            return
        if self.game.round_over or self.game.pending_claim is not None or self.game.current_index == 0:
            return
        self.ai_job = self.root.after(180, self.run_ai_step)

    def run_ai_step(self) -> None:
        self.ai_job = None
        discard_count = self.total_discard_count()
        acted = self.game.run_one_ai_action()
        if acted:
            if self.total_discard_count() > discard_count:
                self.play_discard_sound()
            self.update_status_after_turn()
            self.refresh()
        self.schedule_ai()

    def total_discard_count(self) -> int:
        return sum(len(player.discards) for player in self.game.players)

    def tile_id(self, tile: Tile) -> str:
        return f"{tile.suit.value}-{tile.rank}-{tile.copy}"

    def play_discard_sound(self) -> None:
        if winsound is None or not self.discard_sound_path.exists():
            self.root.bell()
            return
        winsound.PlaySound(str(self.discard_sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)

    def update_status_after_turn(self) -> None:
        if self.game.round_over:
            self.status_var.set("本局结束。可以新开一局。")
        elif self.game.pending_claim is not None:
            claim = self.game.pending_claim
            actions = []
            if claim.can_hu:
                actions.append("胡")
            if claim.can_peng:
                actions.append("碰")
            if claim.can_gang:
                actions.append("杠")
            self.status_var.set(f"{self.game.players[claim.from_index].name}打出 {claim.tile.label}，你可以{'/'.join(actions)}。")
        elif self.game.current_index == 0:
            if self.game.human_needs_draw():
                self.status_var.set("轮到你摸牌。")
            else:
                self.status_var.set("轮到你出牌。")
        else:
            self.status_var.set(f"{self.game.current_player.name}思考中。")

    def refresh(self) -> None:
        if not hasattr(self, "canvas"):
            return
        self.canvas.delete("all")
        self.draw_table()
        self.draw_center()
        self.draw_seats()
        self.draw_discards()
        self.draw_melds()
        self.draw_human_hand()
        self.refresh_scores()
        self.refresh_log()
        self.refresh_actions()
        self.refresh_missing_buttons()

    def draw_table(self) -> None:
        width = max(self.canvas.winfo_width(), 900)
        height = max(self.canvas.winfo_height(), 620)
        t = self.theme
        size = min(width - 120, height - 90)
        x1 = (width - size) / 2
        y1 = (height - size) / 2
        x2 = x1 + size
        y2 = y1 + size
        self.canvas.create_rectangle(0, 0, width, height, fill="#1d251f", outline="")
        self.round_rect(x1, y1, x2, y2, 26, fill=t.rail, outline=t.rail_light, width=10)
        self.round_rect(x1 + 34, y1 + 34, x2 - 34, y2 - 34, 16, fill=t.felt, outline=t.felt_dark, width=8)
        self.round_rect(x1 + size * 0.24, y1 + size * 0.24, x2 - size * 0.24, y2 - size * 0.24, 10, fill="#116f56", outline="#0b4d3c", width=3)

    def draw_center(self) -> None:
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        cx, cy = width / 2, height * 0.42
        t = self.theme
        self.round_rect(cx - 150, cy - 88, cx + 150, cy + 108, 18, fill=t.panel, outline="#1f7a61", width=2)
        self.canvas.create_text(cx, cy - 60, text=f"牌墙 {len(self.game.wall)}", fill=t.gold, font=("Microsoft YaHei UI", 18, "bold"))
        last = self.game.last_discard.label if self.game.last_discard else "无"
        self.canvas.create_text(cx, cy - 26, text=f"最近弃牌：{last}", fill=t.text_light, font=("Microsoft YaHei UI", 12, "bold"))
        self.draw_dice(cx - 40, cy + 4, self.game.dice[0])
        self.draw_dice(cx + 10, cy + 4, self.game.dice[1])
        dealer = self.game.players[self.game.dealer_index].name
        self.canvas.create_text(cx, cy + 48, text=f"庄家：{dealer}", fill=t.gold, font=("Microsoft YaHei UI", 10, "bold"))
        short_status = self.status_var.get()
        if len(short_status) > 28:
            short_status = short_status[:27] + "..."
        self.canvas.create_text(cx, cy + 78, text=short_status, fill=t.text_dim, font=("Microsoft YaHei UI", 10))

    def draw_seats(self) -> None:
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        positions = {
            0: (width / 2, height - 132, "bottom"),
            1: (width - 142, height * 0.46, "right"),
            2: (width / 2, 98, "top"),
            3: (142, height * 0.46, "left"),
        }
        for index, (x, y, side) in positions.items():
            player = self.game.players[index]
            active = not self.game.round_over and self.game.current_index == index and not player.won
            missing = player.missing_suit.label if player.missing_suit else "未定"
            status = "已胡" if player.won else f"缺{missing}"
            dealer_mark = "  庄" if index == self.game.dealer_index else ""
            fill = self.theme.gold if active else self.theme.text_light
            self.canvas.create_text(x, y - 30, text=f"{player.name}{dealer_mark}", fill=fill, font=("Microsoft YaHei UI", 14, "bold"))
            self.canvas.create_text(x, y - 8, text=f"{status}  {player.score}分", fill=self.theme.text_dim, font=("Microsoft YaHei UI", 10))
            if index != 0:
                self.draw_hidden_hand(index, x, y + 18, side)

    def draw_hidden_hand(self, player_index: int, x: float, y: float, side: str) -> None:
        count = len(self.game.players[player_index].hand)
        if side in {"top", "bottom"}:
            start = x - count * 10
            for offset in range(count):
                self.draw_tile_back(start + offset * 20, y, 18, 28)
        else:
            start = y - count * 6
            for offset in range(count):
                self.draw_tile_back(x, start + offset * 12, 28, 18)

    def draw_discards(self) -> None:
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        zones = {
            0: (width / 2 - 170, height * 0.61, 10, 0),
            1: (width * 0.66, height * 0.36, 0, 10),
            2: (width / 2 - 170, height * 0.22, 10, 0),
            3: (width * 0.25, height * 0.36, 0, 10),
        }
        for index, (x, y, dx, dy) in zones.items():
            for tile_index, tile in enumerate(self.game.players[index].discards[-24:]):
                row = tile_index // 8
                col = tile_index % 8
                self.draw_tile_face(x + col * (32 + dx), y + row * (42 + dy), 30, 40, tile, small=True)

    def draw_melds(self) -> None:
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        positions = {
            0: (width * 0.16, height - 112, "horizontal"),
            1: (width - 240, height * 0.68, "vertical"),
            2: (width * 0.16, 138, "horizontal"),
            3: (86, height * 0.68, "vertical"),
        }
        for index, (x, y, direction) in positions.items():
            for meld_index, meld in enumerate(self.game.players[index].melds):
                if direction == "horizontal":
                    mx = x + meld_index * 140
                    self.draw_meld_tiles(meld, mx, y, horizontal=True)
                else:
                    my = y - meld_index * 70
                    self.draw_meld_tiles(meld, x, my, horizontal=False)

    def draw_meld_tiles(self, meld: Meld, x: float, y: float, horizontal: bool) -> None:
        count = 4 if "gang" in meld.kind else 3
        gap = 4
        tile_w, tile_h = 30, 40
        label = {"peng": "碰", "ming_gang": "杠", "an_gang": "暗杠"}.get(meld.kind, meld.kind)
        if horizontal:
            self.canvas.create_text(x + 18, y - 8, text=label, fill=self.theme.gold, font=("Microsoft YaHei UI", 8, "bold"))
            for offset in range(count):
                tx = x + offset * (tile_w + gap)
                if meld.exposed:
                    self.draw_tile_face(tx, y, tile_w, tile_h, meld.tile, small=True)
                else:
                    self.draw_tile_back(tx, y, tile_w, tile_h)
            return

        self.canvas.create_text(x + 24, y - 10, text=label, fill=self.theme.gold, font=("Microsoft YaHei UI", 8, "bold"))
        for offset in range(count):
            ty = y + offset * (tile_h + gap)
            if meld.exposed:
                self.draw_tile_face(x, ty, tile_w, tile_h, meld.tile, small=True)
            else:
                self.draw_tile_back(x, ty, tile_w, tile_h)

    def draw_human_hand(self) -> None:
        human = self.game.players[0]
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        tile_w, tile_h = 60, 80
        gap = 6
        total_width = len(human.hand) * tile_w + max(0, len(human.hand) - 1) * gap
        start_x = max(24, (width - total_width) / 2)
        y = height - tile_h - 24
        legal_tiles = set(human.legal_discards())

        for index, tile in enumerate(human.hand):
            x = start_x + index * (tile_w + gap)
            enabled = (
                not self.game.round_over
                and self.game.current_index == 0
                and self.game.pending_claim is None
                and human.missing_suit is not None
                and not self.game.human_needs_draw()
                and not human.won
                and tile in legal_tiles
            )
            tag = f"human_tile_{index}"
            self.draw_tile_face(x, y, tile_w, tile_h, tile, tag=tag, disabled=not enabled)
            if enabled:
                self.canvas.tag_bind(tag, "<Button-1>", lambda _event, selected=tile: self.discard_tile(selected))
                self.canvas.tag_bind(tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
                self.canvas.tag_bind(tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))

    def draw_tile_face(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        tile: Tile,
        tag: str | None = None,
        small: bool = False,
        disabled: bool = False,
    ) -> None:
        tags = (tag,) if tag else ()
        if not small:
            self.canvas.create_rectangle(x + 3, y + 5, x + w + 3, y + h + 5, fill=self.theme.tile_shadow, outline="", tags=tags)
        size = "small" if small else "large"
        image = self.tile_images[(tile.suit.value, tile.rank, size, disabled)]
        self.canvas.create_image(x, y, anchor=tk.NW, image=image, tags=tags)

    def draw_tile_back(self, x: float, y: float, w: float, h: float) -> None:
        image = self.back_images["small"]
        self.round_rect(x + 2, y + 3, x + image.width() + 2, y + image.height() + 3, 4, fill="#4d211d", outline="")
        self.canvas.create_image(x, y, anchor=tk.NW, image=image)

    def draw_dice(self, x: float, y: float, value: int) -> None:
        self.round_rect(x, y, x + 30, y + 30, 6, fill="#fff8e8", outline="#d6bd85", width=2)
        spots = {
            1: [(15, 15)],
            2: [(9, 9), (21, 21)],
            3: [(9, 9), (15, 15), (21, 21)],
            4: [(9, 9), (21, 9), (9, 21), (21, 21)],
            5: [(9, 9), (21, 9), (15, 15), (9, 21), (21, 21)],
            6: [(9, 8), (21, 8), (9, 15), (21, 15), (9, 22), (21, 22)],
        }
        for dx, dy in spots[value]:
            self.canvas.create_oval(x + dx - 3, y + dy - 3, x + dx + 3, y + dy + 3, fill="#27231d", outline="")

    def round_rect(self, x1: float, y1: float, x2: float, y2: float, radius: float, **kwargs: object) -> int:
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def refresh_scores(self) -> None:
        lines = []
        for player in self.game.players:
            missing = player.missing_suit.label if player.missing_suit else "未定"
            state = "已胡" if player.won else "游戏中"
            lines.append(f"{player.name}：{player.score} 分  缺{missing}  {state}")
        self.score_label.configure(text="\n".join(lines))

    def refresh_log(self) -> None:
        self.log_box.delete(0, tk.END)
        for item in self.game.log:
            self.log_box.insert(tk.END, item)

    def refresh_actions(self) -> None:
        claim = self.game.pending_claim
        human = self.game.players[0]
        if self.online_in_game:
            is_my_turn = self.game.current_index == 0 and not self.game.round_over
            can_draw = is_my_turn and self.online_needs_draw
            self.action_buttons["draw"].configure(state=tk.NORMAL if can_draw else tk.DISABLED)
            self.action_buttons["hu"].configure(state=tk.DISABLED)
            self.action_buttons["peng"].configure(state=tk.DISABLED)
            self.action_buttons["gang"].configure(state=tk.DISABLED)
            self.action_buttons["pass"].configure(state=tk.DISABLED)
            return
        can_draw = self.game.human_needs_draw()
        can_self_hu = (
            not self.game.round_over
            and self.game.current_index == 0
            and not self.game.human_needs_draw()
            and self.game.rules.can_win(human)
        )
        can_hu = bool((claim and claim.can_hu) or can_self_hu)
        can_peng = bool(claim and claim.can_peng)
        can_gang = bool(
            (claim and claim.can_gang)
            or (
                not self.game.round_over
                and self.game.current_index == 0
                and self.game.rules.concealed_gang_tile(human) is not None
            )
        )
        self.action_buttons["draw"].configure(state=tk.NORMAL if can_draw else tk.DISABLED)
        self.action_buttons["hu"].configure(state=tk.NORMAL if can_hu else tk.DISABLED)
        self.action_buttons["peng"].configure(state=tk.NORMAL if can_peng else tk.DISABLED)
        self.action_buttons["gang"].configure(state=tk.NORMAL if can_gang else tk.DISABLED)
        self.action_buttons["pass"].configure(state=tk.NORMAL if claim else tk.DISABLED)

    def refresh_missing_buttons(self) -> None:
        human = self.game.players[0]
        for suit, button in self.missing_buttons.items():
            enabled = not self.game.round_over and human.missing_suit is None
            if self.online_in_game:
                enabled = enabled and self.game.current_index == 0
            text = f"缺{suit.label}"
            if human.missing_suit is suit:
                text = f"已缺{suit.label}"
            button.configure(text=text, state=tk.NORMAL if enabled else tk.DISABLED)

    def show_rules(self) -> None:
        messagebox.showinfo(
            "当前规则",
            "当前程序实现：\n"
            "1. 只使用万、条、筒三门，共 108 张。\n"
            "2. 开局定缺，有缺门必须先打缺门，有缺门不能胡。\n"
            "3. 血战到底，有人胡后本局继续。\n"
            "4. 支持碰、明杠、暗杠和基础杠分。\n"
            "5. 胡牌检测支持平胡、七对、碰碰胡、清一色。",
        )
