# 联机服务器

当前联机服务器是第一版房间服务器，适合部署到 Render Free Web Service 做测试。

## 本地运行

```powershell
pip install -r requirements.txt
python server.py
```

默认监听 `ws://localhost:8000`。

## Render 部署

1. 把项目推到 GitHub。
2. 登录 Render，选择 New Web Service。
3. 连接这个仓库。
4. Render 会读取 `render.yaml`。
5. 部署完成后，得到一个类似 `https://xxx.onrender.com` 的地址。
6. WebSocket 地址是 `wss://xxx.onrender.com`。

## 协议

客户端发送：

```json
{"action":"create_room","data":{"username":"Alice"}}
```

```json
{"action":"join_room","data":{"username":"Bob","code":"ABC123"}}
```

```json
{"action":"start_game","data":{}}
```

开始游戏时不要求真人满 4 个。房主点击开始后，服务器会自动把空座位补成 AI 玩家。

```json
{"action":"game_action","data":{"type":"discard","tile":"wan-1"}}
```

服务端返回统一格式：

```json
{"event":"room_state","data":{"room":{}}}
```

## 当前范围

- 支持创建房间、加入房间、离开房间。
- 支持最多 4 名玩家。
- 支持真人不足 4 人时自动补 AI 座位。
- 支持广播玩家列表和游戏动作。
- 房间状态暂时存在服务器内存里，Render 免费服务休眠或重启后房间会消失。

下一步可以把 `MahjongGame` 移到服务器端作为权威牌局，让客户端只负责显示和提交操作。
