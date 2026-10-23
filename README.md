# FEAR Online Community Launcher

Play FEAR Online again with your Steam friends. One player hosts, friends join through Steam (no port forwarding; IPs stay hidden behind Steam's relays).

1. Install **FEAR Online** from Steam (it's still free to download).
2. Download **[FEAR_Online_Launcher.exe](https://github.com/Campfirecrucifix/fear-online-launcher/raw/main/FEAR_Online_Launcher.exe)**.
3. Copy it into the game folder: Steam > right-click FEAR Online > Manage > Browse local files.
4. Open it and click **PATCH**. Then either **HOST** (you get an invite code) or paste a friend's code and **JOIN**. Friends can also right-click you in Steam > **Join Game**. After the first run, Steam's **Play** button also opens this launcher (it replaces the dead Aeria launcher). It updates itself and the game patches automatically.

## How to play together (follow in order)

**Host:**
1. Open the launcher, click **HOST**. An invite code is copied to your clipboard - send it to your friends.
2. The game starts. Log in with any name/password and pick a channel.
3. Click **HOST GAME**, choose map/mode and create the room. **Stay in the room - don't press START yet.**

**Friends (only after the host's room exists):**
1. Paste the invite code into the launcher and click **JOIN** (or right-click the host in Steam > **Join Game**).
2. Log in with any name/password and pick the **same channel**.
3. Click **GAME ROOM LIST** and double-click the host's room.

**Start:** wait until **everyone is shown in the room**, everyone clicks **READY**, then the host clicks **START**. Players who aren't in the room when the host starts are left out - there is no joining a match already in progress yet.

If a friend can't see the room: they click **GAME ROOM LIST** again to refresh. If anything goes wrong, everyone closes the game and starts over from the host step.

**Known issues:** the kill feed doesn't show the killer's name and the Tab scoreboard is empty (being worked on). Demolition and Soul King modes don't work in 2-player matches yet.

Steam must be running and logged in (for the relay). The first HOST/JOIN downloads a ~12 MB package (`FearHost` folder: a small Python runtime running the game server, and FearLink, the Steam tunnel - source in `src/`).

**Windows says "unknown publisher"?** Click *More info > Run anyway* (the launcher isn't code-signed). Source: [`src/Launcher.cs`](src/Launcher.cs).

**Undo:** Steam > FEAR Online > Properties > Installed Files > *Verify integrity of game files*, and delete the launcher.

What the patch does: disables the dead XignCode anti-cheat check in `Game\ZNetwork.dll` (3 bytes, backup kept as `ZNetwork.dll.bak`) and points the game at the local server / Steam tunnel.
