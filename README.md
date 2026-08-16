# 单机川麻

这是一个本地 Python 程序版川麻小游戏，使用 `tkinter` 做方形牌桌图形界面，并用网上开源牌面资源显示麻将牌。单机客户端不需要安装第三方依赖。

## 运行

```powershell
python main.py
```

如果系统的 `python` 命令不可用，可以换成：

```powershell
py main.py
```

启动后先输入用户名创建角色，然后进入牌桌。

联机模式可以使用当前 Render 服务器地址：

```text
wss://yulewu-de-ma-jiang.onrender.com
```

## Windows 打包

运行：

```powershell
.\build_windows.ps1
```

打包完成后，可执行程序在：

```text
dist\SichuanMahjong\SichuanMahjong.exe
```

把整个 `dist\SichuanMahjong` 文件夹发给别人即可运行。程序窗口标题仍然是“单机川麻”。

## OOP 结构

- `mahjong.models.Tile`：麻将牌对象。
- `mahjong.models.Player`：玩家对象，管理手牌、弃牌、定缺、分数。
- `mahjong.rules.SichuanRules`：川麻规则对象，负责定缺建议、胡牌检测、碰杠、番型判断。
- `mahjong.game.MahjongGame`：牌局对象，负责发牌、回合推进、AI、计分和血战到底流程。
- `mahjong.ui.MahjongApp`：桌面界面对象，负责登录页、牌桌展示和按钮交互。
- `mahjong.online.OnlineClient`：联机客户端，负责连接 WebSocket 房间服务器。
- `server.py`：联机房间服务器，负责创建房间、加入房间和广播动作，部署到 Render 时使用。

界面使用 Canvas 绘制：四个座位围绕方形牌桌、中央牌墙、骰子、庄家、弃牌区、副露区、对手背面手牌和底部可点击图片手牌。

原始牌面图片在 `assets/tiles_fluffy`，来自 FluffyStuff/riichi-mahjong-tiles 的 PNG 导出资源，许可证为 public domain。程序实际运行时加载 `assets/tiles_runtime` 里的小尺寸图片，避免直接读取大图导致卡顿。

## 联机服务器

第一版联机服务器已经放在 `server.py`，部署说明见 `docs/online-server.md`。本地运行服务器需要先安装：

```powershell
pip install -r requirements.txt
python server.py
```

Render 部署会自动使用 `requirements.txt` 和 `render.yaml`。

联机服务器支持真人不足 4 人时自动补 AI 座位，房主可以直接开始游戏。

## 当前规则

- 万、条、筒三门牌，共 108 张。
- 开局掷两颗骰子，从“你”开始按点数选庄家。
- 开局定缺，有缺门牌时必须先打缺门，有缺门不能胡。
- 轮到玩家时手动点击“摸牌”，摸完后再点击底部手牌出牌。
- 血战到底：胡牌玩家退出，剩余玩家继续。
- 支持碰、明杠、暗杠和基础刮风下雨计分。
- 支持平胡、七对、碰碰胡、清一色基础番型。
