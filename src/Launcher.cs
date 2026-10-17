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
  Bitmap top, bottom, gauge, banner; List<Btn> btns = new List<Btn>(); Btn start, check; Point drag; bool soundOn = true;
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
    btns.AddRange(new[] { close, min, snd, notice, support, check, start });
    if (notice.Img == null) notice.Text = "NOTICE"; if (support.Img == null) support.Text = "SUPPORT"; if (check.Img == null) check.Text = "CHECK FILES";
    foreach (var b in new[] { notice, support, check }) b.Font = small;
    if (close.Img == null) { close.Text = "X"; min.Text = "_"; snd.Text = "♪"; foreach (var b in new[] { close, min, snd }) b.Font = small; }
    Shown += (s, e) => Recheck();
  }
  void Redraw() { if (IsHandleCreated) BeginInvoke((Action)Invalidate); }
  void Set(string s, string startText, bool on) { status = s; if (startText != null) start.Text = startText; start.Enabled = on; check.Enabled = on; Redraw(); }
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
    TextRenderer.DrawText(g, status, small, new Rectangle(20, 618, 470, 30), Color.FromArgb(150, 190, 235), TextFormatFlags.WordBreak);
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
      else Set("Up to date. Server: " + Server() + "   Press START to play.", "START", true);
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
                                todo.Clear(); progText = "Complete"; Set("Patch complete! Server: " + Server() + "   Press START to play.", "START", true); }
                         catch (Exception e) { todo.Clear(); m = null; Set("Patch failed: " + e.Message + " (try running as administrator, then CHECK FILES)", null, false); check.Enabled = true; Redraw(); } }) { IsBackground = true }.Start();
      return;
    }
    // pick a reachable address: public IP, else the host's LAN IP (same home network; most routers can't loop back), else this PC
    var ips = new List<string> { Server() };
    string ip = ips.FirstOrDefault(a => Reachable(a, Convert.ToInt32(m["port"])));
    if (ip == null) { Set("Server " + Server() + " is offline. Put the host's address in server.txt next to Engine.exe.", null, true); return; }
    Process.Start(new ProcessStartInfo(Path.Combine(game, "Engine.exe"), "+PB none +LoginServerIP " + ip + " +LoginServerPort " + m["port"] + " +SkipSplashScreens 1 +DisableMovies 1") { WorkingDirectory = game });
    Close();
  }
  [STAThread] static void Main() { Application.EnableVisualStyles(); Application.Run(new L()); }
}
