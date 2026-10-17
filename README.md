# FEAR Online Community Launcher

Play FEAR Online again on a community server.

1. Install **FEAR Online** from Steam (it's still free to download).
2. Download **[FEAR_Online_Launcher.exe](https://github.com/Campfirecrucifix/fear-online-launcher/raw/main/FEAR_Online_Launcher.exe)**.
3. Copy it into the game folder: Steam > right-click FEAR Online > Manage > Browse local files.
4. Open it, click **PATCH**, then **PLAY**. After the first run, Steam's **Play** button also opens this launcher (it replaces the dead Aeria launcher). It updates itself and the game patches automatically.

In game: log in with any name/password, pick a channel, then **Game Room List** to join a match or **Host Game** to create one.

**Windows says "unknown publisher"?** Click *More info > Run anyway* (the launcher isn't code-signed). Source: [`src/Launcher.cs`](src/Launcher.cs).

**Undo:** Steam > FEAR Online > Properties > Installed Files > *Verify integrity of game files*, and delete the launcher.

What the patch does: disables the dead XignCode anti-cheat check in `Game\ZNetwork.dll` (3 bytes, backup kept as `ZNetwork.dll.bak`) and points the game at the community server.
