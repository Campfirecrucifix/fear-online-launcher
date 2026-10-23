// FEAR Online Community Launcher (skinned with the original launcher's artwork from LauncherData\Language\common).
// Build: tools/launcher/build.bat (C# compiler built into Windows' .NET 4). Publish: python tools/publish.py "message"
// Copy the exe into the Steam "FEAR Online" folder, run it, click PATCH, then START. Updates itself + patches from GitHub.
using System; using System.IO; using System.Net; using System.Linq; using System.Drawing; using System.Diagnostics; using System.Media;
using System.Windows.Forms; using System.Collections.Generic; using System.Security.Cryptography; using System.Threading;
using System.Web.Script.Serialization;
[assembly: System.Reflection.AssemblyTitle("FEAR Online Launcher")]
class Btn {  // 4-frame sprite strip: normal, hover, pressed, disabled
  public Rectangle R; public Bitmap Img; public string Text; public Font Font; public bool Enabled = true, Hover, Down; public Action Click; public string Sound;
  public void Paint(Graphics g) {
    int f = !Enabled ? 3 : Down ? 2 : Hover ? 1 : 0;
    if (Img != null) { int w = Img.Width / 4; g.DrawImage(Img, R, new Rectangle(f * w, 0, w, Img.Height), GraphicsUnit.Pixel); }
    else using (var b = new SolidBrush(Enabled ? (Hover ? Color.FromArgb(90, 120, 170) : Color.FromArgb(60, 85, 125)) : Color.FromArgb(55, 55, 60))) g.FillRectangle(b, R);
    if (Text != null) TextRenderer.DrawText(g, Text, Font, R, Enabled ? (Hover ? Color.White : Color.FromArgb(200, 215, 235)) : Color.Gray, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
  }
}
class L : Form {
  const string REPO = "Campfirecrucifix/fear-online-launcher"; string RAW = "https://raw.githubusercontent.com/" + REPO + "/main/";
  string game, skin, status = "Checking for updates...", progText = "Loading...", news = "", ver = ""; double p1, p2;
  Dictionary<string, object> m; List<KeyValuePair<string, Action>> todo = new List<KeyValuePair<string, Action>>();
  Bitmap top, bottom, gauge, banner; List<Btn> btns = new List<Btn>(); Btn start, check, join; Point drag; bool soundOn = true;
  TextBox code; List<Process> kids = new List<Process>(); public static string AutoJoin; public static bool AutoHost; string invite;
  Font small = new Font("Segoe UI", 8f), bold = new Font("Segoe UI", 9f, FontStyle.Bold), big = new Font("Segoe UI", 20f, FontStyle.Bold);

  static string Hash(byte[] d) { using (var s = SHA256.Create()) return BitConverter.ToString(s.ComputeHash(d)).Replace("-", "").ToLower(); }
  static string Hash(string p) { return Hash(File.ReadAllBytes(p)); }
  static byte[] Hex(object s) { return ((string)s).Split(' ').Select(x => Convert.ToByte(x, 16)).ToArray(); }
  byte[] Get(string url) {  // download with progress on the top gauge
    var rq = (HttpWebRequest)WebRequest.Create(url); rq.UserAgent = "FEAR-Online-Launcher"; rq.Headers["Cache-Control"] = "no-cache";
    using (var rs = rq.GetResponse()) using (var st = rs.GetResponseStream()) using (var ms = new MemoryStream()) {
      long len = rs.ContentLength; var b = new byte[65536]; int n;
      while ((n = st.Read(b, 0, b.Length)) > 0) { ms.Write(b, 0, n); if (len > 0) { p1 = (double)ms.Length / len; Redraw(); } }
      p1 = 1; Redraw(); return ms.ToArray(); }
  }
  Bitmap Skin(string f) { try { var p = Path.Combine(skin ?? "", f); return File.Exists(p) ? new Bitmap(p) : null; } catch { return null; } }
  void Play(string wav) { if (!soundOn || skin == null) return; try { var p = Path.Combine(skin, wav); if (File.Exists(p)) new SoundPlayer(p).Play(); } catch { } }

  L() {
    Text = "FEAR Online Launcher"; FormBorderStyle = FormBorderStyle.None; ClientSize = new Size(998, 698); StartPosition = FormStartPosition.CenterScreen;
    BackColor = Color.Black; DoubleBuffered = true;
    try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
    game = FindGame();
    if (game != null) { skin = Path.Combine(Path.GetDirectoryName(game), @"LauncherData\Language\common"); if (!Directory.Exists(skin)) skin = null; }
    top = Skin("BG_launcher_top.bmp"); bottom = Skin("BG_launcher_bottom.bmp"); gauge = Skin("gauge_total.bmp");
    Btn close = new Btn { R = new Rectangle(976, 3, 18, 18), Img = Skin("BTN_close.bmp"), Click = Close, Sound = "btnDownClose.wav" };
    Btn min = new Btn { R = new Rectangle(956, 3, 18, 18), Img = Skin("BTN_minimize.bmp"), Click = () => WindowState = FormWindowState.Minimized, Sound = "btnDownMinimize.wav" };
    Btn snd = null; snd = new Btn { R = new Rectangle(936, 3, 18, 18), Img = Skin("BTN_soundON.bmp"), Click = () => { soundOn = !soundOn; snd.Img = Skin(soundOn ? "BTN_soundON.bmp" : "BTN_soundOFF.bmp"); } };
    Btn notice = new Btn { R = new Rectangle(500, 622, 80, 18), Img = Skin("BTN_notice.BMP"), Click = () => Process.Start("https://github.com/" + REPO) };
    Btn support = new Btn { R = new Rectangle(626, 622, 80, 18), Img = Skin("BTN_support.bmp"), Click = () => Process.Start("https://github.com/" + REPO + "/issues") };
    check = new Btn { R = new Rectangle(708, 622, 80, 18), Img = Skin("BTN_check.bmp"), Click = () => { todo.Clear(); m = null; Recheck(); } };
    start = new Btn { R = new Rectangle(802, 569, 184, 74), Img = Skin("BTN_start.bmp"), Text = "START", Font = big, Enabled = false, Click = Go, Sound = "btnDownStart.wav" };
    join = new Btn { R = new Rectangle(708, 648, 80, 22), Text = "JOIN", Font = bold, Enabled = false, Click = () => Join(code.Text) };
    code = new TextBox { Location = new Point(500, 649), Size = new Size(200, 20), BackColor = Color.FromArgb(20, 26, 36), ForeColor = Color.Gainsboro, BorderStyle = BorderStyle.FixedSingle, Font = bold, CharacterCasing = CharacterCasing.Upper };
    code.KeyDown += (s2, e2) => { if (e2.KeyCode == Keys.Enter && join.Enabled) Join(code.Text); };
    Controls.Add(code); if (AutoJoin != null) code.Text = AutoJoin;
    FormClosed += (s2, e2) => StopKids();
    btns.AddRange(new[] { close, min, snd, notice, support, check, start, join });
    if (notice.Img == null) notice.Text = "NOTICE"; if (support.Img == null) support.Text = "SUPPORT"; if (check.Img == null) check.Text = "CHECK FILES";
    foreach (var b in new[] { notice, support, check }) b.Font = small;
    if (close.Img == null) { close.Text = "X"; min.Text = "_"; snd.Text = "♪"; foreach (var b in new[] { close, min, snd }) b.Font = small; }
    Shown += (s, e) => Recheck();
  }
  void Redraw() { if (IsHandleCreated) BeginInvoke((Action)Invalidate); }
  void Set(string s, string startText, bool on) { status = s; if (startText != null) start.Text = startText; start.Enabled = on; check.Enabled = on; if (join != null) join.Enabled = on && start.Text == "HOST"; Redraw(); }
  void Recheck() { start.Enabled = check.Enabled = false; status = "Checking for updates..."; p1 = p2 = 0; Invalidate(); new Thread(Check) { IsBackground = true }.Start(); }

  protected override void OnPaint(PaintEventArgs e) {
    var g = e.Graphics;
    // middle: banner (optional, from GitHub) + news
    using (var br = new System.Drawing.Drawing2D.LinearGradientBrush(new Rectangle(0, 23, 998, 532), Color.FromArgb(18, 22, 30), Color.FromArgb(4, 5, 8), 90f)) g.FillRectangle(br, 0, 23, 998, 532);
    if (banner != null) g.DrawImage(banner, new Rectangle(0, 23, 998, 532));
    using (var shade = new SolidBrush(Color.FromArgb(170, 0, 0, 0))) g.FillRectangle(shade, 30, 60, 470, 460);
    TextRenderer.DrawText(g, "F.E.A.R. ONLINE", new Font("Segoe UI", 30f, FontStyle.Bold), new Point(45, 70), Color.FromArgb(200, 30, 30));
    TextRenderer.DrawText(g, "Community Server   " + ver, bold, new Point(52, 125), Color.FromArgb(150, 190, 235));
    TextRenderer.DrawText(g, news, new Font("Segoe UI", 10f), new Rectangle(52, 160, 430, 350), Color.Gainsboro, TextFormatFlags.WordBreak);
    // top bar + title
    if (top != null) g.DrawImage(top, 0, 0, 998, 23); else g.FillRectangle(Brushes.Black, 0, 0, 998, 23);
    TextRenderer.DrawText(g, "F.E.A.R Online Launcher", bold, new Point(8, 4), Color.FromArgb(150, 190, 235));
    // bottom panel
    if (bottom != null) g.DrawImage(bottom, 0, 555, 998, 143); else g.FillRectangle(new SolidBrush(Color.FromArgb(40, 50, 65)), 12, 569, 780, 76);
    TextRenderer.DrawText(g, "Patch Progress", bold, new Point(25, 572), Color.White);
    for (int i = 0; i < 2; i++) { int w = (int)(686 * Math.Max(0, Math.Min(1, i == 0 ? p1 : p2))); if (w > 0) { var r = new Rectangle(20, 595 + 12 * i, w, 6);
      if (gauge != null) g.DrawImage(gauge, r, new Rectangle(0, 0, Math.Max(1, w * gauge.Width / 686), gauge.Height), GraphicsUnit.Pixel); else g.FillRectangle(Brushes.SkyBlue, r); } }
    TextRenderer.DrawText(g, progText, small, new Point(708, 600), Color.FromArgb(150, 190, 235));
    TextRenderer.DrawText(g, status, small, new Rectangle(20, 618, 470, 60), Color.FromArgb(150, 190, 235), TextFormatFlags.WordBreak);
    TextRenderer.DrawText(g, "Invite code (or Steam > Join Game):", small, new Point(498, 634), Color.FromArgb(150, 190, 235));
    foreach (var b in btns) b.Paint(g);
  }
  Btn At(Point p) { return btns.FirstOrDefault(b => b.R.Contains(p)); }
  protected override void OnMouseMove(MouseEventArgs e) {
    if (e.Button == MouseButtons.Left && drag != Point.Empty) { Location = new Point(Location.X + e.X - drag.X, Location.Y + e.Y - drag.Y); return; }
    var h = At(e.Location); foreach (var b in btns) { bool was = b.Hover; b.Hover = b == h && b.Enabled; if (b.Hover && !was) { Play(b == start ? "btnOverStart.wav" : "btnOver.wav"); Invalidate(); } else if (was && !b.Hover) Invalidate(); }
  }
  protected override void OnMouseDown(MouseEventArgs e) { var b = At(e.Location); if (b != null) { if (b.Enabled) { b.Down = true; Invalidate(); } } else if (e.Y < 23) drag = e.Location; }
  protected override void OnMouseUp(MouseEventArgs e) {
    drag = Point.Empty; var b = At(e.Location);
    foreach (var x in btns) x.Down = false; Invalidate();
    if (b != null && b.Enabled) { Play(b.Sound ?? "btnOverMenu.wav"); b.Click(); }
  }
  protected override void OnMouseLeave(EventArgs e) { foreach (var b in btns) b.Hover = b.Down = false; Invalidate(); }

  string FindGame() {
    var d = Path.GetDirectoryName(Application.ExecutablePath);
    foreach (var c in new[] { d, Path.Combine(d, "FEAR_Online"), @"C:\Program Files (x86)\Steam\steamapps\common\FEAR Online\FEAR_Online" })
      if (File.Exists(Path.Combine(c, "Engine.exe"))) return c;
    return null;
  }
  void Check() {
    try {
      ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072;
      if (game == null) { Set("Engine.exe not found. Copy this launcher into the Steam FEAR Online folder (Steam > FEAR Online > Manage > Browse local files).", null, false); return; }
      // pin downloads to the latest commit: raw.githubusercontent caches "main" for ~5 min
      try { using (var w = new WebClient()) { w.Headers["User-Agent"] = "FEAR-Online-Launcher"; w.Headers["Accept"] = "application/vnd.github.sha";
        var sha = w.DownloadString("https://api.github.com/repos/" + REPO + "/commits/main").Trim(); if (sha.Length == 40) RAW = "https://raw.githubusercontent.com/" + REPO + "/" + sha + "/"; } } catch { }
      var cache = Path.Combine(game, "launcher_cache.json"); string json;
      try { json = System.Text.Encoding.UTF8.GetString(Get(RAW + "manifest.json")); File.WriteAllText(cache, json); }
      catch { if (!File.Exists(cache)) throw; json = File.ReadAllText(cache); status = "GitHub unreachable - using last known settings."; }
      m = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(json);
      ver = "v" + m["version"]; news = m.ContainsKey("news") ? (string)m["news"] : (m.ContainsKey("message") ? (string)m["message"] : "");
      if (m.ContainsKey("banner") && banner == null) try {
        var bc = Path.Combine(game, "launcher_banner.jpg"); var want = (string)m["banner_sha256"];
        if (!File.Exists(bc) || Hash(bc) != want) { var d = Get(RAW + (string)m["banner"]); if (Hash(d) == want) File.WriteAllBytes(bc, d); }
        using (var img = Image.FromFile(bc)) banner = new Bitmap(img); } catch { }
      // self-update: running exe can be renamed, not overwritten
      var me = Application.ExecutablePath;
      if (m.ContainsKey("launcher_sha256") && !File.Exists(me + ".dev") && Hash(me) != (string)m["launcher_sha256"]) {
        Set("Updating launcher...", null, false); progText = "Launcher";
        var d = Get(RAW + "FEAR_Online_Launcher.exe");
        if (Hash(d) == (string)m["launcher_sha256"]) {
          if (File.Exists(me + ".old")) File.Delete(me + ".old");
          File.Move(me, me + ".old"); File.WriteAllBytes(me, d); Process.Start(me); BeginInvoke((Action)Close); return; }
      }
      try { if (File.Exists(me + ".old")) File.Delete(me + ".old"); } catch { }
      // Steam's Play button runs "<FEAR Online>\Launcher.exe -steam" (the dead Aeria launcher): replace it with this launcher
      try { var steamExe = Path.Combine(Path.GetDirectoryName(game), "Launcher.exe");
        if (File.Exists(Path.Combine(Path.GetDirectoryName(game), "aeria_launcher.exe")) && !string.Equals(steamExe, me, StringComparison.OrdinalIgnoreCase) && (!File.Exists(steamExe) || Hash(steamExe) != Hash(me))) {
          if (File.Exists(steamExe) && !File.Exists(steamExe + ".aeria")) File.Move(steamExe, steamExe + ".aeria");
          File.Copy(me, steamExe, true); } } catch { }
      todo.Clear();
      foreach (Dictionary<string, object> f in (System.Collections.IEnumerable)m["files"]) {
        var p = Path.Combine(game, (string)f["path"]);
        if (!File.Exists(p) || Hash(p) != (string)f["sha256"]) { var ff = f; todo.Add(new KeyValuePair<string, Action>((string)f["path"], () => GetFile(ff))); }
      }
      foreach (Dictionary<string, object> p in (System.Collections.IEnumerable)m["patches"]) {
        var path = Path.Combine(game, (string)p["file"]); var b = File.ReadAllBytes(path); int o = Convert.ToInt32((string)p["offset"], 16);
        byte[] n = Hex(p["new"]), old = Hex(p["old"]);
        if (b.Skip(o).Take(n.Length).SequenceEqual(n)) continue;
        if (!b.Skip(o).Take(old.Length).SequenceEqual(old)) { Set(p["file"] + " is an unexpected version. Verify game files in Steam, then press CHECK FILES.", null, false); check.Enabled = true; Redraw(); return; }
        todo.Add(new KeyValuePair<string, Action>((string)p["file"], () => { File.Copy(path, path + ".bak", true); n.CopyTo(b, o); File.WriteAllBytes(path, b); }));
      }
      p1 = p2 = 1; progText = "Ready";
      if (todo.Count > 0) { p1 = p2 = 0; progText = todo.Count + " update" + (todo.Count > 1 ? "s" : ""); Set("Update available. Press PATCH.", "PATCH", true); }
      else { Set("Up to date. HOST a game for your Steam friends, or enter an invite code and JOIN.", "HOST", true); if (AutoJoin != null) BeginInvoke((Action)(() => Join(AutoJoin))); else if (AutoHost) { AutoHost = false; BeginInvoke((Action)Go); } }
    } catch (Exception e) { m = null; Set("Error: " + e.Message + "  (press CHECK FILES to retry)", null, false); check.Enabled = true; Redraw(); }
  }
  void GetFile(Dictionary<string, object> f) {
    var p = Path.Combine(game, (string)f["path"]); var d = Get(RAW + "files/" + ((string)f["path"]).Replace('\\', '/'));
    if (Hash(d) != (string)f["sha256"]) throw new Exception("download of " + f["path"] + " was corrupt");
    Directory.CreateDirectory(Path.GetDirectoryName(p));
    if (File.Exists(p) && !File.Exists(p + ".bak")) File.Copy(p, p + ".bak");
    File.WriteAllBytes(p, d);
  }
  string Server() { try { var f = Path.Combine(game, "server.txt"); if (File.Exists(f)) { var t = File.ReadAllText(f).Trim(); if (t != "") return t; } } catch { } return "127.0.0.1"; }
  static bool Reachable(string ip, int port) {
    try { using (var c = new System.Net.Sockets.TcpClient()) { var r = c.BeginConnect(ip, port, null, null); return r.AsyncWaitHandle.WaitOne(1500) && c.Connected; } } catch { return false; }
  }
  void Go() {
    if (m == null) { Recheck(); return; }
    if (todo.Count > 0) {
      Set("Patching...", null, false);
      new Thread(() => { try { for (int i = 0; i < todo.Count; i++) { progText = todo[i].Key; p1 = 0; Redraw(); todo[i].Value(); p1 = 1; p2 = (i + 1.0) / todo.Count; Redraw(); }
                                todo.Clear(); progText = "Complete"; Set("Patch complete! HOST a game, or enter an invite code and JOIN.", "HOST", true); if (AutoJoin != null) BeginInvoke((Action)(() => Join(AutoJoin))); else if (AutoHost) { AutoHost = false; BeginInvoke((Action)Go); } }
                         catch (Exception e) { todo.Clear(); m = null; Set("Patch failed: " + e.Message + " (try running as administrator, then CHECK FILES)", null, false); check.Enabled = true; Redraw(); } }) { IsBackground = true }.Start();
      return;
    }
    Host();
  }
  // ---- hosting / joining through Steam (FearHost package: embedded Python server + FearLink Steam tunnel) ----
  string HostDir { get { return Path.Combine(game, "FearHost"); } }
  void EnsurePackage() {
    var want = m.ContainsKey("host_sha256") ? (string)m["host_sha256"] : null; var stamp = Path.Combine(HostDir, "package.sha256");
    if (want == null || (File.Exists(stamp) && File.ReadAllText(stamp).Trim() == want)) return;
    progText = "FearHost"; status = "Downloading host/join package (first time only)..."; Redraw();
    var d = Get(RAW + (string)m["host_zip"]); if (Hash(d) != want) throw new Exception("host package download was corrupt");
    StopKids(); KillStale(); System.Threading.Thread.Sleep(500);
    var zip = Path.Combine(game, "FearHost.zip"); var tmp = HostDir + ".new"; File.WriteAllBytes(zip, d);
    if (Directory.Exists(tmp)) Directory.Delete(tmp, true);
    System.IO.Compression.ZipFile.ExtractToDirectory(zip, tmp); File.Delete(zip);
    // swap in the new package only when the old one is fully removed (files can be briefly locked by a closing server)
    for (int i = 0; Directory.Exists(HostDir); i++) {
      try { Directory.Delete(HostDir, true); } catch { if (i > 20) throw new Exception("could not update FearHost - close any running FEAR Online servers and try again"); KillStale(); System.Threading.Thread.Sleep(500); } }
    Directory.Move(tmp, HostDir); File.WriteAllText(stamp, want);
  }
  static void KillStale() {
    foreach (var p in Process.GetProcessesByName("FearLink")) try { p.Kill(); } catch { }
    foreach (var p in Process.GetProcessesByName("python")) try { if (p.MainModule.FileName.IndexOf("FearHost", StringComparison.OrdinalIgnoreCase) >= 0) p.Kill(); } catch { }
  }
  Process Kid(string exe, string args, string log) {
    var si = new ProcessStartInfo(exe, args) { WorkingDirectory = HostDir, UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
    si.EnvironmentVariables["PUBLIC_IP"] = "127.0.0.1"; si.EnvironmentVariables["BIND"] = "127.0.0.1"; var p = Process.Start(si); kids.Add(p);
    var w = new StreamWriter(Path.Combine(HostDir, log)) { AutoFlush = true };
    p.OutputDataReceived += (s, e) => { if (e.Data != null) lock (w) w.WriteLine(e.Data); };
    p.ErrorDataReceived += (s, e) => { if (e.Data != null) lock (w) w.WriteLine(e.Data); };
    p.BeginOutputReadLine(); p.BeginErrorReadLine(); return p;
  }
  void StopKids() { foreach (var p in kids) try { if (!p.HasExited) p.Kill(); } catch { } kids.Clear(); }
  void Engine(Action exited) {
    var g = Process.Start(new ProcessStartInfo(Path.Combine(game, "Engine.exe"), "+PB none +LoginServerIP 127.0.0.1 +LoginServerPort 30003 +SkipSplashScreens 1 +DisableMovies 1") { WorkingDirectory = game });
    new Thread(() => { g.WaitForExit(); try { BeginInvoke(exited); } catch { } }) { IsBackground = true }.Start();
  }
  static bool WaitPort(int port, int ms) { var t = DateTime.Now; while ((DateTime.Now - t).TotalMilliseconds < ms) { if (Reachable("127.0.0.1", port)) return true; Thread.Sleep(300); } return false; }
  void Busy(string s) { start.Enabled = check.Enabled = join.Enabled = false; status = s; Redraw(); }
  void Host() {
    Busy("Starting your game server...");
    new Thread(() => { try {
      EnsurePackage(); StopKids(); KillStale();
      var py = Path.Combine(HostDir, @"python\python.exe");
      foreach (var port in new[] { 30003, 30004, 30005, 30015, 30025, 30035 }) Kid(py, "-u proud.py " + port, "server_" + port + ".log");
      var inv = Path.Combine(HostDir, "invite.txt"); if (File.Exists(inv)) File.Delete(inv);
      var link = Kid(Path.Combine(HostDir, "FearLink.exe"), "host", "fearlink.log");
      for (int i = 0; i < 50 && !File.Exists(inv) && !link.HasExited; i++) Thread.Sleep(200);
      if (!File.Exists(inv)) throw new Exception("Steam tunnel failed to start (is Steam running and logged in?). See FearHost\\fearlink.log");
      invite = File.ReadAllText(inv).Trim();
      if (!WaitPort(30003, 15000)) throw new Exception("game server failed to start. See FearHost\\server_30003.log");
      BeginInvoke((Action)(() => {
        try { Clipboard.SetText(invite); } catch { }
        Set("HOSTING. Invite code: " + invite + " (copied). Steam friends can also right-click you > Join Game. Keep this launcher open while you play; closing it stops the server.", "STOP", true);
        join.Enabled = false; start.Click = StopHosting; Engine(() => { }); WindowState = FormWindowState.Minimized; }));
    } catch (Exception e) { BeginInvoke((Action)(() => { StopKids(); Set("Host failed: " + e.Message, "HOST", true); })); } }) { IsBackground = true }.Start();
  }
  void StopHosting() { StopKids(); start.Click = Go; Set("Server stopped. HOST again, or enter an invite code and JOIN.", "HOST", true); }
  void Join(string c) {
    c = (c ?? "").Trim(); if (c == "") { Set("Enter the host's invite code (looks like FEAR-XXXXXX), then press JOIN.", null, true); return; }
    Busy("Connecting to host through Steam...");
    new Thread(() => { try {
      EnsurePackage(); StopKids(); KillStale();
      var link = Kid(Path.Combine(HostDir, "FearLink.exe"), "join " + c, "fearlink.log");
      if (!WaitPort(30003, 20000) || link.HasExited) throw new Exception("could not reach the host. Check the code, that the host is still hosting, and that Steam is running. See FearHost\\fearlink.log");
      BeginInvoke((Action)(() => {
        Set("Connected to " + c + ". Starting the game...", "HOST", false);
        Engine(() => { StopKids(); Close(); }); WindowState = FormWindowState.Minimized; }));
    } catch (Exception e) { BeginInvoke((Action)(() => { StopKids(); Set("Join failed: " + e.Message, "HOST", true); })); } }) { IsBackground = true }.Start();
  }
  [STAThread] static void Main(string[] args) {
    int i = Array.FindIndex(args, a => a.Equals("+fearjoin", StringComparison.OrdinalIgnoreCase)); if (i >= 0 && i + 1 < args.Length) AutoJoin = args[i + 1];  // Steam "Join Game"
    AutoHost = args.Any(a => a.Equals("+fearhost", StringComparison.OrdinalIgnoreCase));  // shortcut / automation: host immediately
    Application.EnableVisualStyles(); Application.Run(new L()); }
}
