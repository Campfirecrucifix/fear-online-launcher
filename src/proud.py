import threading
import os
# FEAR Online ProudNet-variant login server (WIP). Run: python proud.py [port]
# Frame: 13 57 | varint(len) | payload ; payload[0] = MessageType (S4 ProudNet enum +1)
import socket, threading, struct, sys, datetime
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5, PKCS1_OAEP, AES
import re, os, zlib, time
NAMES = {int(i): n for i, n in re.findall(r"(\d+): (\w+)", next((open(f).read() for f in (os.path.join(os.path.dirname(os.path.abspath(__file__)), d, "rmi_map.txt") for d in ("..", ".")) if os.path.exists(f)), ""))}

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 30003
KEY = RSA.generate(1024)
LOG = open(f"proud_{PORT}.log", "a")
def log(*a):
    s = f"{datetime.datetime.now():%H:%M:%S} " + " ".join(map(str, a)); print(s); LOG.write(s + "\n"); LOG.flush()

def varint(n):  # client 0x10127630 (positive only)
    out = bytearray()
    while True:
        b = n & 0x7f; n >>= 7
        if n == 0:
            if b & 0x40: out += bytes([b | 0x80, 0])
            else: out.append(b)
            return bytes(out)
        out.append(b | 0x80)
def read_varint(d, i):
    n = s = 0
    while True:
        b = d[i]; i += 1; n |= (b & 0x7f) << s; s += 7
        if not b & 0x80: return n, i

def frame(p): return b"\x13\x57" + varint(len(p)) + p
def arr(b): return varint(len(b)) + b
B = lambda v: struct.pack("<B", v); I = lambda v: struct.pack("<i", v)

def hint():
    s = (B(0) + B(0) + I(1048576) + I(900000) + I(60000) + B(0) + I(15360) + B(1)   # fallback, maxlen, idle, ?, p2pcond, oversend, nagle
         + I(128) + I(512)                                              # enc key len, fast key len
         + B(1) + B(0) + B(0) + B(0) + B(0) + B(0) + B(0) + I(0))
    return B(5) + s + arr(KEY.publickey().export_key("DER", pkcs=1))

def rmi(c, st, rid, args=b""):
    n = st.get("sc", 0); st["sc"] = n + 1
    data = struct.pack("<H", n) + B(1) + struct.pack("<H", rid) + args
    pad = 16 - (len(data) + 5) % 16
    inner = data + bytes(pad) + struct.pack("<I", zlib.crc32(data)) + B(pad)
    c.sendall(frame(B(0x26) + AES.new(st["aes"], AES.MODE_ECB).encrypt(inner))); log(f"-> RMI {rid} {NAMES.get(rid, '?')} {args.hex()}")

def wstr(t): return varint(len(t)) + t.encode("utf-16le")
H = lambda v: struct.pack("<H", v)
def channel(i, name, ip, port):  # client reader 0x100c64a0
    return I(i) + B(i) + B(1) + wstr(name) + wstr(ip) + H(port) + wstr(ip) + H(port) + H(0) + H(500)
try: _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); _s.connect(("8.8.8.8", 80)); LAN_IP = _s.getsockname()[0]; _s.close()
except OSError: LAN_IP = "127.0.0.1"
PUBLIC_IP = os.environ.get("PUBLIC_IP", "auto")  # WAN IP handed to internet players ("auto" = ask api.ipify.org)
if PUBLIC_IP == "auto":
    try: import urllib.request; PUBLIC_IP = urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode().strip()
    except Exception: PUBLIC_IP = LAN_IP
def ip_for(c):  # address a client should use to reach THIS machine: loopback / LAN / WAN depending on where it connects from (avoids NAT hairpin)
    try: peer = c.getpeername()[0]
    except OSError: return PUBLIC_IP
    if peer == os.environ.get('TUNNEL_SRC'): return os.environ['TUNNEL_ADV']  # single-PC tunnel test hook
    if peer.startswith(("127.", "10.", "192.168.")) or re.match(r"172\.(1[6-9]|2\d|3[01])\.", peer): return c.getsockname()[0]  # same address the client used to reach us (VPN-proof)
    return PUBLIC_IP
GAME_IP, GAME_PORT = PUBLIC_IP, 30004
# (MapIndex, MapMode) from the client's built-in MapInfo table (read from live memory)
MAPS = [(200, 2), (515, 5), (525, 5), (518, 5), (522, 5), (529, 5), (517, 5), (531, 5), (321, 3), (204, 2), (206, 2), (213, 2), (603, 6), (103, 1), (704, 7), (705, 7), (706, 7), (423, 4), (424, 4), (425, 4), (729, 7), (730, 7), (731, 7), (802, 8), (803, 8)]
SLOT_STATE = int(os.environ.get('SLOT_STATE', '0'))
ROOM_TAIL = [int(x) for x in os.environ.get('ROOM_TAIL', '16,16,1,1,1,1,1,1,1,1').split(',')]
HOST_IP, HOST_PORT = os.environ.get('HOST_IP'), int(os.environ.get('HOST_PORT', '27999'))
# guess: weapons(5), weapon parts(6), perks(3), character, helmet, goggle, mask, face  (ids from d3.Arch01 = GameItem.csv, XOR 9)
EQUIP = [int(x) for x in os.environ.get('EQUIP', '21102201,22100201,23100101,24100101,0,31100101,32100101,33100101,34100101,0,0,0,0,0,12100101,0,0,0,0').split(',')]
HOST_FLAGS = [int(x) for x in os.environ.get('HOST_FLAGS', '1,0,0,0').split(',')]
AUTO = {30106: 30175, 30107: 30177, 30108: 30179, 30109: 30181, 30110: 30183, 42001: 42501, 41001: 41051, 40001: 40101, 35503: 35605, 35505: 35618, 35506: 35624, 35508: 35633, 35509: 35629, 35510: 35635}  # LoginLevel/PVP/PVE/Hit/Rank
import itertools
GAME = PORT >= 30005 and PORT % 10 == 5  # game servers: 30005 (room 1), 30015 (room 2), ...
GROOM = (PORT - 30005) // 10 + 1 if GAME else 0
ROOM = []  # channel-server (c, st) that got a room index
TEAM = {}  # team -> score
KD = {}  # game server: user idx -> [kills, deaths]
ROOMS = {}  # room no -> {'info','mapinfo','members','started'}  (channel server)
def room_enter(c, st, no):
    r = ROOMS[no]; st['room'] = no; st['mapinfo'] = r['mapinfo']
    r['members'] = [(cc, ss) for cc, ss in r['members'] if cc.fileno() != -1 and cc is not c] + [(c, st)]
    room_state(c, st, r)
def room_state(c, st, r):  # full room snapshot (also resent when returning from a match, else slots show -Unavailable-)
    rmi(c, st, 36101, r['info'])  # NotifyRoomInfo (Room::Info: u16 no, wstr title, wstr pw, wstr leader, i32, mapinfo5, 10xu8; reader ZNetwork 0x100cb190)
    rmi(c, st, 36102, r['mapinfo'])  # NotifyRoomMapInfo
    gidx(c, st)
    ms = [ss for cc, ss in r['members'] if cc.fileno() != -1 and 'gidx' in ss and not ((os.environ.get('DEDI') == '1') and ss['gidx'] == 1)] or [st]
    rmi(c, st, 36106, varint(len(ms)) + b''.join(struct.pack('<i', ss.get('gidx', 1)) + wstr(pname(ss.get('gidx', 1), st.get('room', 1))) + wstr("") + struct.pack('<4H', 1, 0, 0, 0) + bytes([0, ss.get('gidx', 1) - 1, (ss.get('gidx', 1) - 1) % 2, 0]) for ss in ms))  # User tail: u8 +1c, u8 +20 slot?, u8 +24 team?, u8 +2c (reader ZNetwork 0x100cba10)  # SendUserList (all members, real ids)
    rmi(c, st, 36104, struct.pack('<i', 1 if st['gidx'] == 1 else 999))  # NotifyRoomLeader: client hosts iff its id == leader
    rmi(c, st, 36109, varint(16) + b"".join(struct.pack('<i', k) + B(SLOT_STATE) for k in range(16)))
    rmi(c, st, 36112, varint(1) + struct.pack('<i', 1) + B(0))
def game_start(c, st):
    rmi(c, st, 36105, B(1))  # NotifyRoomGame
    rmi(c, st, 36951, wstr(ip_for(c)) + H(30005 + 10 * (st.get('room', 1) - 1)) + H(1) + I(1) + B(gidx(c, st)) + bytes(16))  # NotifyGameStart
    rmi(c, st, 37401, st.get('mapinfo', bytes.fromhex('0302100164')) + B(0))
    rmi(c, st, 37404, wstr(HOST_IP or ip_for(c)) + H(HOST_PORT + st.get('room', 1) - 1) + (bytes([1, 0, 0, 0]) if st['gidx'] == 1 else bytes([0, 0, 1, 0])))  # NotifyHostServer
def end_match():  # game server: RoundEnd + GameEnd to all, then reset per-match state (clients return to their room)
    for cc, ss in [x for x in PLAYERS if x[0].fileno() != -1]:
        try: rmi(cc, ss, 37419); rmi(cc, ss, 37420, bytes(4))  # GameEnd payload (reader 0x10020470) - zeros accepted
        except OSError: pass
    PLAYERS.clear(); KD.clear(); TEAM.clear()
def gidx(c, st):  # 1-based index among LIVE room members (dead sockets pruned) so joiners get 2, not 3
    if 'gidx' not in st:
        L = ROOMS[st['room']].setdefault('gl', []) if st.get('room') in ROOMS else ROOM  # slot indices are per room
        L[:] = [(cc, ss) for cc, ss in L if cc.fileno() != -1 and not ss.get('dead')]
        used = {ss['gidx'] for _, ss in L}
        st['gidx'] = next(i for i in range(1, 99) if i not in used); L.append((c, st))
        kv_set(f"slot{st.get('room', 1)}_{st['gidx']}", st.get('name', f"Player{st['gidx']}"))
    return st['gidx']
PLAYERS = []  # game-server connections (c, st) in join order; player 1 hosts (listen server), others connect to it
def uid(st):
    if 'uid' not in st: st['uid'] = len(PLAYERS) + 1
    return st['uid']
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state"); os.makedirs(STATE, exist_ok=True)
def kv_set(k, v): open(os.path.join(STATE, k), "w", encoding="utf-8").write(v)
def kv_get(k, d=""):
    try: return open(os.path.join(STATE, k), encoding="utf-8").read()
    except OSError: return d
def pname(i, r=0): return kv_get(f"slot{r or GROOM or 1}_{i}", f"Player{i}")  # display name of room/game slot i (written by channel server)
def user_elem(i): return B(i - 1) + wstr('' if (i == 1 and (os.environ.get('DEDI') == '1')) else pname(i)) + wstr('') + H(1)*4 + B(0) + B(int(os.environ.get('TEAMBASE', '1')) + (i + 1) % 2) + H(1)*4 + B(1) + B(0)
def equip_elem(i): return B(int(os.environ.get('EQKEY0','1')) and i - 1) + b''.join(I(x) for x in EQUIP)
def on_rmi(c, st, rid, args):
    log(f"<- RMI {rid} {NAMES.get(rid, '?')} {args.hex()}")
    if GAME and 37001 <= rid <= 37030 and rid != 37009: rmi(c, st, 37426 + 2 * (rid - 37001))  # game Request N -> AnswerSuccess (pairing inferred)
    if GAME and rid == 37004:  # client finished loading -> tell everyone loaded, begin round (payloads guessed)
        rmi(c, st, 37424, I(uid(st))); rmi(c, st, 37425); rmi(c, st, 37418, B(1)); rmi(c, st, 37415, B(uid(st)) + B(0) + B(0) + B(0) + H(0))  # RoundBegin u8 (reader 0x100204d0)
        if uid(st) > 1:  # joiner never sends 37009 itself -> tell everyone (host spawns it) after it joined the LithTech host
            def _jr(u=uid(st)):
                for cc, ss in PLAYERS:
                    for v in (u - 1, u):
                        if v == 1 and (os.environ.get('DEDI') == '1'): continue  # never spawn the bot host's player
                        try: rmi(cc, ss, 37424, I(v)); rmi(cc, ss, 37444, B(v))
                        except Exception: pass
            for d in (3, 6): threading.Timer(d, _jr).start()
    if GAME and rid == 37010 and uid(st) == 1:  # host's round timer expired -> end match for everyone
        end_match()
    if GAME and rid == 37011:  # RequestDeath (payload logged) -> AnswerDeathSuccess + NotifyDeath(args echoed) to all
        rmi(c, st, 37447)
        killer, victim = (args[0], args[1]) if len(args) >= 2 else (0, 0)  # guess: (killer, victim, ?, i32 weapon, u8 x3)
        KD.setdefault(victim, [0, 0])[1] += 1
        if killer != victim: KD.setdefault(killer, [0, 0])[0] += 1; TEAM[killer % 2] = TEAM.get(killer % 2, 0) + 1
        for cc, ss in (PLAYERS or [(c, st)]):
            try:
                rmi(cc, ss, 37449, args)
                for u_, (k_, d_) in KD.items():  # NotifyGameScore: GameScore{u8 user, u8 team?, u8 kill, u8 death, u16 score} (ZNetwork 0x100cd7a0)
                    rmi(cc, ss, 37415, B(u_) + B(0) + B(min(k_, 255)) + B(min(d_, 255)) + H(k_ * 100))
                for t_, v_ in TEAM.items(): rmi(cc, ss, 37417, B(t_) + B(min(v_, 255)))  # NotifyTeamScore(u8 team: 0=blue, u8 score) VERIFIED on HUD
            except OSError: pass
    if GAME and rid == 37009 and (os.environ.get('DEDI') == '1') and uid(st) == 1:
        return  # dedicated bot host: never spawn its own player (stays invisible spectator)
    if GAME and rid == 37009:  # RequestRespawn -> AnswerRespawnSuccess(u8) + NotifyRespawn(u8 user idx) to all
        rmi(c, st, 37442, B(uid(st))); [rmi(c, st, 37424, I(u)) for u in (0, uid(st))]  # re-send user-load so host spawns (player obj exists now)
        for cc, ss in (PLAYERS or [(c, st)]):
            try: rmi(cc, ss, 37444, B(uid(st)))
            except OSError: pass
    if GAME and not st.get('gs'):  # game server: push match start on first RMI
        st['gs'] = 1
        me = uid(st); PLAYERS.append((c, st)); ids = [x[1]['uid'] for x in PLAYERS]
        for cc, ss in PLAYERS:  # (re)send full user + equip lists to everyone (reader 0x100cd050 / 0x100cd420)
            try:
                ks = list(range(1, len(ids) + 2))  # keys 0..n: joiner's 36951 idx may be 1-based
                rmi(cc, ss, 37405, varint(len(ks)) + b''.join(user_elem(i) for i in ks))
                rmi(cc, ss, 37411, varint(len(ks) + 1) + b''.join(B(k) + b''.join(I(x) for x in EQUIP) for k in ks + [0]))  # keys 1..n then 0 LAST: ZNetwork FUN_100a63a0 matches key first (empty slots have key 0, flag not set) so key 0 must not be written first or a later key overwrites it
            except Exception as e: log('push err', e)
        rmi(c, st, 37401, bytes.fromhex('0302100164') + B(0))
        rmi(c, st, 37404, wstr(HOST_IP or ip_for(c)) + H(HOST_PORT + GROOM - 1) + (bytes([1, 0, 0, 0]) if me == 1 else bytes([0, 0, 1, 0])))  # flag0 = you host
    if rid == 30001:  # RequestFirstLogon(wstr id, wstr pw) -> remember account name
        try: n = args[0]; st['name'] = bytes(args[1:1 + 2 * n]).decode('utf-16le')[:16] or 'Player'
        except Exception: st['name'] = 'Player'
        rmi(c, st, 30051)  # RequestFirstLogon -> AnswerFirstLogonSuccess
    elif rid == 30101: rmi(c, st, 30151)  # RequestLogin -> AnswerLoginSuccess (args TBD)
    elif rid == 30002:
        rmi(c, st, 35103, varint(1) + channel(1, "Channel 1", ip_for(c), GAME_PORT)); rmi(c, st, 35101)  # SendChannelList + AnswerChannelListSuccess
        st["cred"] = os.urandom(16); kv_set("cred_" + st["cred"].hex(), st.get('name', 'Player')); rmi(c, st, 30053, st["cred"])  # credential GUID
    elif rid == 30003:  # CheckCredential(guid) on channel server -> recover account name
        st['name'] = kv_get("cred_" + bytes(args[:16]).hex(), 'Player'); rmi(c, st, 30055)
    elif rid == 36001:  # Room Create: wstr title, wstr pw, u16 map, u8 users, u8 ?, u8 goal, ...
        n, i = read_varint(args, 0); i += 2 * n; n, i = read_varint(args, i); i += 2 * n
        n0, j = read_varint(args, 0); t = args[j:j + 2 * n0].decode('utf-16le')
        no = next(k for k in range(1, 999) if k not in ROOMS)
        mi = bytes.fromhex(os.environ['MAPINFO']) if os.environ.get('MAPINFO') else args[i:i + 5]
        ROOMS[no] = {'info': struct.pack('<H', no) + wstr(t) + wstr(st.get('name', 'Player')) + wstr("") + struct.pack('<i', 1) + args[i:i + 5] + bytes(ROOM_TAIL), 'mapinfo': mi, 'members': [], 'started': False}
        rmi(c, st, 36114)  # AnswerCreateSuccess
        room_enter(c, st, no)
    elif rid == 36002:  # Room Join: u16 room no, wstr pw (guess)
        no = struct.unpack_from('<H', args, 0)[0] if len(args) >= 2 else 0
        if no not in ROOMS: no = next(iter(ROOMS), 0)
        if not no: rmi(c, st, 36117); return
        rmi(c, st, 36116)  # AnswerJoinSuccess
        room_enter(c, st, no)
        if ROOMS[no]['started']: game_start(c, st)  # join match in progress (dedicated bot host)
    elif rid == 36006:  # Room GameStart (leader) -> start everybody in the room
        rmi(c, st, 36126)  # AnswerGameStartSuccess
        r = ROOMS.get(st.get('room')); 
        if r: r['started'] = True
        for cc, ss in (r['members'] if r else [(c, st)]):
            try: game_start(cc, ss)
            except OSError: pass
    elif rid in (35504, 35507):  # RoomList / RefreshRoomList -> SendRoomList(CFastArray<Room::Info>) + answer
        rmi(c, st, 35610, varint(len(ROOMS)) + b''.join(r['info'] for r in ROOMS.values()))
        rmi(c, st, 35608 if rid == 35504 else 35631)
    elif rid == 36904:  # client left game (back in room) after GameEnd
        rmi(c, st, 36953)  # AnswerLeaveSuccess (guess pairing)
        r = ROOMS.get(st.get('room'))
        if r: room_state(c, st, r)
        if r and (os.environ.get('DEDI') == '1'):  # dedicated: bot re-hosts a new match, players follow automatically
            r['started'] = True
            threading.Timer(4 if st.get('gidx') == 1 else float(os.environ.get('REJOIN_DELAY', '25')), lambda: game_start(c, st)).start()
    elif rid == 35501:
        rmi(c, st, 35601, B(args[0] if args else 1))  # lobby AnswerJoinSuccess(u8 lobby)
        rmi(c, st, 36133, varint(len(MAPS)) + b"".join(B(m) + struct.pack('<HH', i, 0) for i, m in MAPS))  # NotifyModeMapList (u8 mode,u16 map,u16 ?)
        rmi(c, st, 36139, varint(len(MAPS)) + b"".join(struct.pack('<H', i) + B(1) for i, m in MAPS))  # NotifyOpenMapList (u16 map,u8 open)
    elif rid == 35002: rmi(c, st, 35104, B(1))  # channel AnswerJoinSuccess(u8 channel)
    elif rid in AUTO: rmi(c, st, AUTO[rid])
    elif NAMES.get(rid + 50) == "AnswerLoginSuccess": rmi(c, st, rid + 50)  # per-service RequestLogin

def injector(c, st):
    f = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"cmd_{PORT}.txt")
    while True:
        time.sleep(0.5)
        if os.path.exists(f) and "aes" in st:
            for line in open(f).read().split("\n"):
                if line.strip() == 'END': end_match(); continue
                if line.strip():
                    rid, *h = line.split(); pl = bytes.fromhex(h[0]) if h else b""
                    for cc, ss in ([x for x in PLAYERS if x[0].fileno() != -1] if GAME and PLAYERS else [(c, st)]):  # game server: broadcast
                        try: rmi(cc, ss, int(rid), pl)
                        except OSError: pass
            os.remove(f)

def handle(c, a):
    log("connect", a); buf = b""; st = {}
    threading.Thread(target=injector, args=(c, st), daemon=True).start()
    try:
        while (d := c.recv(65536)):
            buf += d
            while len(buf) > 3 and buf[:2] == b"\x13\x57":
                n, i = read_varint(buf, 2)
                if len(buf) < i + n: break
                p, buf = buf[i:i + n], buf[i + n:]
                t = p[0]; log(f"<- type {t:#x} len {n}: {p[1:80].hex()}")
                if t == 0x32: c.sendall(frame(hint())); log("-> hint")
                elif t == 0x6:
                    n1, j = read_varint(p, 1); st["aes"] = PKCS1_OAEP.new(KEY).decrypt(p[j:j + n1]); j += n1
                    n2, j = read_varint(p, j); st["fast_enc"] = p[j:j + n2]
                    log(f"aes key {st['aes'].hex()} fast blob {n2}b")
                    c.sendall(frame(B(7))); log("-> session key success")
                elif t in (0x25, 0x26):
                    dec = AES.new(st["aes"], AES.MODE_ECB).decrypt(p[1:]); dec = dec[:len(dec) - 5 - dec[-1]]
                    if dec[2] == 1: on_rmi(c, st, struct.unpack_from("<H", dec, 3)[0], dec[5:])
                    else: log("<- enc", dec.hex())
                elif t == 0x1c: c.sendall(frame(B(0x1d) + p[1:9] + struct.pack('<q', int(time.time() * 1000))))  # ping -> pong (echo client time, server time)
                elif t == 0x1: on_rmi(c, st, struct.unpack_from("<H", p, 1)[0], p[3:])
                elif t == 0x8:
                    ok = B(0xb) + I(1000 + a[1] % 1000) + bytes(16) + arr(b"") + B(1) + arr(ip_for(c).encode()) + struct.pack("<H", PORT)
                    c.sendall(frame(ok)); log("-> connect success")
            if buf and buf[:2] != b"\x13\x57": log("garbage", buf.hex()); buf = b""
    except Exception as e: log("err", e)
    log("disconnect", a)

try:  # dev convenience: replace a stale server on this port
    import psutil
    for cn in psutil.net_connections("tcp"):
        if cn.laddr.port == PORT and cn.status == "LISTEN" and cn.pid != os.getpid(): psutil.Process(cn.pid).kill()
    time.sleep(0.5)
except ImportError: pass
s = socket.socket(); s.bind(("0.0.0.0", PORT)); s.listen()
log("listening", PORT)
while True:
    c, a = s.accept(); threading.Thread(target=handle, args=(c, a), daemon=True).start()
