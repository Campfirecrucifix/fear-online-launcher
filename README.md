# FEAR Online Community Launcher

Play FEAR Online again with your Steam friends. One player hosts, friends join through Steam (no port forwarding; IPs stay hidden behind Steam's relays).

1. Install **FEAR Online** from Steam (it's still free to download).
2. Download **[FEAR_Online_Launcher.exe](https://github.com/Campfirecrucifix/fear-online-launcher/raw/main/FEAR_Online_Launcher.exe)**.
3. Copy it into the game folder: Steam > right-click FEAR Online > Manage > Browse local files.
4. Open it and click **PATCH**. Then either **HOST** (you get an invite code) or paste a friend's code and **JOIN**. Friends can also right-click you in Steam > **Join Game**. After the first run, Steam's **Play** button also opens this launcher (it replaces the dead Aeria launcher). It updates itself and the game patches automatically.

In game: log in with any name/password, pick a channel. The host clicks **Host Game**; friends double-click the room in **Game Room List**.

Steam must be running and logged in (for the relay). The first HOST/JOIN downloads a ~12 MB package (`FearHost` folder: a small Python runtime running the game server, and FearLink, the Steam tunnel - source in `src/`).

**Windows says "unknown publisher"?** Click *More info > Run anyway* (the launcher isn't code-signed). Source: [`src/Launcher.cs`](src/Launcher.cs).

**Undo:** Steam > FEAR Online > Properties > Installed Files > *Verify integrity of game files*, and delete the launcher.

What the patch does: disables the dead XignCode anti-cheat check in `Game\ZNetwork.dll` (3 bytes, backup kept as `ZNetwork.dll.bak`) and points the game at the local server / Steam tunnel.
