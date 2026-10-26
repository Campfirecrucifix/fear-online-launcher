# FEAR Online Community Launcher

Play **FEAR Online** again with your Steam friends. One player hosts, everyone else joins with an invite code. The connection runs through Steam's relay network, so there's no port forwarding and nobody sees anyone's IP address.

**Latest version:** see [Releases](https://github.com/Campfirecrucifix/fear-online-launcher/releases). The launcher updates itself and the game patches automatically, so you only download it once.

---

## 1. Install (everyone, once)

1. Install **FEAR Online** from Steam. It's still free to download.
2. Download **`FEAR_Online_Launcher.exe`** from the [latest release](https://github.com/Campfirecrucifix/fear-online-launcher/releases/latest).
3. Open the game folder: Steam > right-click **FEAR Online** > **Manage** > **Browse local files**.
4. Copy `FEAR_Online_Launcher.exe` into that folder (next to `Engine.exe`).
5. Run it. If Windows says "unknown publisher", click **More info** > **Run anyway** (the launcher isn't code-signed; its source is in [`src/`](src)).
6. Click **PATCH** and wait until it says **Patch complete**.

After the first run, Steam's **Play** button opens this launcher too (it replaces the old, dead Aeria launcher).

**Requirements:** Windows, Steam running and logged in (the Steam relay is what connects you), and everyone on the same launcher version (it updates itself when you open it).

---

## 2. Hosting a game

1. Open the launcher and click **HOST**.
   - The first time, it downloads a small (~12 MB) host package: a game server and FearLink, the Steam tunnel.
   - An **invite code** like `FEAR-AB12CD` is shown and **copied to your clipboard**. Send it to your friends (Steam chat, Discord, ...).
2. The game starts. Log in with **any name and password** (there are no accounts; the name is your in-game name).
3. Pick a **channel**. Remember which one, because your friends must pick the same one.
4. Click **HOST GAME**, pick a mode and map, and create the room.
5. **Stay in the room and don't press START yet.** Wait for your friends to appear in the room (see below).
6. When everyone is shown in the room and has clicked **READY**, click **START**.

Keep the launcher open while you play: closing it stops the server. To stop hosting, close the game and press **STOP** in the launcher.

## 3. Joining a friend's game

1. Wait until the host has created their room.
2. Open the launcher, paste the host's invite code into the box and click **JOIN**.
   - Or, in your Steam friends list, right-click the host > **Join Game**.
3. The game starts. Log in with any name and password.
4. Pick the **same channel** as the host.
5. Click **GAME ROOM LIST** and double-click the host's room. If it isn't there, click **GAME ROOM LIST** again to refresh.
6. Click **READY** and wait for the host to start.

Players who aren't in the room when the host presses START sit that match out and join the next one.

## 4. Between matches

When a match ends everyone goes back to the room. The host can change the map/mode and press **START** again; there's no need to restart the game.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| **Join failed: could not reach the host** | Check the code, make sure the host's launcher still shows it's hosting, and that both of you have Steam running and logged in. |
| **Host failed: Steam tunnel failed to start** | Start Steam and log in, then press HOST again. Details are in `FearHost\fearlink.log` in the game folder. |
| **The room isn't in the list** | Make sure you're in the same channel as the host and click **GAME ROOM LIST** to refresh. |
| **"... is an unexpected version"** | Steam > FEAR Online > Properties > Installed Files > **Verify integrity of game files**, then open the launcher and press **PATCH** again. |
| **Something else goes wrong** | Everyone closes the game, the host presses HOST again and sends the (new) code, and everyone joins again. |
| **Found a bug** | Press **SUPPORT** in the launcher, or open an [issue](https://github.com/Campfirecrucifix/fear-online-launcher/issues). |

## Known issues

- **Demolition** can hang on the loading screen with 2 players, and **Soul King** won't start. Use the other modes.
- Joining a match that's already running isn't supported when a player hosts: be in the room before the host presses START.
- The channel tab may show `[ERROR: Invalid String ID]` (cosmetic).

---

## What the launcher changes

- **Patches** (byte edits, checked against the original bytes first): disables the dead XignCode anti-cheat check in `Game\ZNetwork.dll`, and fixes in `GameClient.dll` / `GameServer.dll` / `Engine.exe` for teams, damage, the scoreboard, kill feed, match timer, aiming and more. The full list is in [`manifest.json`](manifest.json) (`patches`).
- **Files**: updated game data, interface and maps, downloaded from this repository and checked by SHA-256.
- **FearHost**: the community game server (`src/proud.py`) and the Steam tunnel (`src/FearLink.cs`), used when you HOST or JOIN.
- It points the game at the local server / Steam tunnel instead of the dead official servers.

**Undo everything:** Steam > FEAR Online > Properties > Installed Files > **Verify integrity of game files**, then delete `FEAR_Online_Launcher.exe` and the `FearHost` folder.

## Source

- [`src/Launcher.cs`](src/Launcher.cs): the launcher (C#, .NET Framework 4).
- [`src/proud.py`](src/proud.py): the game server (login, channels, rooms, matches).
- [`src/FearLink.cs`](src/FearLink.cs): the Steam relay tunnel.

This is a fan project. FEAR Online and F.E.A.R. belong to their respective owners; you need your own copy of the game from Steam.
