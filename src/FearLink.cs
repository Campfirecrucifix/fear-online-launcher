// FearLink: tunnels FEAR Online's TCP/UDP game traffic between a host and joiners through Steam's relay network
// (ISteamNetworkingMessages over Valve SDR, ICE disabled => players never see each other's IP addresses).
//   FearLink.exe host                -> forwards tunneled traffic to this PC's lobby server/game; advertises "Join Game" to Steam friends
//   FearLink.exe join <code|steamid> -> game connects to 127.0.0.1; traffic goes to the host through Steam
//   --udp <port> [peerport]          -> test transport over local UDP instead of Steam (single-PC testing)
//   --bind <ip>                      -> joiner listen address (default 127.0.0.1)
// Build (x64, needs steam_api64.dll v1.57+ next to it): see build.bat
using System; using System.Collections.Generic; using System.Linq; using System.Net; using System.Net.Sockets;
using System.Runtime.InteropServices; using System.Text; using System.Threading; using System.IO;
static class S {  // Steamworks flat API
  const string D = "steam_api64.dll";
  [DllImport(D)] public static extern int SteamAPI_InitFlat(byte[] err);
  [DllImport(D)] public static extern void SteamAPI_Shutdown();
  [DllImport(D)] public static extern void SteamAPI_RunCallbacks();
  [DllImport(D)] public static extern void SteamAPI_RegisterCallback(IntPtr obj, int id);
  [DllImport(D)] public static extern bool SteamAPI_ISteamNetworkingUtils_SetConfigValue(IntPtr i, int cfg, int scope, IntPtr obj, int type, ref IntPtr val);
  [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate void NetCb(IntPtr p);
  [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate void DbgCb(int t, IntPtr msg);
  [DllImport(D)] public static extern void SteamAPI_ISteamNetworkingUtils_SetDebugOutputFunction(IntPtr i, int level, DbgCb f);
  [DllImport(D)] public static extern void SteamAPI_ManualDispatch_Init();
  [DllImport(D)] public static extern int SteamAPI_GetHSteamPipe();
  [DllImport(D)] public static extern void SteamAPI_ManualDispatch_RunFrame(int pipe);
  [DllImport(D)] public static extern bool SteamAPI_ManualDispatch_GetNextCallback(int pipe, out CB cb);
  [DllImport(D)] public static extern void SteamAPI_ManualDispatch_FreeLastCallback(int pipe);
  [DllImport(D)] public static extern IntPtr SteamAPI_SteamNetworkingMessages_SteamAPI_v002();
  [DllImport(D)] public static extern IntPtr SteamAPI_SteamNetworkingUtils_SteamAPI_v004();
  [DllImport(D)] public static extern IntPtr SteamAPI_SteamUser_v023();
  [DllImport(D)] public static extern IntPtr SteamAPI_SteamFriends_v018();
  [DllImport(D)] public static extern int SteamAPI_ISteamNetworkingMessages_SendMessageToUser(IntPtr i, ref Id id, byte[] d, uint n, int flags, int ch);
  [DllImport(D)] public static extern int SteamAPI_ISteamNetworkingMessages_ReceiveMessagesOnChannel(IntPtr i, int ch, IntPtr[] msgs, int max);
  [DllImport(D)] public static extern bool SteamAPI_ISteamNetworkingMessages_AcceptSessionWithUser(IntPtr i, ref Id id);
  [DllImport(D)] public static extern void SteamAPI_SteamNetworkingMessage_t_Release(IntPtr m);
  [DllImport(D)] public static extern bool SteamAPI_ISteamNetworkingMessages_CloseSessionWithUser(IntPtr i, ref Id id);
  [DllImport(D)] public static extern int SteamAPI_ISteamNetworkingMessages_GetSessionConnectionInfo(IntPtr i, ref Id id, byte[] info, byte[] quick);
  [DllImport(D)] public static extern int SteamAPI_ISteamNetworkingUtils_GetRelayNetworkStatus(IntPtr i, byte[] st);
  [DllImport(D)] public static extern void SteamAPI_ISteamNetworkingUtils_InitRelayNetworkAccess(IntPtr i);
  [DllImport(D)] public static extern bool SteamAPI_ISteamNetworkingUtils_SetGlobalConfigValueInt32(IntPtr i, int cfg, int v);
  [DllImport(D)] public static extern ulong SteamAPI_ISteamUser_GetSteamID(IntPtr i);
  [DllImport(D)] public static extern bool SteamAPI_ISteamFriends_SetRichPresence(IntPtr i, byte[] k, byte[] v);
  [DllImport(D)] public static extern IntPtr SteamAPI_ISteamFriends_GetFriendPersonaName(IntPtr i, ulong id);
  [StructLayout(LayoutKind.Sequential)] public struct CB { public int user, id; public IntPtr param; public int size; }
  [StructLayout(LayoutKind.Sequential, Size = 136)] public struct Id { public int type, size; public ulong steamid; }
  public static Id Of(ulong sid) { return new Id { type = 16, size = 8, steamid = sid }; }
  public static byte[] Z(string s) { return Encoding.UTF8.GetBytes(s + "\0"); }
}
abstract class Transport {  // send(peer, reliable, frame); Poll() returns (peer, reliable, frame)
  public abstract void Send(ulong peer, bool rel, byte[] f); public abstract IEnumerable<Tuple<ulong, bool, byte[]>> Poll(); public virtual void Tick() { }
  public Func<ulong, bool> Accept = p => true; public Action<ulong> JoinRequest = null; public ulong Me;
}
class SteamCb {  // fake CCallbackBase for SteamAPI_RegisterCallback (MSVC x64 vtable: RunCallResult, Run, GetSize)
  [UnmanagedFunctionPointer(CallingConvention.ThisCall)] delegate void RunD(IntPtr self, IntPtr p);
  [UnmanagedFunctionPointer(CallingConvention.ThisCall)] delegate void RunResD(IntPtr self, IntPtr p, bool io, ulong h);
  [UnmanagedFunctionPointer(CallingConvention.ThisCall)] delegate int SizeD(IntPtr self);
  static List<object> keep = new List<object>();
  public static void Register(int id, int size, Action<IntPtr> f) {
    RunD run = (self, p) => { try { f(p); } catch (Exception e) { Log.W("callback error: " + e.Message); } };
    RunResD res = (self, p, io, h) => run(self, p); SizeD sz = self => size; keep.Add(run); keep.Add(res); keep.Add(sz);
    var vt = Marshal.AllocHGlobal(24); Marshal.WriteIntPtr(vt, 0, Marshal.GetFunctionPointerForDelegate(res)); Marshal.WriteIntPtr(vt, 8, Marshal.GetFunctionPointerForDelegate(run)); Marshal.WriteIntPtr(vt, 16, Marshal.GetFunctionPointerForDelegate(sz));
    var o = Marshal.AllocHGlobal(32); for (int i = 0; i < 32; i++) Marshal.WriteByte(o, i, 0); Marshal.WriteIntPtr(o, 0, vt); Marshal.WriteInt32(o, 12, id);
    S.SteamAPI_RegisterCallback(o, id);
  }
}
class SteamT : Transport {
  IntPtr nm, fr, ut; int pipe; DateTime nextDiag = DateTime.Now; public HashSet<ulong> Peers = new HashSet<ulong>(); object lk = new object();
  public SteamT() {
    var err = new byte[1024]; // NOTE: no ManualDispatch - it stalls the relay config fetch (relay net stuck at 'Waiting')
    if (SteamAPI_Init(err) != 0) throw new Exception("Steam not running / not logged in: " + Encoding.UTF8.GetString(err).TrimEnd('\0'));
    pipe = S.SteamAPI_GetHSteamPipe();
    ut = S.SteamAPI_SteamNetworkingUtils_SteamAPI_v004();
    S.SteamAPI_ISteamNetworkingUtils_SetGlobalConfigValueInt32(ut, 104, 0);  // P2P_Transport_ICE_Enable = disable: relay only, IPs never exposed
    S.SteamAPI_ISteamNetworkingUtils_InitRelayNetworkAccess(ut);
    onReq = p => { var id = (S.Id)Marshal.PtrToStructure(p, typeof(S.Id)); lock (Peers) Peers.Add(id.steamid); bool ok = Accept(id.steamid);
      if (ok) S.SteamAPI_ISteamNetworkingMessages_AcceptSessionWithUser(nm, ref id); Log.W("session request from " + Name(id.steamid) + (ok ? " (accepted)" : " (ignored)")); };
    onFail = p => Log.W("connection to peer failed: " + Encoding.ASCII.GetString(Bytes(p + 184, 128)).Split((char)0)[0]);
    SteamCb.Register(1251, 136, p => onReq(p));   // SteamNetworkingMessagesSessionRequest_t
    SteamCb.Register(1252, 696, p => onFail(p));  // SteamNetworkingMessagesSessionFailed_t
    SteamCb.Register(337, 264, p => { var con = Marshal.PtrToStringAnsi(p + 8); var m = System.Text.RegularExpressions.Regex.Match(con ?? "", @"\d{17}"); if (m.Success && JoinRequest != null) JoinRequest(ulong.Parse(m.Value)); });  // GameRichPresenceJoinRequested_t
    if (Environment.GetEnvironmentVariable("FL_DEBUG") == "1") { onDbg = (t, m) => Log.W("steam: " + Marshal.PtrToStringAnsi(m)); S.SteamAPI_ISteamNetworkingUtils_SetDebugOutputFunction(ut, 5, onDbg); }
    else { onDbg = (t, m) => Log.W("steam: " + Marshal.PtrToStringAnsi(m)); S.SteamAPI_ISteamNetworkingUtils_SetDebugOutputFunction(ut, 3, onDbg); }  // errors+important
    nm = S.SteamAPI_SteamNetworkingMessages_SteamAPI_v002(); fr = S.SteamAPI_SteamFriends_v018();
    Me = S.SteamAPI_ISteamUser_GetSteamID(S.SteamAPI_SteamUser_v023());
  }
  static S.NetCb onReq, onFail; static S.DbgCb onDbg;  // kept alive for native callbacks
  static byte[] Bytes(IntPtr p, int n) { var b = new byte[n]; Marshal.Copy(p, b, 0, n); return b; }
  static int SteamAPI_Init(byte[] e) { return S.SteamAPI_InitFlat(e); }
  public void Presence(string k, string v) { S.SteamAPI_ISteamFriends_SetRichPresence(fr, S.Z(k), v == null ? null : S.Z(v)); }
  public string Name(ulong id) { return Marshal.PtrToStringAnsi(S.SteamAPI_ISteamFriends_GetFriendPersonaName(fr, id)); }
  System.Collections.Concurrent.ConcurrentQueue<Tuple<ulong, bool, byte[]>> q = new System.Collections.Concurrent.ConcurrentQueue<Tuple<ulong, bool, byte[]>>();
  public override void Send(ulong peer, bool rel, byte[] f) { q.Enqueue(Tuple.Create(peer, rel, f)); }  // Steam calls only from the main thread
  void Flush() { Tuple<ulong, bool, byte[]> m; while (q.TryDequeue(out m)) SendNow(m.Item1, m.Item2, m.Item3); }
  void SendNow(ulong peer, bool rel, byte[] f) {
    var id = S.Of(peer); int r = S.SteamAPI_ISteamNetworkingMessages_SendMessageToUser(nm, ref id, f, (uint)f.Length, rel ? 8 | 1 : 1, rel ? 0 : 1);  // reliable|nonagle / unreliable|nonagle
    if (r != 1) { Log.W("send to " + peer + " failed, EResult " + r + " - resetting session and retrying"); S.SteamAPI_ISteamNetworkingMessages_CloseSessionWithUser(nm, ref id);
      r = S.SteamAPI_ISteamNetworkingMessages_SendMessageToUser(nm, ref id, f, (uint)f.Length, rel ? 8 | 1 : 1, rel ? 0 : 1); if (r != 1) Log.W("retry failed, EResult " + r); }
    lock (Peers) Peers.Add(peer);
  }
  public override void Tick() {
    Flush();
    if (DateTime.Now > nextDiag) { nextDiag = DateTime.Now.AddSeconds(5);  // diagnostics: relay network + each peer session state
      var rs = new byte[512]; int avail = S.SteamAPI_ISteamNetworkingUtils_GetRelayNetworkStatus(ut, rs);
      var line = "relay net " + avail + " (" + Encoding.ASCII.GetString(rs, 16, 256).Split('\0')[0] + ")";
      ulong[] ps; lock (Peers) ps = Peers.ToArray();
      foreach (var p in ps) { var id = S.Of(p); var info = new byte[1024]; var q = new byte[256]; int st = S.SteamAPI_ISteamNetworkingMessages_GetSessionConnectionInfo(nm, ref id, info, q);
        line += " | peer " + Name(p) + " state " + st + " end " + BitConverter.ToInt32(info, 180) + " " + Encoding.ASCII.GetString(info, 184, 128).Split('\0')[0] + " ping " + BitConverter.ToInt32(q, 4); }
      var key = System.Text.RegularExpressions.Regex.Replace(line, @" ping -?\d+|Relays:.*?ignored", "");
      if (key != lastDiag) { Log.W(line); lastDiag = key; } }
    lock (lk) {
      S.SteamAPI_RunCallbacks();  // fires the session request/failed config callbacks above
    }
  }
  string lastDiag;
  public override IEnumerable<Tuple<ulong, bool, byte[]>> Poll() {
    var r = new List<Tuple<ulong, bool, byte[]>>(); var buf = new IntPtr[64];
    lock (lk) for (int ch = 0; ch < 2; ch++) {
      int n = S.SteamAPI_ISteamNetworkingMessages_ReceiveMessagesOnChannel(nm, ch, buf, buf.Length);
      for (int i = 0; i < n; i++) {
        var p = Marshal.ReadIntPtr(buf[i]); int sz = Marshal.ReadInt32(buf[i], 8); ulong peer = (ulong)Marshal.ReadInt64(buf[i], 16 + 8);
        var d = new byte[sz]; Marshal.Copy(p, d, 0, sz); r.Add(Tuple.Create(peer, ch == 0, d)); S.SteamAPI_SteamNetworkingMessage_t_Release(buf[i]);
      }
    }
    return r;
  }
}
class UdpT : Transport {  // test transport (peer id = port on 127.0.0.1): reliable frames over TCP (like Steam's reliable channel), unreliable over UDP
  UdpClient u; Dictionary<ulong, NetworkStream> tcp = new Dictionary<ulong, NetworkStream>(); System.Collections.Concurrent.ConcurrentQueue<Tuple<ulong, bool, byte[]>> inq = new System.Collections.Concurrent.ConcurrentQueue<Tuple<ulong, bool, byte[]>>();
  public UdpT(int port, int hostPort) {
    u = new UdpClient(new IPEndPoint(IPAddress.Loopback, port)); u.Client.ReceiveBufferSize = 1 << 22; Me = (ulong)port;
    if (hostPort == 0) { var l = new TcpListener(IPAddress.Loopback, port); l.Start();
      new Thread(() => { while (true) { var c = l.AcceptTcpClient(); c.NoDelay = true; var ns = c.GetStream(); var id = new byte[4]; Read(ns, id); ulong peer = BitConverter.ToUInt32(id, 0); lock (tcp) tcp[peer] = ns; Reader(ns, peer); } }) { IsBackground = true }.Start(); }
    else { var c = new TcpClient(); c.NoDelay = true; c.Connect(IPAddress.Loopback, hostPort); var ns = c.GetStream(); ns.Write(BitConverter.GetBytes(port), 0, 4); tcp[(ulong)hostPort] = ns; Reader(ns, (ulong)hostPort); }
  }
  static void Read(NetworkStream ns, byte[] b) { int o = 0; while (o < b.Length) { int n = ns.Read(b, o, b.Length - o); if (n <= 0) throw new IOException("closed"); o += n; } }
  void Reader(NetworkStream ns, ulong peer) { new Thread(() => { try { var h = new byte[4]; while (true) { Read(ns, h); var d = new byte[BitConverter.ToInt32(h, 0)]; Read(ns, d); inq.Enqueue(Tuple.Create(peer, true, d)); } } catch { } }) { IsBackground = true }.Start(); }
  public override void Send(ulong peer, bool rel, byte[] f) {
    if (rel) { NetworkStream ns; lock (tcp) tcp.TryGetValue(peer, out ns); if (ns == null) return; var b = new byte[f.Length + 4]; BitConverter.GetBytes(f.Length).CopyTo(b, 0); f.CopyTo(b, 4); lock (ns) ns.Write(b, 0, b.Length); }
    else u.Send(f, f.Length, new IPEndPoint(IPAddress.Loopback, (int)peer));
  }
  public override IEnumerable<Tuple<ulong, bool, byte[]>> Poll() {
    var r = new List<Tuple<ulong, bool, byte[]>>(); Tuple<ulong, bool, byte[]> m; while (inq.TryDequeue(out m)) r.Add(m);
    while (u.Available > 0) { var ep = new IPEndPoint(0, 0); try { var b = u.Receive(ref ep); r.Add(Tuple.Create((ulong)ep.Port, false, b)); } catch { } }
    return r;
  }
}
static class Log { public static void W(string s) { Console.WriteLine(DateTime.Now.ToString("HH:mm:ss ") + s); } }
class Link {
  // frames: reliable [1 open|2 data|3 close][u32 conn][u16 port][payload]; unreliable [u32 key][u16 port][payload]
  public static int[] TCP = { 30003, 30004, 30005, 30015, 30025, 30035 }, UDP = { 30003, 30004, 30005, 30015, 30025, 30035, 27999, 28000, 28001, 28002 };
  public static IPAddress Src = IPAddress.Loopback;  // host side: source address for local connections (test hook)
  Transport t; ulong host; bool isHost; IPAddress bind = IPAddress.Loopback; object lk = new object();
  Dictionary<string, Socket> tcp = new Dictionary<string, Socket>(); Dictionary<string, UdpClient> udp = new Dictionary<string, UdpClient>();
  Dictionary<uint, IPEndPoint> keyEp = new Dictionary<uint, IPEndPoint>(); Dictionary<string, uint> epKey = new Dictionary<string, uint>(); uint next = 1;
  static byte[] F(byte a, uint c, int port, byte[] p, int n) { var f = new byte[(a == 0 ? 6 : 7) + n]; int o = 0; if (a != 0) f[o++] = a; BitConverter.GetBytes(c).CopyTo(f, o); BitConverter.GetBytes((ushort)port).CopyTo(f, o + 4); if (n > 0) Array.Copy(p, 0, f, o + 6, n); return f; }
  void Pump(Socket s, ulong peer, uint conn, int port, string key) {  // socket -> tunnel
    new Thread(() => { var b = new byte[65536]; try { int n; while ((n = s.Receive(b)) > 0) t.Send(peer, true, F(2, conn, port, b, n)); } catch { }
      t.Send(peer, true, F(3, conn, port, null, 0)); lock (lk) tcp.Remove(key); try { s.Close(); } catch { } }) { IsBackground = true }.Start();
  }
  public Link(Transport tr, bool h, ulong hostId, IPAddress b) {
    t = tr; isHost = h; host = hostId; if (b != null) bind = b;
    if (!isHost) {
      foreach (var port in TCP) { var l = new TcpListener(bind, port); try { l.Start(); } catch (Exception e) { Log.W("can't listen tcp " + port + ": " + e.Message); continue; }
        int pp = port; new Thread(() => { while (true) { var s = l.AcceptSocket(); s.NoDelay = true; uint c; lock (lk) { c = next++; tcp["0:" + c] = s; }
          Log.W("game connected to tcp " + pp + ", opening through tunnel"); t.Send(host, true, F(1, c, pp, null, 0)); Pump(s, host, c, pp, "0:" + c); } }) { IsBackground = true }.Start(); }
      foreach (var port in UDP) { UdpClient u; try { u = new UdpClient(new IPEndPoint(bind, port)); } catch (Exception e) { Log.W("can't listen udp " + port + ": " + e.Message); continue; }
        Nocr(u); int pp = port; udp["L:" + port] = u;
        new Thread(() => { while (true) { try { var ep = new IPEndPoint(0, 0); var d = u.Receive(ref ep); uint k; var ek = ep + ">" + pp;
          lock (lk) if (!epKey.TryGetValue(ek, out k)) { k = next++; epKey[ek] = k; keyEp[k] = ep; }
          t.Send(host, false, F(0, k, pp, d, d.Length)); } catch { } } }) { IsBackground = true }.Start(); }
      t.Accept = p => p == host;
    }
  }
  static void Nocr(UdpClient u) { try { u.Client.IOControl(-1744830452, new byte[] { 0 }, null); } catch { } }  // SIO_UDP_CONNRESET off
  public void Handle(ulong peer, bool rel, byte[] f) {
    if (rel) {
      byte a = f[0]; uint c = BitConverter.ToUInt32(f, 1); int port = BitConverter.ToUInt16(f, 5); string key = (isHost ? peer : 0) + ":" + c; Socket s;
      if (a == 1 && isHost) {
        if (!TCP.Contains(port)) return;
        s = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp) { NoDelay = true }; s.Bind(new IPEndPoint(Src, 0));
        if (port == 30003) try { Directory.CreateDirectory("state"); File.WriteAllText(Path.Combine("state", "peer_" + ((IPEndPoint)s.LocalEndPoint).Port), Name(peer) ?? ""); } catch { }  // server uses Steam name as in-game name
        try { s.Connect(IPAddress.Loopback, port); } catch { t.Send(peer, true, F(3, c, port, null, 0)); return; }
        lock (lk) tcp[key] = s; Pump(s, peer, c, port, key); Log.W("player " + Name(peer) + " -> tcp " + port);
      } else if (a == 2) { lock (lk) tcp.TryGetValue(key, out s); if (s != null) try { s.Send(f, 7, f.Length - 7, SocketFlags.None); } catch { } }
      else if (a == 3) { lock (lk) { tcp.TryGetValue(key, out s); tcp.Remove(key); } if (s != null) try { s.Shutdown(SocketShutdown.Both); s.Close(); } catch { } }
    } else {
      uint k = BitConverter.ToUInt32(f, 0); int port = BitConverter.ToUInt16(f, 4);
      if (isHost) {
        if (!UDP.Contains(port)) return;
        string key = peer + ":" + k + ":" + port; UdpClient u;
        lock (lk) if (!udp.TryGetValue(key, out u)) {
          u = new UdpClient(new IPEndPoint(Src, 0)); Nocr(u); udp[key] = u; var uu = u; uint kk = k; int pp = port;
          new Thread(() => { while (true) { try { var ep = new IPEndPoint(0, 0); var d = uu.Receive(ref ep); t.Send(peer, false, F(0, kk, pp, d, d.Length)); } catch { } } }) { IsBackground = true }.Start();
        }
        var pl = f.Skip(6).ToArray(); u.Send(pl, pl.Length, new IPEndPoint(IPAddress.Loopback, port));
      } else {
        IPEndPoint ep; UdpClient u; lock (lk) keyEp.TryGetValue(k, out ep); udp.TryGetValue("L:" + port, out u);
        if (ep != null && u != null) { var pl = f.Skip(6).ToArray(); u.Send(pl, pl.Length, ep); }
      }
    }
  }
  string Name(ulong p) { var st = t as SteamT; return st != null ? st.Name(p) : p.ToString(); }
}
static class P {
  const ulong BASE = 76561197960265728UL; const string AL = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ";  // invite code = Steam account id in base32
  public static string Code(ulong sid) { ulong a = sid - BASE; var s = ""; do { s = AL[(int)(a % 32)] + s; a /= 32; } while (a > 0); return "FEAR-" + s; }
  public static ulong Parse(string c) {
    c = c.Trim().ToUpper(); if (c.Length == 17 && c.All(char.IsDigit)) return ulong.Parse(c);
    if (c.StartsWith("FEAR-")) c = c.Substring(5); ulong a = 0; foreach (var ch in c) { int i = AL.IndexOf(ch); if (i < 0) throw new Exception("bad invite code"); a = a * 32 + (ulong)i; }
    return BASE + a;
  }
  [DllImport("winmm.dll")] static extern int timeBeginPeriod(int ms);
  static int Main(string[] a) {
    try {
      Directory.SetCurrentDirectory(AppDomain.CurrentDomain.BaseDirectory);
      if (!File.Exists("steam_appid.txt")) File.WriteAllText("steam_appid.txt", "223650");
      var args = a.ToList(); Func<string, string> opt = k => { int i = args.IndexOf(k); if (i < 0 || i + 1 >= args.Count) return null; var v = args[i + 1]; args.RemoveRange(i, 2); return v; };
      string up = opt("--udp"), bind = opt("--bind"), src = opt("--src"); if (src != null) Link.Src = IPAddress.Parse(src);
      bool host = args.Count > 0 && args[0] == "host"; if (!host && (args.Count < 2 || args[0] != "join")) { Console.WriteLine("usage: FearLink host | FearLink join <code>"); return 2; }
      Transport t = up != null ? (Transport)new UdpT(int.Parse(up), host ? 0 : int.Parse(args[1])) : new SteamT();
      ulong hid = host ? t.Me : (up != null ? ulong.Parse(args[1]) : Parse(args[1]));
      var link = new Link(t, host, hid, bind == null ? null : IPAddress.Parse(bind));
      var st = t as SteamT;
      if (host) {
        Log.W("HOSTING. Invite code: " + (st != null ? Code(t.Me) : t.Me.ToString()));
        if (st != null) { st.Presence("status", "Hosting a FEAR Online game"); st.Presence("connect", "+fearjoin " + t.Me); st.Presence("steam_display", null); }
        if (st != null) try { Directory.CreateDirectory("state"); File.WriteAllText(Path.Combine("state", "peer_self"), st.Name(t.Me) ?? ""); } catch { }
        if (File.Exists("invite.txt") || true) File.WriteAllText("invite.txt", st != null ? Code(t.Me) : t.Me.ToString());
      } else Log.W("JOINING " + (st != null ? st.Name(hid) : hid.ToString()) + " - start the game with +LoginServerIP " + (bind ?? "127.0.0.1"));
      timeBeginPeriod(1);
      while (true) { t.Tick(); bool any = false; foreach (var m in t.Poll()) { any = true; link.Handle(m.Item1, m.Item2, m.Item3); } if (!any) Thread.Sleep(1); }
    } catch (Exception e) { Log.W("ERROR: " + e.Message); return 1; }
  }
}
