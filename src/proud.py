import threading
import os
# FEAR Online ProudNet-variant login server (WIP). Run: python proud.py [port]
# Frame: 13 57 | varint(len) | payload ; payload[0] = MessageType (S4 ProudNet enum +1)
import socket, threading, struct, sys, datetime
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5, PKCS1_OAEP, AES
import re, os, zlib, time, json, random, contextlib
try: import msvcrt
except ImportError: msvcrt = None; import fcntl
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
  with st.setdefault("lk", threading.RLock()):
    if isinstance(st.get('sent'), list): st['sent'].append(rid)  # ids answered in the current request (no Failed after a Success)
    n = st.get("sc", 0); st["sc"] = n + 1
    data = struct.pack("<H", n) + B(1) + struct.pack("<H", rid) + args
    pad = 16 - (len(data) + 5) % 16
    inner = data + bytes(pad) + struct.pack("<I", zlib.crc32(data)) + B(pad)
    c.sendall(frame(B(0x26) + AES.new(st["aes"], AES.MODE_ECB).encrypt(inner))); log(f"-> RMI {rid} {NAMES.get(rid, '?')} {args.hex()}")

def wstr(t): return varint(len(t)) + t.encode("utf-16le")
H = lambda v: struct.pack("<H", v)
def F(n): return os.environ.get(n, '1') == '1'  # protocol fixes, default ON (NAME=0 reverts one): FIX_ROOMUSER FIX_ROOMINFO FIX_TEAMS FIX_RESULTS FIX_HITCOUNT FIX_LOAD FIX_HOSTTAIL FIX_DEATH FIX_CHAT FIX_RECORDS FIX_STORE FIX_REWARD FIX_FRIENDS FIX_CLAN
def L24(v): return B(v) if F('FIX_LOAD') else I(v)  # NotifyUserLoadComplete 37424: u8 seat (old: i32)
def host_tail(host, itr=0): return bytes([1, itr if F('FIX_HOSTTAIL') else 0, 0, 0] if host else [0, itr if F('FIX_HOSTTAIL') else 0, 1, 0])  # NotifyHostServer 37404 tail: u8 isHost, u8 intrude + 2 old bytes (LIVE: the bare 2-byte tail stops the client loading the match, keep 4)
def rd_wstr(b, i): n, i = read_varint(b, i); return bytes(b[i:i + 2 * n]).decode('utf-16le', 'replace'), i + 2 * n
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
MAPS = [(533, 5), (532, 5), (515, 5), (525, 5), (518, 5), (522, 5), (529, 5), (517, 5), (531, 5), (200, 2), (321, 3), (204, 2), (206, 2), (213, 2), (603, 6), (103, 1), (704, 7), (705, 7), (706, 7), (423, 4), (424, 4), (425, 4), (729, 7), (730, 7), (731, 7), (802, 8), (803, 8)]
NOWORLD = {int(x) for x in os.environ.get('NOWORLD_MAPS', '603').split(',') if x}  # maps whose world isn't shipped in the Steam client: 603 Soul King (FO_Ghost_1 -> worlds\mp\ffm\ffm_soulking_ghetto\*.wld, folder empty) -> every client's SetNewLevel fails (LoadControl error), forced disconnect + RequestGameLeave 37026 -> closed in 36139, room create refused
SEAT0, TEAM0 = int(os.environ.get('SEAT0', 0)), int(os.environ.get('TEAM0', 0))  # 37402 NotifyInfo: seat/team base offsets (testing)
SLOT_STATE = int(os.environ.get('SLOT_STATE', '0'))
ROOM_TAIL = [int(x) for x in os.environ.get('ROOM_TAIL', '16,16,1,1,1,1,1,1,1,1').split(',')]
HOST_IP, HOST_PORT = os.environ.get('HOST_IP'), int(os.environ.get('HOST_PORT', '27999'))
def hport(room):  # ALTPORT=1: alternate host listen port per match (27999/28000) in case the previous match still holds it
    return HOST_PORT + (int(kv_get(f'mcount{room}') or 0) % 2 if os.environ.get('ALTPORT', '1') == '1' else 0)
# guess: weapons(5), weapon parts(6), perks(3), character, helmet, goggle, mask, face  (ids from d3.Arch01 = GameItem.csv, XOR 9)
EQUIP = [int(x) for x in os.environ.get('EQUIP', '21102201,22100201,23100101,24100101,0,31100101,32100101,33100101,34100101,0,0,0,0,0,12100101,0,0,0,0').split(',')]
MONEY = int(os.environ.get('MONEY', '9999999'))
DEFAULT_SLOTS = {0x15: 21102201, 0x16: 22100201, 0x17: 23100101, 0x18: 24100101, 0x0b: 11100101, 0x0c: 12100101, 0x1f: 31100101, 0x20: 32100101, 0x21: 33100101, 0x22: 34100101}
ITEMS = [(int(x), int(x[0]) * 10 + int(x[1])) for x in '''11100101 11600201 11600301 11600401 11600501 11600601 11600701 11600801 12100101 12600201 12600301 12600401 12600501 12600601 12600701 12600801 21102201 21600101 21600201 21600301 21600501 21600601 21600701 21600801 21601001 21601301 21601401 21601501 21601601 21601701 21601801 21601901 21602001 21602101 21602301 21602401 21602501 21602601 21602701 21602801 21602901 21603001 21603101 21603201 21603301 21603401 21603501 21603601 21603701 21603801 21603901 21604001 21604101 21604201 21604301 21604401 21604501 21604601 21604701 21605001 21605101 21605201 21605301 21605401 21605501 21605601 21605701 21605801 21605901 21606001 21606101 21606201 21606301 21606401 21606501 21606601 21606701 21606801 21606901 21607001 21607101 21607201 21607301 21607401 21607501 21607601 21607701 21607801 22100201 22600101 22600301 22600401 22600501 22600601 22600701 22600801 23100101 23600301 23600401 23600501 23600601 23600701 23600801 24100101 24600201 24600301 24600401 24600501 25600101 25600201 25600301 31400101 31400201 31400301 31400401 31400501 31400601 31400701 32400101 32400201 32400301 32400401 32400501 32400601 32400701 33400101 33400201 33400301 34400101 34400301 34400401 34400501 34400601 34400701 34401001 34600201 61400201 61400301 62400101 62400201 62400301 62400401 62400501 62400601 63400101 64400101 65400101 66400101 81400101 81400501 81400801 81400901 81401001 81401101 81401801 81402101 81402201 81402301 81402401 81402501 81402601 81402701 81402801 81402901 81403001 81403101'''.split()]  # one GameItem per model (RecordName; prefer default UseType1 > Permanent 6 > Period 4 > Durability 2), IsInvenShow=1, HighGroup 1/2/3/6/8; category = HighGroup*10+MiddleGroup = slot type
ITEM_IDS = {x for x, _ in ITEMS}
def slots_of(name):
    try: own = ITEM_IDS | ({e[1] for e in inv_of(name)['x']} if F('FIX_STORE') else set()); return {**DEFAULT_SLOTS, **{int(k): v for k, v in json.loads(kv_get('slots_' + name) or '{}').items() if v in own}}  # drop saved items no longer in the inventory
    except Exception: return dict(DEFAULT_SLOTS)
def equip_of(name):  # 37411 equip array (19 x i32): 0-4 weapon slots 0x15.., 5-8 gear 0x1f.., 14 character
    sl = slots_of(name); e = list(EQUIP)
    for i in range(5): e[i] = sl.get(0x15 + i, e[i])
    for i in range(4): e[5 + i] = sl.get(0x1f + i, e[5 + i])
    return e
INV_DEFAULT = [(21102201, 0x15), (22100201, 0x16), (23100101, 0x17), (24100101, 0x18), (11100101, 0x0b), (12100101, 0x0c)]  # slot types from ZNetwork 0x10029590: 0xb/0xc hero ATC/TF (ServerData+0x130/0x138), 0x15..0x19 weapon slots (+0x140..)
HOST_FLAGS = [int(x) for x in os.environ.get('HOST_FLAGS', '1,0,0,0').split(',')]
AUTO = {30106: 30175, 30107: 30177, 30108: 30179, 30109: 30181, 30110: 30183, 42001: 42501, 41001: 41051, 40001: 40101, 35503: 35605, 35505: 35618, 35506: 35624, 35508: 35633, 35509: 35629, 35510: 35635, 39001: 39101, 42002: 42503, 39401: 39501, 39601: 39701, 43001: 43051}  # LoginLevel/PVP/PVE/Hit/Rank
import itertools
GAME = PORT >= 30005 and PORT % 10 == 5  # game servers: 30005 (room 1), 30015 (room 2), ...
GROOM = (PORT - 30005) // 10 + 1 if GAME else 0
ROOM = []  # channel-server (c, st) that got a room index
TEAM = {}  # team -> score
KD = {}  # game server: user idx -> [kills, deaths]
ROOMS = {}  # room no -> {'info','mapinfo','members','started'}  (channel server)
def prune_rooms():  # drop rooms whose members all disconnected (else stale 'started' rooms send joiners into dead matches)
    for r in ROOMS.values():  # dedicated: the bot host is killed+relaunched between matches -> keep its room alive meanwhile
        if any(ss.get('name') == 'BOT' and cc.fileno() != -1 for cc, ss in r['members']): r['bot_seen'] = time.time()
    for no in [k for k, r in ROOMS.items() if not (os.environ.get('DEDI') == '1' and time.time() - r.get('bot_seen', 0) < 120) and not any(cc.fileno() != -1 and not ss.get('dead') and time.time() - ss.get('last', time.time()) < 60 for cc, ss in r['members'])]:  # silent >60s = ghost (Steam tunnel kept socket open; live clients ping ~18s)
        log("room", no, "closed (empty)"); del ROOMS[no]
def room_enter(c, st, no):
    r = ROOMS[no]; st['room'] = no; st['mapinfo'] = r['mapinfo']
    kv_set(f"map{no}", r['mapinfo'].hex())  # game server (separate process) sends the room's map in 37401
    r['members'] = [(cc, ss) for cc, ss in r['members'] if cc.fileno() != -1 and cc is not c] + [(c, st)]
    room_state(c, st, r); room_refresh(r, c)
def room_refresh(r, skip=None):  # resend room snapshot to everyone else (join/leave/team change)
    for cc, ss in r['members']:
        if cc is skip or cc.fileno() == -1: continue
        try: room_state(cc, ss, r)
        except OSError: pass
def room_info(r):  # Room::Info: u16 no, wstr title, wstr pw, wstr mapName, u32 leader, mapinfo5, u8 cur, u8 max, 8 x u8 (type, public, state, teamBal, instr, deathChat, perk, 3rdView)
    if not F('FIX_ROOMINFO') or 'rawmi' not in r: return r['info']
    cur = sum(1 for cc, ss in r['members'] if cc.fileno() != -1 and not ss.get('dead') and not (os.environ.get('DEDI') == '1' and ss.get('name') == 'BOT'))
    return r['info'][:2] + wstr(r.get('title', '')) + wstr('') + wstr('') + struct.pack('<I', 1) + r['rawmi'] + bytes([min(cur, 255), r.get('max', 16)] + ROOM_TAIL[2:])  # leader = room user id 1 (see 36104)
def room_state(c, st, r):  # full room snapshot (also resent when returning from a match, else slots show -Unavailable-)
    rmi(c, st, 36101, room_info(r))  # NotifyRoomInfo (Room::Info: u16 no, wstr title, wstr pw, wstr leader, i32, mapinfo5, 10xu8; reader ZNetwork 0x100cb190)
    rmi(c, st, 36102, r['mapinfo'])  # NotifyRoomMapInfo
    rmi(c, st, 36103, wstr(r.get('title', 'F.E.A.R. Online')) + wstr('') + B(0) + r['mapinfo'] + B(0) + bytes(int(x) for x in os.environ.get('ROOMOPT', '0,1,1,1,1,0').split(',')))  # NotifyRoomSetting (reader ZNetwork stub 0x10080f66): wstr title, wstr pw, u8, mapinfo5, u8, 6x bool options (team balance first?)
    gidx(c, st)
    ms = [ss for cc, ss in r['members'] if cc.fileno() != -1 and 'gidx' in ss and not ((os.environ.get('DEDI') == '1') and ss['gidx'] == 1)] or [st]
    rmi(c, st, 36106, varint(len(ms)) + b''.join(struct.pack('<i', ss.get('gidx', 1)) + wstr(pname(ss.get('gidx', 1), st.get('room', 1))) + wstr("") + struct.pack('<4H', 1, 0, 0, 0) + (bytes([lvl(ss.get('name', '')), tm(ss) + int(os.environ.get('RTEAMBASE', '1')), ss.get('rstate', 0), 0]) if F('FIX_ROOMUSER') else bytes([0, ss.get('gidx', 1) - 1, tm(ss) + int(os.environ.get('RTEAMBASE', '1')), 0])) for ss in ms))  # FIX_ROOMUSER tail: u8 level, u8 team 1/2, u8 state 0 wait/2 ready, u8 hasClan  # User tail: u8 +1c, u8 +20 slot?, u8 +24 team?, u8 +2c (reader ZNetwork 0x100cba10)  # SendUserList (all members, real ids)
    rmi(c, st, 36104, struct.pack('<i', 1 if st['gidx'] == 1 else 999))  # NotifyRoomLeader: client hosts iff its id == leader
    rmi(c, st, 36109, varint(16) + b"".join(struct.pack('<i', k) + B(SLOT_STATE) for k in range(16)))
    rmi(c, st, 36112, varint(len(ms)) + b''.join(struct.pack('<i', ss.get('gidx', 1)) + B(tm(ss) + int(os.environ.get('RTEAMBASE', '1'))) for ss in ms))  # NotifyTeamList (i32 user, u8 team)
def tm(ss):  # room team 0/1 (default alternate by slot); persisted for the game-server process
    return ss.setdefault('team', (ss.get('gidx', 1) - 1) % 2)
def game_start(c, st, _loop=False):
    if not _loop:  # one pending start per player: a second trigger (START click + auto rejoin) would send NotifyGameStart twice -> client crash
        if st.get('gs_pending'): log(f"game_start dup ignored gidx={st.get('gidx')}"); return
        st['gs_pending'] = True
    if _loop and 'room' not in st: st['gs_pending'] = False; log(f"game_start cancelled gidx={st.get('gidx')} (left room)"); return
    hold = os.environ.get('DEDI') == '1'
    if hold and st.get('gidx') != 1 and kv_get(f"botready{st.get('room', 1)}") != '1' and st.setdefault('gs_wait', 0) < int(os.environ.get('BOT_WAIT', '150')):  # dedicated: players join only once the bot finished loading the new match (else the bot's reload hangs)
        if st['gs_wait'] % 10 == 0: log(f"game_start wait gidx={st.get('gidx')} room={st.get('room')} botready={kv_get('botready' + str(st.get('room', 1)))} n={st['gs_wait']}")
        st['gs_wait'] += 1; threading.Timer(1, lambda: game_start(c, st, True)).start(); return
    itr = 1 if st.pop('intrude', 0) else 0  # joining a match already running (37404 intrude)
    if c.fileno() == -1:  # delayed start: the player's channel socket may have been replaced while we waited for the bot -> use the live one
        live = [(cc, ss) for cc, ss in list(SESS) + [m for r in ROOMS.values() for m in r.get('members', [])] if cc.fileno() != -1 and not ss.get('dead') and (ss is st or (st.get('name') and ss.get('name') == st.get('name')))]
        if not live: log(f"game_start: socket gone, no live connection for gidx={st.get('gidx')} name={st.get('name')}"); st['gs_pending'] = False; return
        log(f"game_start: socket replaced, resending on live connection gidx={st.get('gidx')}"); c, st2 = live[0]
        if st2 is not st: st2['gs_pending'] = True; st2.setdefault('gidx', st.get('gidx')); st = st2
    log(f"game_start send gidx={st.get('gidx')} room={st.get('room')} after {st.get('gs_wait')}"); st['gs_wait'] = 0; st['gs_pending'] = False
    if hold and st.get('gidx') != 1 and st.get('room') in ROOMS and os.environ.get('REJOINPATH', '1') == '1': rmi(c, st, 36116); room_enter(c, st, st['room'])  # replay the room-join path (AnswerJoinSuccess + room snapshot), which is what makes the 1st match switch screens  # fresh room snapshot (relaunched bot = leader present) right before start, like the join path
    if st.get('gidx') == 1: kv_set(f"botready{st.get('room', 1)}", '0')  # bot (re)hosting: not ready until its 37004
    kv_set(f"team{st.get('room', 1)}_{st.get('gidx', 1)}", str(tm(st)))
    rmi(c, st, 36105, B(1))  # NotifyRoomGame
    rmi(c, st, 36951, wstr(ip_for(c)) + H(30005 + 10 * (st.get('room', 1) - 1)) + H(int(os.environ.get('GS_H', '1'))) + I(int(os.environ.get('GS_I', '1'))) + B(gidx(c, st) - int(os.environ.get('GIDX0', '1'))) + bytes.fromhex(os.environ.get('GS_TAIL', '00' * 16)))  # NotifyGameStart
    rmi(c, st, 37401, host_map(st.get('mapinfo', bytes.fromhex('0302100164')), st.get('room', 1), st.get('gidx') == 1) + B(0))
    kv_set(f"intrude{st.get('room', 1)}_{st.get('gidx', 1)}", str(itr))  # game server (separate process) sends 37404 too
    rmi(c, st, 37404, wstr(HOST_IP or ip_for(c)) + H(hport(st.get('room', 1))) + host_tail(st['gidx'] == 1, itr))  # NotifyHostServer
KILL_MODES = {3, 5, 8}  # MapMode (= MapIndex // 100) whose MapInfo row has a Kill list (csv_dec/e.txt: Knife, TeamDeathMatch, Rag); only these send the kill goal in mapinfo[4]
FFA_MODES = {int(x) for x in os.environ.get('FFA_MODES', '').split(',') if x}  # free-for-all modes: kill goal is per player (none in the MapInfo table; all kill modes are team modes)
def mode_of(mi): return struct.unpack_from('<H', mi)[0] // 100 if len(mi) >= 2 else 0  # mapinfo = u16 MapIndex, u8 users, u8 ?, u8 goal
def gteam(i): return int(kv_get(f'team{GROOM}_{i}') or kv_get(f'team{GROOM}_{i-1}') or (i + 1) % 2)  # room team 0/1 of game user i (written by channel server game_start)
def host_map(mi, room, host):  # host's timer = goal byte minutes (GameServer patch) -> give the host the room's Time instead of the kill goal (kill modes only)
    t = kv_get(f"time{room}")
    return mi[:4] + bytes([max(1, min(255, int(t)))]) if host and t and len(mi) >= 5 and mode_of(mi) in KILL_MODES else mi
def end_match():  # game server: RoundEnd + GameEnd to all, then reset per-match state (clients return to their room)
  with LOCK:
    m = kv_get(f'mcount{GROOM}') or '0'
    if kv_get(f'endm{GROOM}') == m: log('end_match: already ended', m); return
    kv_set(f'endm{GROOM}', m)
    if os.environ.get('PREEND', '1') == '1':  # tell channel server to clear the room's in-game flag BEFORE GameEnd (else returning clients see 'Playing' and auto-rejoin -> stray reload)
        kv_set(f'ended{GROOM}', str(time.time())); time.sleep(1.2)
    res, win = results() if F('FIX_RESULTS') else (None, None)
    if F('FIX_RECORDS'): save_records(win_team())
    rw = rewards(win_team()) if F('FIX_REWARD') else None  # computed + persisted once per match
    for cc, ss in [x for x in PLAYERS if x[0].fileno() != -1]:
        try:
            if res is not None: rmi(cc, ss, 37409, res)  # NotifyUserResultList (results screen) before RoundEnd
            if rw is not None: rmi(cc, ss, 37410, rw)  # NotifyUserRewardList: XP / GP / item columns
            rmi(cc, ss, 37419); rmi(cc, ss, 37420, B(win) if res is not None else bytes(4))  # GameEnd: u8 winning team 1/2, 0 = draw (old: 4 zero bytes)
        except OSError: pass
    for _, ss in PLAYERS: ss.pop('loaded', None); ss.pop('lc_sent', None)  # 37425 state is per match
    PLAYERS.clear(); KD.clear(); TEAM.clear()
    kv_set(f'mcount{GROOM}', str(int(kv_get(f'mcount{GROOM}') or 0) + 1))  # next match uses the other host port (hport)
def seats():  # game seats to report: live players + anyone with a score (dedicated bot host excluded)
    s = {x[1].get('uid') for x in PLAYERS if x[0].fileno() != -1} | set(KD)
    return sorted(u for u in s if u and not (u == 1 and os.environ.get('DEDI') == '1'))
def win_team():  # TEAM keys are room teams 0/1 -> wire teams 1/2; 0 = draw
    a, b = TEAM.get(0, 0), TEAM.get(1, 0)
    return 1 if a > b else 2 if b > a else 0
def results():  # NotifyUserResultList 37409: varint n, per seat [u8 seat][u8 team][u16 deaths][u16 assists][u16 kills][u16 points][u16 0][7 x 0]
    ss_ = seats(); rows = b''
    for u in ss_:
        k, d, a = (KD.get(u, []) + [0, 0, 0])[:3]
        rows += B(u) + B(gteam(u) + 1) + struct.pack('<5H', d, a, k, min(k * 100, 65535), 0) + bytes(7)
    return varint(len(ss_)) + rows, win_team()
def save_records(win):  # per-account PvP totals for PLAYER INFO (30953); win None = unknown
    for cc, ss in PLAYERS:
        if not ss.get('acct') or not ss.get('uid'): continue
        try:
            r = json.loads(kv_get('rec_' + ss['acct']) or '{}'); k, d, a = (KD.get(ss['uid'], []) + [0, 0, 0])[:3]
            r['kill'] = r.get('kill', 0) + k; r['death'] = r.get('death', 0) + d
            if win is not None:
                t = gteam(ss.get('gidx', ss['uid'])) + 1; key = 'draw' if win == 0 else 'win' if win == t else 'lose'; r[key] = r.get(key, 0) + 1
            kv_set('rec_' + ss['acct'], json.dumps(r))
        except Exception as e: log('save_records', e)
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
    if 'uid' not in st:  # drop dead game connections first; if nobody live is left the match is over -> fresh match state
        PLAYERS[:] = [x for x in PLAYERS if x[0].fileno() != -1 and not x[1].get('dead')]
        if not PLAYERS: KD.clear(); TEAM.clear()
        used = {x[1].get('uid') for x in PLAYERS}; g = st.get('gidx')  # uid = room slot (gidx) when free: by connect order a simultaneous joiner could win uid 1 = 'you host' (37404) -> two hosts, joiner hangs on loading
        st['uid'] = g if g and g not in used else next(i for i in range(1, 99) if i not in used)
    return st['uid']
def myteam(st): return gteam(st.get('gidx') or uid(st)) + 1  # wire team 1/2 of a game connection
def load_done(c, st):  # NotifyLoadComplete 37425: once per player, when everyone live has loaded (late joiners get it at once; LOADWAIT s fallback)
    st['loaded'] = 1
    live = [x for x in PLAYERS if x[0].fileno() != -1 and not x[1].get('dead')]
    if not any(ss is st for _, ss in live): live.append((c, st))
    rnd = round_lc(); want = int(kv_get(f'nplay{GROOM}') or 0) if rnd else 0  # round modes (Demolition..): a 37425 before every member loaded starts the round on the listen host;
    # a joiner still connecting then sits in PreGameLobby (RE GameClient 0x101a4510: remote client waits there in non-TDM modes) / host hangs on loading -> Go server semantics: only when all have loaded
    if all(ss.get('loaded') for _, ss in live) and sum(1 for _, ss in live if ss.get('loaded')) >= want:
        for cc, ss in live:
            if not ss.get('lc_sent'):
                ss['lc_sent'] = 1
                try: rmi(cc, ss, 37425)
                except OSError: pass
    elif not st.get('lc_sent') and not rnd:
        def _lw(c=c, st=st):
            with LOCK:
                if st.get('lc_sent') or c.fileno() == -1: return
                st['lc_sent'] = 1; log('37425 fallback (not everyone loaded) uid', st.get('uid'))
                try: rmi(c, st, 37425)
                except OSError: pass
        threading.Timer(float(os.environ.get('LOADWAIT', '10')), _lw).start()
def room_round(no): return F('FIX_ROUNDLC') and mode_of(bytes.fromhex(kv_get(f"map{no}") or '00000000')) != 5
def round_lc():  # RE GameClient 0x101a4510: in every mode but TDM (5) a remote client waits in PreGameLobby until NotifyLoadComplete 37425
    # (Client_On_GAME_LOAD_COMPLETE_Callback 0x1033fd20 -> StartLoadWorld) before it loads / sends 37004 -> joiners need it once the host has loaded (Demolition load hang)
    return room_round(GROOM)
SELF = {}
SESS = []  # live channel sessions (c, st)
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state"); os.makedirs(STATE, exist_ok=True)
NAME_RE = re.compile(r'[\w -]{1,16}')  # account names (login / friend targets); also keeps them safe as file names
def clean_name(s): return re.sub(r'[^\w -]', '_', s or '').strip()[:16] or 'Player'
def kv_path(k):  # state file of key k; keys are plain names only (no path separators / drive / '..' -> nothing outside STATE)
    if not isinstance(k, str) or not re.fullmatch(r'[\w -]{1,80}', k): raise ValueError(f'bad state key {k!r}')
    return os.path.join(STATE, k.lower())  # case-insensitive keys: 'Bob' / 'bob' are one account on every file system (NTFS ignores case anyway)
def kv_old(k): return os.path.join(STATE, k)  # pre-lowercase file name (read fallback / migration)
def kv_set(k, v):  # atomic: write a temp file, then os.replace (readers in other processes never see a half-written file)
    p = kv_path(k); tmp = f'{p}.{os.getpid()}.{threading.get_ident()}.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f: f.write(v)
    except BaseException:
        try: os.remove(tmp)
        except OSError: pass
        raise
    for n in range(5):
        try: return os.replace(tmp, p)
        except PermissionError:  # Windows: target briefly open by a reader
            if n == 4: os.remove(tmp); raise
            time.sleep(0.02)
def kv_get(k, d=""):
    try: p = kv_path(k)
    except ValueError: return d
    for n in range(5):
        try:
            with open(p, encoding='utf-8') as f: return f.read()
        except FileNotFoundError:
            if p != kv_old(k) and os.path.exists(kv_old(k)): p = kv_old(k); continue  # old-case file (case-sensitive FS): use it until rewritten
            return d
        except OSError: time.sleep(0.02)  # e.g. Windows sharing violation during a replace
    raise OSError(f'state {k} unreadable')  # never read as 'missing' (would look like 'no clan' / 'name free')
def kv_del(k):  # delete a key (instead of blanking it)
    for p in {kv_path(k), kv_old(k)}:
        for n in range(5):
            try: os.remove(p); break
            except FileNotFoundError: break
            except PermissionError:
                if n == 4: raise
                time.sleep(0.05)
def kv_claim(k, v):  # create key k only if it doesn't exist (O_EXCL: atomic across processes) -> True if claimed
    p = kv_path(k)
    if p != kv_old(k) and os.path.exists(kv_old(k)): return False
    try: fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError: return False
    with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(v)
    return True
def kv_json(k):  # parsed JSON state ({} if missing); corrupt data raises instead of reading as empty (a save would wipe it)
    for n in range(3):
        s = kv_get(k)
        try: return json.loads(s) if s else {}
        except ValueError: time.sleep(0.05)
    raise ValueError(f'corrupt state file {k}: refusing to use it')
XL = threading.local()
@contextlib.contextmanager
def xlock(timeout=5):  # cross-process lock (state/state.lock) around read-modify-write of shared state; re-entrant per thread
    if getattr(XL, 'n', 0):
        XL.n += 1
        try: yield
        finally: XL.n -= 1
        return
    fd = os.open(os.path.join(STATE, 'state.lock'), os.O_RDWR | os.O_CREAT); end = time.time() + timeout
    try:
        while True:
            try: msvcrt.locking(fd, msvcrt.LK_NBLCK, 1) if msvcrt else fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); break
            except OSError:
                if time.time() > end: raise TimeoutError('state lock busy')
                time.sleep(0.01)
        XL.n = 1
        try: yield
        finally:
            XL.n = 0; os.lseek(fd, 0, 0)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1) if msvcrt else fcntl.lockf(fd, fcntl.LOCK_UN)
    finally: os.close(fd)
def locked(f):
    def w(*a, **k):
        with xlock(): return f(*a, **k)
    return w
def acct_of(i, r=0): return kv_get(f"slot{r or GROOM or 1}_{i}")  # account of room slot i, no fallback (rewards / records / loadouts)
def pname(i, r=0): return kv_get(f"slot{r or GROOM or 1}_{i}") or kv_get(f"slot{r or GROOM or 1}_{i-1}") or f"Player{i}"  # extra 1-based key copies the previous slot (joiner lookup)  # display name of room/game slot i (written by channel server)
def user_elem(i): return B(i - 1) + wstr('' if (i == 1 and (os.environ.get('DEDI') == '1')) else pname(i)) + wstr('') + H(1)*4 + B(0) + B(int(os.environ.get('TEAMBASE', '1')) + gteam(i)) + H(1)*4 + B(1) + B(0)
def equip_elem(i): return B(int(os.environ.get('EQKEY0','1')) and i - 1) + b''.join(I(x) for x in EQUIP)
def chat_scope(c, st):  # lobby chat goes to lobby users (channel sessions outside rooms), room chat to the room's members
    r = ROOMS.get(st.get('room'))
    pool = r['members'] if r else [x for x in SESS if x[1].get('room') not in ROOMS]
    out = []
    for cc, ss in pool + [(c, st)]:
        if cc.fileno() != -1 and not ss.get('dead') and all(cc is not o for o, _ in out): out.append((cc, ss))
    return out
# ---- client data tables (GameItem / ClassInfo / MapInfo / RewardItem / Recipe / FunctionItem): CSV in <game>/x3.Arch01, every line XOR 9; [] if the game dir is missing
GDIR = next((d for d in (os.environ.get('GAMEDIR', ''), os.path.dirname(os.path.dirname(os.path.abspath(__file__))), r'C:\Program Files (x86)\Steam\steamapps\common\FEAR Online\FEAR_Online') if d and os.path.exists(os.path.join(d, 'd3.Arch01'))), '')
_GT = {}
def gtab(arch):  # a3 ClassInfo, d3 GameItem, e3 MapInfo, i3 RewardItem, j3 Recipe, r3 FunctionItem
    if arch not in _GT:
        try: rows = [bytes(ch ^ 9 for ch in l).decode('latin1').split(',') for l in open(os.path.join(GDIR, arch + '.Arch01'), 'rb').read().split(b'\r\n') if l]
        except OSError: rows = [[]]
        _GT[arch] = [dict(zip(rows[0], r)) for r in rows[1:]]
    return _GT[arch]
def ival(r, k):
    try: return int((r or {}).get(k) or 0)
    except ValueError: return 0
def gitem(x):
    if 'd3i' not in _GT: _GT['d3i'] = {ival(r, 'ItemIndex'): r for r in gtab('d3')}
    return _GT['d3i'].get(x)
def itype(x): r = gitem(x); return 0x0B + (ival(r, 'HighGroup') - 1) * 10 + ival(r, 'MiddleGroup') - 1 if r else int(str(x)[:2] or 0)  # slot type (= HighGroup*10+MiddleGroup for 1-digit groups)
def ifunc(x):  # FunctionItem.FunctionType of the item's FunctionIndex (last byte of Item::Info; 17 = PVE ticket)
    if 'r3f' not in _GT: _GT['r3f'] = {ival(r, 'FunctionIndex'): ival(r, 'FunctionType') & 0xFF for r in gtab('r3')}
    return _GT['r3f'].get(ival(gitem(x), 'FunctionIndex'), 0)

# ---- FIX_STORE: per-account inventory extras on top of the fixed 'own everything' list (serials 1..BASE_N)
BASE_N = len(ITEMS) + 1
INV_MAX = int(os.environ.get('INV_MAX', '1000'))  # saved entries per account (serials stay below 65536)
def inv_of(name):  # {'x': [[serial, ItemIndex, value, type]] bought/crafted/reward items, 'm': [[parent, child, slot]] gear/perk/custom-part mounts}
    d = kv_json('inv_' + name)
    return {'x': [e for e in d.get('x', []) if 0 < e[0] <= 65535], 'm': d.get('m', [])}  # serials are u16 on the wire
def inv_save(name, d): kv_set('inv_' + name, json.dumps(d))
@locked
def inv_add(name, x, n=1):  # grant ItemIndex x: mergeable items stack (value = count), others get a new serial (value = count, or seconds left for rentals); -> (row, is_new)
    d = inv_of(name); r = gitem(x)
    for e in d['x']:
        if e[1] == x:  # owned: stack mergeable items, reuse the serial of non-stacking ones
            if ival(r, 'IsMerge'): e[2] += n; inv_save(name, d)
            return e, False
    if len(d['x']) >= INV_MAX: raise ValueError(f'inventory of {name} full')
    used = {e[0] for e in d['x']}
    e = [next(s for s in range(BASE_N + 1, 65536) if s not in used), x, ival(r, 'UseTime') or n, itype(x)]
    d['x'].append(e); inv_save(name, d); return e, True
def item_row(s, x, v, t): return H(s) + I(x) + I(v) + B(1) + B(0) + B(t) + B(ifunc(x))  # Item::Info [u16 serial][i32 ItemIndex][i32 value][u8 state 1][u8 aux 0][u8 type][u8 function]
def is_custom(t): return 0x3D <= t <= 0x42  # weapon custom-part slots (Item::Equip rows); others mount as Item::Slot
STORE_OK = {39009: 39117, 39010: 39119, 39011: 39121, 39012: 39123, 39604: 39707, 39605: 39709}  # Equip/Break Custom, Equip/Break Gear, Equip/Break Perk -> Answer...Success (fail = +1)
@locked
def store(c, st, rid, args):  # FIX_STORE hangar handlers (buy custom part / mounts / perk slot / crafting); failures answer [u32 0]
    name = st.get('name', 'Player'); inv = st.setdefault('inv', {}); byidx = st.setdefault('byidx', {})
    def give(x):  # add to account + session, push SendItem 30456 (new) / SendItemValue 30462 (stack)
        e, new = inv_add(name, x); inv[e[0]] = (x, e[3]); byidx.setdefault(x, e[0])
        rmi(c, st, 30456, item_row(*e)) if new else rmi(c, st, 30462, H(e[0]) + I(e[2]) + B(1)); return e
    if rid == 39606: return rmi(c, st, 39711, bytes(args))  # RequestIncreasePerkSlot -> echo
    if rid == 39008:  # RequestBuyCustomItem [u16 weapon serial][i32 part] -> part bought + mounted: SendItem, SendEquip 30466, Answer 39115 [u16 serial][i32 part]
        if len(args) < 6 or struct.unpack_from('<H', args)[0] not in inv or (gtab('d3') and not gitem(struct.unpack_from('<i', args, 2)[0])): return rmi(c, st, 39116, I(0))
        w, x = struct.unpack_from('<Hi', args); rmi(c, st, 30255, struct.pack('<q', MONEY)); e = give(x)
        d = inv_of(name)
        for m in [m for m in d['m'] if m[1] == e[0] and m[0] != w]: rmi(c, st, 30466, H(e[0]) + H(m[0]) + B(m[2]) + B(0))  # owned part moves: unmount it elsewhere
        d['m'] = [m for m in d['m'] if not (m[0] == w and m[2] == e[3]) and m[1] != e[0]] + [[w, e[0], e[3]]]; inv_save(name, d)
        rmi(c, st, 30466, H(e[0]) + H(w) + B(e[3]) + B(1)); return rmi(c, st, 39115, H(e[0]) + I(x))
    if rid == 39404:  # RequestRecipeItem [u32 recipe] -> consume materials (SendDeleteItem 30458 / SendItemValue), SendItem output, Answer 39507 [u32 recipe][u32 output]
        rid_ = struct.unpack_from('<I', args)[0] if len(args) >= 4 else 0
        r = next((q for q in gtab('j3') if ival(q, 'id') == rid_ and ival(q, 'exist')), None); d = inv_of(name)
        need = [(ival(r, f'Material{k}'), ival(r, f'mCount{k}')) for k in range(1, 7)] if r else []
        need = [(m, n) for m, n in need if m and n]
        if not r or any(sum(e[2] for e in d['x'] if e[1] == m) < n for m, n in need): log('craft rejected', rid_); return rmi(c, st, 39508, I(0))
        for m, n in need:
            for e in [e for e in d['x'] if e[1] == m]:
                k = min(n, e[2]); e[2] -= k; n -= k
                if e[2] <= 0: d['x'].remove(e); inv.pop(e[0], None); rmi(c, st, 30458, H(e[0]))
                elif k: rmi(c, st, 30462, H(e[0]) + I(e[2]) + B(1))
        inv_save(name, d); x = ival(r, 'itemOutput'); give(x); return rmi(c, st, 39507, I(rid_) + I(x))
    if rid == 39604 and len(args) == 2: return equip_item(c, st, struct.unpack_from('<H', args)[0], 39707)  # perk by serial only
    ok_ = STORE_OK[rid]
    if len(args) < 4: return rmi(c, st, ok_ + 1, I(0))
    p, ch_ = struct.unpack_from('<2H', args); x, t = inv.get(ch_, (0, 0)); on = rid in (39009, 39011, 39604)
    d = inv_of(name); hit = [m for m in d['m'] if m[0] == p and (m[2] == t if on else m[1] == ch_)]
    if not x or p not in inv or (not on and not hit): return rmi(c, st, ok_ + 1, I(0))
    d['m'] = [m for m in d['m'] if m not in hit] + ([[p, ch_, t]] if on else []); inv_save(name, d)
    rmi(c, st, 30466, H(ch_) + H(p) + B(t) + B(on)) if is_custom(t) else rmi(c, st, 30460, H(p) + H(ch_) + I(x) + B(t) + B(on))  # SendEquip [child][parent][slot][active] / SendSlot [parent][child][i32 item][slot][active]
    rmi(c, st, ok_, bytes(args[:4]))
@locked
def equip_item(c, st, n, ans=39107):  # RequestEquipItem(u16 serial) -> SendEquipSlot 30464 (+ old SendEquip 30466 rows when FIX_STORE=0) + Answer(u16); remember per account (used in matches)
    x, t = st.get('inv', {}).get(n, (0, 0)); nm = st.get('name', 'Player')
    if x:
        sl = slots_of(nm); old_ = sl.get(t); sl[t] = x; kv_set('slots_' + nm, json.dumps(sl))
        if not F('FIX_STORE') and old_ in st['byidx'] and old_ != x: rmi(c, st, 30466, H(st['byidx'][old_]) + H(0) + B(t) + B(0))
        rmi(c, st, 30464, H(n) + I(x) + B(t))
        if not F('FIX_STORE'): rmi(c, st, 30466, H(n) + H(0) + B(t) + B(1))
    rmi(c, st, ans, H(n))

# ---- FIX_REWARD: end-of-match XP / GP / item (NotifyUserRewardList 37410), persisted per account (prog_<acct>), level from ClassInfo
def prog(acct):
    return {'exp': 0, 'point': 0, **kv_json('prog_' + acct)}
def level_of(exp): return max([1] + [ival(r, 'ClassLevel') for r in gtab('a3') if r.get('ClassLevel') and ival(r, 'ExpMin') <= exp])
def lvl(name): return min(level_of(prog(name)['exp']), 255) if F('FIX_REWARD') else 1
def roll(idx):  # RewardItem rows of one RewardIndex: n = 1..RandomMax, the row whose [Min, Max] holds n gives the item (0 = nothing)
    rs = [r for r in gtab('i3') if idx and ival(r, 'RewardIndex') == idx]
    n = random.randint(1, max([ival(r, 'RandomMax') for r in rs] + [1]))
    return next((ival(r, 'RewardItem') for r in rs if ival(r, 'Min') <= n <= ival(r, 'Max')), 0)
@locked
def grant(acct, exp, pt, item):  # add XP/GP (+ item); level-up grants ClassInfo RewardItemIndex1..3 of every level passed
    p = prog(acct); old = level_of(p['exp']); p['exp'] += exp; p['point'] += pt; new = level_of(p['exp']); p['level'] = new
    kv_set('prog_' + acct, json.dumps(p))
    for x in [item] + [ival(r, f'RewardItemIndex{k}') for r in gtab('a3') if old < ival(r, 'ClassLevel') <= new for k in (1, 2, 3)]:
        if x: inv_add(acct, x)
    if new > old: log(f'level up {acct}: {old} -> {new} (exp {p["exp"]})')
def rewards(win):  # NotifyUserRewardList 37410: varint n, per seat [u8 seat][u16 exp][u16 point][u32 item]; XP = REWARD_BASE + 10/kill + 3/assist + 50 win / 25 draw / 10 lose, GP = 2 x XP
    mi = bytes.fromhex(kv_get(f'map{GROOM}') or '0000'); m = next((r for r in gtab('e3') if len(mi) >= 2 and ival(r, 'MapIndex') == struct.unpack_from('<H', mi)[0]), {})
    acct = {ss.get('uid'): ss.get('acct') for cc, ss in PLAYERS}; ss_ = seats(); rows = b''
    for u in ss_:
        k, d, a = (KD.get(u, []) + [0, 0, 0])[:3]; t = gteam(u) + 1; res = 'Draw' if win == 0 else 'Win' if win == t else 'Lose'
        xp = min(int(os.environ.get('REWARD_BASE', '30')) + 10 * k + 3 * a + {'Win': 50, 'Draw': 25, 'Lose': 10}[res], 65535); pt = min(2 * xp, 65535)
        item = roll(ival(m, 'WinRewardItem' if res == 'Win' else res + 'RewardIndex'))
        if acct.get(u):  # unknown account -> no reward (never credit another player)
            try: grant(acct[u], xp, pt, item)
            except Exception as e: log('grant', acct[u], e)
        rows += B(u) + H(xp) + H(pt) + I(item)
    return varint(len(ss_)) + rows
def char_note(name):  # NotifyCharacter 30157: wstr nick, i64, u8 level, i32 level, i32 exp, 6 x i32 PvP, 4 x i32 PvE, 5 x i32 hit
    if not F('FIX_REWARD'): return wstr(name) + bytes(8) + B(1) + bytes(4 * (2 + 6 + 4 + 5))
    e = prog(name)['exp']; return wstr(name) + bytes(8) + B(lvl(name)) + I(level_of(e)) + I(min(e, 2**31 - 1)) + bytes(4 * (6 + 4 + 5))

# ---- FIX_FRIENDS: 41001 login lists, 41002 ask [wstr], 41003 accept / 41004 reject / 41005 delete / 41006 invite [u16 id]; ids = stable per-account number, lists in fr_<name>
@locked
def acct_id(name):  # ids are claimed with O_EXCL (unique across processes), u16 on the wire
    v = kv_get('aid_' + name)
    if not v:
        n = int(kv_get('aid_next') or 0) + 1
        while not kv_claim(f'aname_{n}', name): n += 1
        if n > 65535: kv_del(f'aname_{n}'); raise ValueError('account ids exhausted')
        kv_set('aid_next', str(n))
        if kv_claim('aid_' + name, str(n)): v = str(n)
        else: kv_del(f'aname_{n}'); v = kv_get('aid_' + name)  # another process registered this name meanwhile
    return int(v)
def canon(name):  # registered spelling of a case-variant name ('bob' -> 'Bob'); state keys are case-insensitive
    v = kv_get('aid_' + name) if NAME_RE.fullmatch(name or '') else ''
    return (kv_get('aname_' + v) or name) if v else name
def guest(name): return name == 'BOT' or bool(re.fullmatch(r'Player\d*', name or ''))  # shared fallback / bot sessions: no clan actions
def fr(name):
    return {'f': [], 'r': [], **kv_json('fr_' + name)}
def fr_set(name, d): kv_set('fr_' + name, json.dumps(d))
def online(name): return [(cc, ss) for cc, ss in SESS if ss.get('name', '').lower() == name.lower() and cc.fileno() != -1]
def friend_row(name):  # Friend::Info [u16 id][wstr name][wstr clan][4 x u16 mark][u8 isClan][u8 level][u8 channel][u8 lobby][u16 room][u8 online][u8 inGame]
    on = online(name); rno = next((ss['room'] for cc, ss in on if ss.get('room') in ROOMS), 0)
    return H(acct_id(name)) + wstr(name) + wstr('') + H(0) * 4 + B(0) + B(lvl(name)) + B(1 if on else 0) + B(1 if on and not rno else 0) + H(rno) + B(1 if on else 0) + B(1 if rno and ROOMS[rno].get('started') else 0)
def req_row(name): return H(acct_id(name)) + wstr(name) + B(lvl(name))  # Friend::Request [u16 id][wstr name][u8 level]
def push(name, rid, body=b""):
    for cc, ss in online(name):
        try: rmi(cc, ss, rid, body)
        except OSError: pass
@locked
def friends(c, st, rid, args):
    me = canon(st.get('name', 'Player')); acct_id(me); f = fr(me)
    if rid == 41001:  # login -> Answer + SendFriendList 41053 + SendRequestFriendList 41054
        rmi(c, st, 41051); rmi(c, st, 41053, varint(len(f['f'])) + b''.join(friend_row(n) for n in f['f'])); return rmi(c, st, 41054, varint(len(f['r'])) + b''.join(req_row(n) for n in f['r']))
    if rid == 41002:  # ask -> 41055 / 41056 [u32]; target gets SendRequestFriendInfo 41057
        try: to = canon(rd_wstr(args, 0)[0])
        except Exception: to = ''
        if not NAME_RE.fullmatch(to) or to == me or to == 'BOT' or re.fullmatch(r'Player\d*', to) or to in f['f'] or not (kv_get('aid_' + to) or online(to)): return rmi(c, st, 41056, I(0))
        t = fr(to)
        if to in f['r']:  # they already asked me -> mutual request = friends
            f['r'].remove(to); f['f'].append(to); t['f'] += [me] * (me not in t['f']); t['r'] = [n for n in t['r'] if n != me]; fr_set(to, t); fr_set(me, f)
            rmi(c, st, 41055); rmi(c, st, 41060, friend_row(to)); return push(to, 41060, friend_row(me))
        if me not in t['r']: t['r'].append(me); fr_set(to, t)
        rmi(c, st, 41055); return push(to, 41057, req_row(me))
    i = struct.unpack_from('<H', args)[0] if len(args) >= 2 else 0; who = kv_get(f'aname_{i}') if i else ''
    if rid in (41003, 41004):  # accept -> 41058 [u16] + SendFriendInfo 41060 both ways / reject -> 41061 [u16]; fail +1 [u32]
        ok_ = {41003: 41058, 41004: 41061}[rid]
        if not who or who not in f['r']: return rmi(c, st, ok_ + 1, I(0))
        f['r'].remove(who)
        if rid == 41003:
            t = fr(who); f['f'] += [who] * (who not in f['f']); t['f'] += [me] * (me not in t['f']); t['r'] = [n for n in t['r'] if n != me]; fr_set(who, t)
        fr_set(me, f); rmi(c, st, ok_, H(i))
        if rid == 41003: rmi(c, st, 41060, friend_row(who)); push(who, 41060, friend_row(me))
    elif rid == 41005:  # delete -> 41063 [u16]; other side gets SendDeleteFriend 41065 [u16 my id]
        if not who or who not in f['f']: return rmi(c, st, 41064, I(0))
        f['f'].remove(who); fr_set(me, f); t = fr(who); t['f'] = [n for n in t['f'] if n != me]; fr_set(who, t)
        rmi(c, st, 41063, H(i)); push(who, 41065, H(acct_id(me)))
    elif rid == 41006:  # invite to my room -> 41066 [u16]; friend gets SendInviteRoom 41068 [u16 inviter][Room::Invite: u16 no, u8 kind, mapinfo5, wstr title, u8 popup 1, u8 0]
        r = ROOMS.get(st.get('room'))
        if not who or who not in f['f'] or not r or not online(who): return rmi(c, st, 41067, I(0))
        rmi(c, st, 41066, H(i)); push(who, 41068, H(acct_id(me)) + H(st['room']) + B(0) + bytes(r['mapinfo'][:5]) + wstr(r.get('title', '')) + B(1) + B(0))

def chat(c, st, rid, args):  # 38001 all / 38002 clan [wstr text][u8 flag], 38003 whisper [wstr to][wstr text][u8] -> 38106/38108/38110 (fail +1 [u32]); NotifyChat 38101 [wstr speaker][wstr text][u8 type 0][u8 flag]
    ok = rid * 2 - 37896  # 38001->38106, 38002->38108, 38003->38110
    to, i = rd_wstr(args, 0) if rid == 38003 else ('', 0)
    text, i = rd_wstr(args, i); text = text.strip()[:200]; flag = args[i] if i < len(args) else 0
    if rid == 38003:
        tgt = [x for x in SESS if x[0].fileno() != -1 and not x[1].get('dead') and x[1].get('name', '').lower() == to.strip().lower()]
        dest = tgt[:1] + ([(c, st)] if tgt and tgt[0][0] is not c else [])  # whisper: target + echo to sender
    elif rid == 38002 and F('FIX_CLAN') and (d := clan_of(st.get('name', ''))): dest = [x for m in d['m'] for x in online(m['n'])]  # clan chat -> online members
    else: dest = chat_scope(c, st) if rid == 38001 else [(c, st)]  # no clan: clan chat only echoes
    if not text or not dest: rmi(c, st, ok + 1, I(0)); return
    log(f"chat {rid} {st.get('name')} -> {to or len(dest)}: {text}")
    rmi(c, st, ok)
    row = wstr(st.get('name', 'Player')) + wstr(text) + B(0) + B(flag)
    for cc, ss in dest:
        try: rmi(cc, ss, 38101, row)
        except OSError: pass
# ---- FIX_CLAN: ClanC2S 42001.. -> ClanS2C 42501.. (ids / layouts: rmi_map.txt + ran-j protocol notes). State: clan_<id> {'id','name','mark':[4 x u16],'m':[{'n','r'}],'a':[{'n','d'}],'t':[y,m,d]},
# uclan_<acct> = clan id, uapp_<acct> = clan id of the pending application, clanname_<lower name> = id (unique), clan_next. Member / applicant id = acct_id. Ranks: 1 master, 2 manager, 8 member, 9 associate.
CLAN_NAME = re.compile(r'[\w -]{2,16}'); CLAN_CAP = 50; APP_CAP = 50
CLAN_FAIL = {42004: 42523, 42005: 42525, 42006: 42527, 42007: 42529, 42008: 42531, 42009: 42533, 42014: 42546, 42015: 42548, 42016: 42550, 42017: 42552, 42018: 42554, 42019: 42556, 42020: 42558, 42021: 42560, 42023: 42574, 42025: 42580, 42026: 42582, 42010: 42536, 42011: 42539, 42012: 42543, 42022: 42564}
def clan_get(cid): return kv_json(f'clan_{cid}') if str(cid).isdigit() else {}
def clan_set(d): kv_set(f"clan_{d['id']}", json.dumps(d))
def clan_of(name):  # the account's clan ({} = none); mapping and member list must agree
    d = clan_get(kv_get('uclan_' + name)); return d if d and any(m['n'] == name for m in d['m']) else {}
def clan_app(name):  # clan of the account's pending application ({} = none / stale)
    d = clan_get(kv_get('uapp_' + name)); return d if d and any(a['n'] == name for a in d['a']) else {}
def clans():
    for f in sorted(os.listdir(STATE)):
        if re.fullmatch(r'clan_\d+', f):
            try: d = clan_get(f[5:])
            except ValueError: continue  # corrupt file: skip in listings
            if d: yield d
def u32(v):
    try: return min(max(int(v), 0), 2**32 - 1)
    except (TypeError, ValueError): return 0
def rec_of(name):
    try: return json.loads(kv_get('rec_' + name) or '{}')
    except ValueError: return {}
def pvp6(name): r = rec_of(name); return struct.pack('<6I', *(u32(r.get(k)) for k in ('win', 'lose', 'draw', 'kill', 'death')), 0)  # win, lose, draw, kill, death, extra
def clan_master(d): return next((m['n'] for m in d['m'] if m['r'] == 1), '')
def clan_counts(d): rs = [m['r'] for m in d['m']]; n = min(len(rs), 255); return bytes([n, rs.count(2), rs.count(8), rs.count(9), max(CLAN_CAP, n)])  # [total][managers][members][associates][capacity]
def clan_mark(d): return b''.join(H(v & 0xFFFF) for v in d['mark'])  # Clan::Mark 4 x u16
def clan_info(d):  # Clan::Info [u32 id][wstr name][wstr master][u8 0][u8 level][u64 score][6 x u32 win/draw/lose/kill/death/0][u8 0][mark][u8 0][counts 5][wstr notice][wstr intro][u16 y][u8 m][u8 d]
    y, mo, dd = d['t']; return struct.pack('<I', d['id']) + wstr(d['name']) + wstr(clan_master(d)) + B(0) + B(1) + bytes(8) + bytes(24) + B(0) + clan_mark(d) + B(0) + clan_counts(d) + wstr('') + wstr('') + H(y) + B(mo) + B(dd)
def clan_member(m):  # Clan::Member [u16 id][wstr name][u8 level][6 x u32 PvP][6 x u32 clan record][u8 channel][u8 lobby][u16 room][u8 position][u8 online][u8 inGame]
    n = m['n']; on = online(n); rno = next((ss['room'] for cc, ss in on if ss.get('room') in ROOMS), 0)
    return H(acct_id(n)) + wstr(n) + B(lvl(n)) + pvp6(n) + bytes(24) + B(1 if on else 0) + B(1 if on and not rno else 0) + H(rno) + B(m['r']) + B(1 if on else 0) + B(1 if rno and ROOMS[rno].get('started') else 0)
def clan_req(a): y, mo, dd = a['d']; return H(acct_id(a['n'])) + wstr(a['n']) + B(lvl(a['n'])) + pvp6(a['n']) + H(y) + B(mo) + B(dd)  # Clan::Request [u16 id][wstr name][u8 level][6 x u32 PvP][u16 y][u8 m][u8 d]
def clan_reqinfo(d): m = d['mark']; return wstr(d['name']) + struct.pack('<II', d['id'], (m[0] & 0xFFFF) | (m[1] & 0xFF) << 16 | (m[2] & 0xFF) << 24)  # SendRequestClanInfo [wstr name][u32 id][u32 packed mark]
def clan_list(ds): ds = list(ds)[:50]; return varint(len(ds)) + b''.join(clan_info(d) for d in ds)
def clan_bcast(d, rid, body=b'', skip=''):
    for m in d['m']:
        if m['n'] != skip: push(m['n'], rid, body)
def clan_welcome(name, d):  # full clan state for one account (login / created / accepted)
    push(name, 42507, clan_info(d)); push(name, 42511, varint(len(d['m'])) + b''.join(clan_member(m) for m in d['m'])); push(name, 42562, clan_counts(d))
    push(name, 41076, H(acct_id(name)) + wstr(d['name']) + clan_mark(d))  # NotifyUserClanInfo [u16 user][wstr clan][mark]
    if clan_master(d) == name and d['a']: push(name, 42518, varint(len(d['a'])) + b''.join(clan_req(a) for a in d['a']))  # SendRequestList
def clan_depart(d, name):  # name already removed from d: others drop the row, the leaver clears the clan screen
    clan_bcast(d, 42516, H(acct_id(name))); clan_bcast(d, 42562, clan_counts(d)); kv_del('uclan_' + name); push(name, 42517); push(name, 42508)
def clan_disband(d, answer):  # remove the clan file first (retried; raises -> caller answers Failed), then answer + clean up
    kv_del(f"clan_{d['id']}"); kv_del('clanname_' + d['name'].lower()); answer()
    for m in d['m']: kv_del('uclan_' + m['n']); push(m['n'], 42517); push(m['n'], 42508)
    for a in d['a']:
        if kv_get('uapp_' + a['n']) == str(d['id']): kv_del('uapp_' + a['n']); push(a['n'], 42510)
def clan_presence(name):  # online / offline change -> other members get the refreshed row (NotifyMemberInfo)
    d = clan_of(name)
    if d: clan_bcast(d, 42512, clan_member(next(m for m in d['m'] if m['n'] == name)), skip=name)
def clan(c, st, rid, args):
    fail = CLAN_FAIL.get(rid); st['sent'] = []
    try:
        with xlock(): r = clan_do(c, st, rid, args, canon(st.get('name', 'Player')))
    except Exception as e: log(f'clan {rid} error: {e!r}'); r = False
    if r is False and fail and fail - 1 not in st.get('sent', ()): rmi(c, st, fail, I(0))  # no Failed after the Success went out
def clan_do(c, st, rid, args, me):  # returns False -> caller answers the matching ...Failed [u32 0]
    today = list(time.gmtime()[:3])
    def text(): return rd_wstr(args, 0)[0].strip()
    def who(): return kv_get(f'aname_{struct.unpack_from("<H", args)[0]}') if len(args) >= 2 else ''  # [u16 member / applicant id] -> account
    if rid == 42001:  # clan login -> AnswerLoginSuccess + my clan (info, members, counts, user clan info, master: requests) or my pending application
        rmi(c, st, 42501); st['clan_login'] = 1; d = {} if guest(me) else clan_of(me)
        if d: clan_welcome(me, d); clan_presence(me)
        elif not guest(me) and (p := clan_app(me)): rmi(c, st, 42509, clan_reqinfo(p))
        return
    if guest(me) and rid in CLAN_FAIL and rid not in (42004, 42005, 42006, 42025): return False  # shared 'Player' / BOT sessions can't own clan state
    if rid == 42002: return rmi(c, st, 42503)  # open clan screen
    if rid == 42003: return rmi(c, st, 42505)  # close clan screen
    if rid in (42004, 42005):  # search by clan name / master name [wstr] ('' = all, max 50) -> varint n + Clan::Info rows
        q = text().lower()
        if len(q) > 16 or not re.fullmatch(r'[\w -]*', q): return False
        return rmi(c, st, 42522 if rid == 42004 else 42524, clan_list(d for d in clans() if q in (d['name'] if rid == 42004 else clan_master(d)).lower()))
    if rid == 42006:  # check name [wstr]
        n = text(); return rmi(c, st, 42526) if CLAN_NAME.fullmatch(n) and not kv_get('clanname_' + n.lower()) else False
    if rid == 42025:  # check mark [4 x u16] -> [u8 free]
        if len(args) < 8: return False
        mk = list(struct.unpack_from('<4H', args)); mine = clan_of(me).get('id')
        return rmi(c, st, 42579, B(0 if any(d['mark'][:3] == mk[:3] and d['id'] != mine for d in clans()) else 1))
    if rid == 42007:  # create [4 x u16 mark][wstr name] (no cost, like the reference server) -> 42528 + clan state
        if len(args) < 9: return False
        mk = list(struct.unpack_from('<4H', args)); n = rd_wstr(args, 8)[0].strip()
        if not CLAN_NAME.fullmatch(n) or kv_get('clanname_' + n.lower()) or clan_of(me) or clan_app(me) or any(x['mark'][:3] == mk[:3] for x in clans()): return False
        cid = int(kv_get('clan_next') or 0) + 1; d = {'id': cid, 'name': n, 'mark': mk, 'm': [{'n': me, 'r': 1}], 'a': [], 't': today}
        while not kv_claim(f'clan_{cid}', json.dumps({**d, 'id': cid})): cid += 1  # O_EXCL: ids / names unique across processes
        d['id'] = cid; kv_set('clan_next', str(cid))
        if not kv_claim('clanname_' + n.lower(), str(cid)): kv_del(f'clan_{cid}'); return False
        kv_set('uclan_' + me, str(cid)); log(f'clan created {n} ({cid}) by {me}')
        rmi(c, st, 42528); return clan_welcome(me, d)
    if rid == 42014:  # join request [wstr clan name] -> 42545 + SendRequestClanInfo; master gets NotifyRequestInfo
        n = text(); d = clan_get(kv_get('clanname_' + n.lower())) if CLAN_NAME.fullmatch(n) else {}
        if not d or clan_of(me) or len(d['m']) >= CLAN_CAP or clan_app(me).get('id', d['id']) != d['id'] or (len(d['a']) >= APP_CAP and not any(a['n'] == me for a in d['a'])): return False
        if not any(a['n'] == me for a in d['a']): d['a'].append({'n': me, 'd': today}); clan_set(d); kv_set('uapp_' + me, str(d['id'])); push(clan_master(d), 42519, clan_req(d['a'][-1]))
        rmi(c, st, 42545); return rmi(c, st, 42509, clan_reqinfo(d))
    if rid == 42015:  # cancel my application -> 42547 + SendClearRequestInfo; master gets NotifyDeleteRequest [u16]
        d = clan_app(me)
        if not d: return False
        d['a'] = [a for a in d['a'] if a['n'] != me]; clan_set(d); kv_del('uapp_' + me)
        rmi(c, st, 42547); rmi(c, st, 42510); return push(clan_master(d), 42520, H(acct_id(me)))
    if rid == 42023:  # clan chat [wstr text] -> 42573; members get NotifyClanChat [wstr speaker][wstr text]
        t = text()[:200]; d = clan_of(me)
        if not t or not d: return False
        log(f'clan chat [{d["name"]}] {me}: {t}'); rmi(c, st, 42573); return clan_bcast(d, 42575, wstr(me) + wstr(t))
    if rid == 42019:  # leave -> 42555; the master may only leave alone (= disband)
        d = clan_of(me)
        if not d or (clan_master(d) == me and len(d['m']) > 1): return False
        if len(d['m']) == 1: return clan_disband(d, lambda: rmi(c, st, 42555))
        d['m'] = [m for m in d['m'] if m['n'] != me]; clan_set(d); rmi(c, st, 42555); return clan_depart(d, me)
    if rid in (42008, 42016, 42017, 42018, 42020):  # master only: disband, accept, reject, kick, hand over
        d = clan_of(me)
        if not d or clan_master(d) != me: return False
        if rid == 42008: log(f'clan disbanded {d["name"]} by {me}'); return clan_disband(d, lambda: rmi(c, st, 42530))
        w = who(); i = acct_id(w) if w else 0
        if rid in (42016, 42017):  # accept / reject applicant [u16] -> 42549 / 42551 + NotifyDeleteRequest; applicant gets SendClearRequestInfo
            if not any(a['n'] == w for a in d['a']) or (rid == 42016 and len(d['m']) >= CLAN_CAP): return False
            d['a'] = [a for a in d['a'] if a['n'] != w]
            if rid == 42016 and clan_of(w): clan_set(d); rmi(c, st, 42520, H(i)); return False  # joined / founded another clan meanwhile: drop the stale request (master's row too)
            if kv_get('uapp_' + w) == str(d['id']): kv_del('uapp_' + w)
            if rid == 42016: d['m'].append({'n': w, 'r': 8}); kv_set('uclan_' + w, str(d['id']))
            clan_set(d); rmi(c, st, 42549 if rid == 42016 else 42551); rmi(c, st, 42520, H(i)); push(w, 42510)
            if rid == 42016: clan_bcast(d, 42512, clan_member(d['m'][-1]), skip=w); clan_bcast(d, 42562, clan_counts(d), skip=w); clan_welcome(w, d)
            return
        t = next((m for m in d['m'] if m['n'] == w), None)
        if not t or w == me: return False
        if rid == 42018: d['m'].remove(t); clan_set(d); rmi(c, st, 42553); return clan_depart(d, w)  # kick [u16 member]
        t['r'] = 1; next(m for m in d['m'] if m['n'] == me)['r'] = 2; clan_set(d); rmi(c, st, 42557)  # hand over [u16 member] -> NotifyMemberPosition [u16 id][u32 rank] x 2
        clan_bcast(d, 42561, H(i) + struct.pack('<I', 1)); clan_bcast(d, 42561, H(acct_id(me)) + struct.pack('<I', 2)); return clan_bcast(d, 42562, clan_counts(d))
    return False if rid in CLAN_FAIL else None  # change name / position / mark: unsupported -> Failed; others (e.g. 42024 login clan record) unanswered as before

def on_rmi(c, st, rid, args):
    log(f"<- RMI {rid} {NAMES.get(rid, '?')} {args.hex()}")
    ANS = sorted(k for k, n in NAMES.items() if 37426 <= k < 37500 and n.startswith('Answer') and n.endswith('Success'))  # Request 37001+k -> k-th AnswerXSuccess
    if GAME and 37001 <= rid < 37001 + len(ANS) and rid != 37009 and not (F('FIX_DEATH') and rid in (37007, 37008, 37018, 37021)): rmi(c, st, ANS[rid - 37001])  # FIX_DEATH: those get real answers below (37018 no longer gets an empty 37467 first)
    if GAME and F('FIX_DEATH') and rid in (37007, 37008): rmi(c, st, 37438 if rid == 37007 else 37440, B(uid(st)))  # CheckRespawn(Instant) answers carry u8 seat
    if GAME and F('FIX_DEATH') and rid == 37021:  # RequestUserEquip(u8 seat): AnswerUserEquipSuccess(u8) + NotifyUserEquipInfo (one 37411 row)
        k = args[0] if args else uid(st)
        rmi(c, st, 37475, B(k)); rmi(c, st, 37412, B(k) + b''.join(I(x) for x in equip_of(pname(k + 1))))
    if GAME and rid == 37001 and len(args) >= 7 and 'acct' not in st:  # RequestJoin echoes NotifyGameStart's tail (u16, i32, u8 room slot idx) -> remember which account this game connection is
        st['gidx'] = args[6] + int(os.environ.get('GIDX0', '1')); st['acct'] = acct_of(st['gidx'])  # '' = unknown: no rewards / records / loadout saves
        log(f"game join uid {uid(st)} gidx {st['gidx']} acct {st['acct']}")
    if GAME and rid == 37004:  # client finished loading -> tell everyone loaded, begin round (payloads guessed)
        if uid(st) == 1 or (os.environ.get('DEDI') == '1' and kv_get(f'botready{GROOM}') != '1'): kv_set(f'botready{GROOM}', '1')  # dedicated: players are held until botready, so the first loader is the (re)launched bot (its uid can be >1 while the killed bot's socket lingers)
        rmi(c, st, 37424, L24(uid(st)))
        if F('FIX_LOAD'): load_done(c, st)  # 37425 once, after every player in the match loaded
        else: rmi(c, st, 37425)
        rmi(c, st, 37418, B(1)); rmi(c, st, 37415, B(uid(st)) + B(myteam(st) if F('FIX_TEAMS') and F('FIX_TEAMS_RB') else 0) + B(0) + B(0) + H(0))  # RoundBegin u8 (reader 0x100204d0)
        if uid(st) > 1:  # joiner never sends 37009 itself -> tell everyone (host spawns it) after it joined the LithTech host
            def _jr(u=uid(st)):
                for cc, ss in PLAYERS:
                    for v in (u - 1, u):
                        if v == 1 and (os.environ.get('DEDI') == '1'): continue  # never spawn the bot host's player
                        try: rmi(cc, ss, 37424, L24(v)); rmi(cc, ss, 37444, B(v))
                        except Exception: pass
            for d in ((3, 6, 9, 13, 18) if F('FIX_SPAWN') else (3, 6)): threading.Timer(d, _jr).start()
            st['spawn_t'] = time.time() + 6
        else:  # round-based modes (Demolition...) never send RequestRespawn: spawn the host ourselves if it hasn't asked within 3s
            def _ar(c=c, st=st):
                if st.get('respawned') or c.fileno() == -1: return
                log('auto-respawn (no 37009)'); on_rmi(c, st, 37009, bytes(1))
            threading.Timer(3, _ar).start()
    if GAME and rid == 37010 and uid(st) == 1:  # host's round timer expired -> end match for everyone
        kv_set(f'botready{GROOM}', '0')
        if os.environ.get('NOREHOST') == '1': threading.Timer(6, lambda: kv_set(f'botready{GROOM}', '1')).start()  # host reloads the level by itself; players may rejoin shortly after
        end_match()
    if GAME and rid == 37011: log(f'death from uid {uid(st)} gidx {st.get("gidx")}')
    if GAME and rid in (37011, 37018, 37007, 37008): st['played'] = 1  # player is in the world: stop FIX_SPAWN resends
    if GAME and rid == 37011:  # RequestDeath (payload logged) -> AnswerDeathSuccess + NotifyDeath(args echoed) to all
        killer, victim = (args[0], args[1]) if len(args) >= 2 else (0, 0)  # guess: (killer, victim, ?, i32 weapon, u8 x3)
        inm = {ss.get('uid') for _, ss in PLAYERS} | {uid(st)}
        if F('FIX_DEATH') and (victim not in inm or (killer and killer not in inm)): log(f'37011 ignored: ids {killer}/{victim} not in match'); return
        KD.setdefault(victim, [0, 0, 0])[1] += 1
        if len(args) >= 3 and args[2] in inm and args[2] not in (killer, victim): KD.setdefault(args[2], [0, 0, 0])[2] += 1  # assist (request: killer, victim, assist, u32, 3 x u8)
        mi_ = bytes.fromhex(kv_get(f"map{GROOM}") or '00000000') + bytes(1); ffa = mode_of(mi_) in FFA_MODES
        if killer and killer != victim and (ffa or gteam(killer) != gteam(victim)):  # world/fall deaths (killer 0) and team kills don't score
            KD.setdefault(killer, [0, 0, 0])[0] += 1
            if not ffa: TEAM[gteam(killer)] = TEAM.get(gteam(killer), 0) + 1
        for cc, ss in (PLAYERS or [(c, st)]):
            try:
                rmi(cc, ss, 37449, args[:3] + args[7:10] if F('FIX_DEATH') and len(args) >= 10 else args)  # NotifyDeath: [killer][victim][assist][b7][b8][b9] (old: whole request echoed)
                for u_, (k_, d_, *_) in KD.items():  # NotifyGameScore: GameScore{u8 user, u8 team 1/2, u8 kill, u8 death, u16 score} (ZNetwork 0x100cd7a0)
                    rmi(cc, ss, 37415, B(u_) + B(gteam(u_) + 1 if F('FIX_TEAMS') else 0) + B(min(k_, 255)) + B(min(d_, 255)) + H(k_ * 100))
                for t_, v_ in TEAM.items(): rmi(cc, ss, 37417, B(t_) + B(min(v_, 255)))  # NotifyTeamScore(u8 team: 0=blue, u8 score) VERIFIED on HUD
            except OSError: pass
        goal = mi_[4] if mode_of(mi_) in KILL_MODES else 0  # room kill goal (kill modes; host's copy carries the time instead)
        best = max([v_[0] for v_ in KD.values()] if ffa else TEAM.values(), default=0)  # FFA: per player, else per team
        if goal and best >= goal and kv_get(f'goalend{GROOM}') != (kv_get(f'mcount{GROOM}') or '0'):  # '0': fresh state has no mcount yet
            log('kill goal', goal, 'reached -> end match'); kv_set(f'goalend{GROOM}', kv_get(f'mcount{GROOM}') or '0'); kv_set(f'botready{GROOM}', '0'); threading.Timer(3, end_match).start()
    if GAME and rid == 37009 and (os.environ.get('DEDI') == '1') and uid(st) == 1:
        return  # dedicated bot host: never spawn its own player (stays invisible spectator)
    if GAME and rid == 37009: st['respawned'] = 1; st['spawn_t'] = time.time()
    if GAME and rid == 37009:  # RequestRespawn -> AnswerRespawnSuccess(u8) + NotifyRespawn(u8 user idx) to all
        rmi(c, st, 37442, B(uid(st))); [rmi(c, st, 37424, L24(u)) for u in (0, uid(st))]  # re-send user-load so host spawns (player obj exists now)
        for cc, ss in (PLAYERS or [(c, st)]):
            try: rmi(cc, ss, 37444, B(uid(st)))
            except OSError: pass
        if F('FIX_SPAWN'):  # host only spawns if the player object already exists when 37424 lands (race, ~50% floor-camera/AP 0): resend for a while
            mc0, u0 = kv_get(f'mcount{GROOM}'), uid(st)
            def _rs(d, c=c, st=st):
                if c.fileno() == -1 or st.get('played') or kv_get(f'mcount{GROOM}') != mc0: return
                log(f'spawn resend uid {u0} +{d}s')
                for cc, ss in (PLAYERS or [(c, st)]):
                    try: rmi(cc, ss, 37424, L24(u0)); rmi(cc, ss, 37444, B(u0))
                    except Exception: pass
            for d in (1, 2, 4, 7, 12): threading.Timer(d, _rs, (d,)).start()
        if F('FIX_ROUNDBEGIN') and uid(st) == 1:  # RE: only BeginRound (37418) spawns the host's player; lost if it lands before the player enters the world -> resend later
            mc1 = kv_get(f'mcount{GROOM}')
            def _rb(d, c=c, st=st):
                if c.fileno() == -1 or kv_get(f'mcount{GROOM}') != mc1: return
                log(f'round-begin resend +{d}s'); rmi(c, st, 37418, B(1))
            for d in (1.5, 4): threading.Timer(d, _rb, (d,)).start()
    if GAME and not st.get('gs'):  # game server: push match start on first RMI
        st['gs'] = 1
        me = uid(st); PLAYERS.append((c, st)); ids = [x[1]['uid'] for x in PLAYERS]
        for cc, ss in PLAYERS:  # (re)send full user + equip lists to everyone (reader 0x100cd050 / 0x100cd420)
            try:
                ks = list(range(1, len(ids) + 2))  # keys 0..n: joiner's 36951 idx may be 1-based
                rmi(cc, ss, 37405, varint(len(ks)) + b''.join(user_elem(i) for i in ks))
                rmi(cc, ss, 37411, varint(len(ks) + 1) + b''.join(B(k) + b''.join(I(x) for x in equip_of(pname(k + 1))) for k in ks + [0]))  # keys 1..n then 0 LAST: ZNetwork FUN_100a63a0 matches key first (empty slots have key 0, flag not set) so key 0 must not be written first or a later key overwrites it
            except Exception as e: log('push err', e)
        rmi(c, st, 37401, host_map(bytes.fromhex(kv_get(f"map{GROOM}") or '0302100164'), GROOM, me == 1) + B(0))
        if F('FIX_TEAMS') and os.environ.get('FIX_TEAMINFO') == '1': rmi(c, st, 37402, B(me - SEAT0) + B(1 - SEAT0) + B(myteam(st) - TEAM0) * 2)  # OFF by default: any 37402 to the listen host = floor-camera spawn every match (bisected 10/25). NotifyInfo: my seat, leader (host) seat, my team 1/2 (x2)
        rmi(c, st, 37404, wstr(HOST_IP or ip_for(c)) + H(hport(GROOM)) + host_tail(me == 1, int(kv_get(f"intrude{GROOM}_{st.get('gidx')}") or 0)))  # flag0 = you host
    if rid == 30001:  # RequestFirstLogon(wstr id, wstr pw) -> remember account name
        try: n = args[0]; st['name'] = clean_name(bytes(args[1:1 + 2 * n]).decode('utf-16le'))  # [\w -]{1,16}: names become state file names
        except Exception: st['name'] = 'Player'
        sn = kv_get(f"peer_{st.get('port')}") or (kv_get("peer_self") if SELF.setdefault('id', st['name']) == st['name'] else '')  # host's Steam name only for the first login ID seen; other (LAN/tunnel) joiners keep their typed ID  # Steam persona name written by FearLink (joiner / host)
        if sn: st['name'] = clean_name(sn)
        rmi(c, st, 30051)  # RequestFirstLogon -> AnswerFirstLogonSuccess
    elif rid == 30101:  # RequestLogin -> AnswerLoginSuccess + NotifyCharacter(wstr nick, i64, u8, 2xi32, 6xi32 PvPRecord, 4xi32, 5xi32) so the game knows our name
        rmi(c, st, 30151)
        if os.environ.get('NOCHAR') != '1': rmi(c, st, 30157, char_note(st.get('name', 'Player')))  # FIX_REWARD: saved level / exp
    elif rid == 30002:
        rmi(c, st, 35103, varint(1) + channel(1, os.environ.get("CHAN_NAME", "Z_Beginner"), ip_for(c), GAME_PORT)); rmi(c, st, 35101)  # SendChannelList + AnswerChannelListSuccess
        st["cred"] = os.urandom(16); kv_set("cred_" + st["cred"].hex(), st.get('name', 'Player')); rmi(c, st, 30053, st["cred"])  # credential GUID
    elif rid == 30003:  # CheckCredential(guid) on channel server -> recover account name
        st['name'] = kv_get("cred_" + bytes(args[:16]).hex(), 'Player'); rmi(c, st, 30055)
        for cc, ss in [x for x in SESS if x[0] is not c and x[1].get('name') == st['name'] and time.time() - x[1].get('last', 0) > 40]:  # same account logged in again: the old session is a ghost the Steam tunnel kept open (only if silent; a live player sharing the account with the dedicated bot pings every ~18s)
            ss['dead'] = True; log("closing stale session of", st['name'])
            try: cc.shutdown(socket.SHUT_RDWR); cc.close()
            except OSError: pass
        SESS[:] = [x for x in SESS if not x[1].get('dead')] + [(c, st)]; prune_rooms()
        # SendItemList (Item::Info reader ZNetwork 0x100c4260: u16, i32 ItemIndex, i32 count, u8,u8,u8,u8): PVE ticket (Operation Plan) so scenario/PVE modes start
        # item.+0x24 = count, last byte (+0x4c) = kind; kind 0x11 -> ScenarioTicket count (ZNetwork FUN_10029950)
        rmi(c, st, 30255, struct.pack('<q', MONEY)); rmi(c, st, 30355, struct.pack('<q', MONEY))  # SendPoint / SendCash (i64) so the store can buy
        # inventory = every GameItem (server/items.txt: index,category; category = HighGroup*10+MiddleGroup = slot type, ZNetwork 0x10029590) + PVE ticket
        inv = [(1, 43510701, int(os.environ.get('TICKETS', '99')), 0x2b, 0x11)] + [(n + 2, x, 1, cat, 0) for n, (x, cat) in enumerate(ITEMS)]  # (serial, ItemIndex, count, type, function)
        fs = F('FIX_STORE'); d = inv_of(st.get('name', 'Player')) if fs else {'x': [], 'm': []}
        if fs: inv = [(s, x, cnt, cat, ifunc(x) or kind) for s, x, cnt, cat, kind in inv] + [tuple(e) + (ifunc(e[1]),) for e in d['x']]  # + saved purchases / crafts / rewards
        st['inv'] = {s: (x, cat) for s, x, cnt, cat, kind in inv}; st['byidx'] = {}
        for s, x, cnt, cat, kind in inv: st['byidx'].setdefault(x, s)
        rmi(c, st, 30455, varint(len(inv)) + b''.join(H(s) + I(x) + I(cnt) + (B(1) + B(0) if fs else B(0) + B(1)) + B(cat) + B(kind) for s, x, cnt, cat, kind in inv))  # FIX_STORE: [u8 state 1][u8 aux 0] (old: 0, 1)
        sl = slots_of(st.get('name', 'Player'))  # {slot type: ItemIndex}
        eq = [(st['byidx'][x], x, t) for t, x in sl.items() if x in st['byidx']]
        if fs:  # SendSlotList 30459: gear/perk mounts Item::Slot [u16 parent][u16 child][i32 item][u8 slot][u8 1]
            ms = [m for m in d['m'] if m[0] in st['inv'] and m[1] in st['inv']]
            rmi(c, st, 30459, varint(len([m for m in ms if not is_custom(m[2])])) + b''.join(H(p) + H(ch_) + I(st['inv'][ch_][0]) + B(t) + B(1) for p, ch_, t in ms if not is_custom(t)))
        else: rmi(c, st, 30465, varint(len(eq)) + b''.join(H(n) + H(0) + B(t) + B(1) for n, x, t in eq))  # old SendEquipList: weapon rows with parent 0
        rmi(c, st, 30463, varint(len(eq)) + b''.join(H(n) + I(x) + B(t) for n, x, t in eq))  # SendEquipSlotList: EquipSlot(u16 serial, i32 ItemIndex, u8 slot type) -> hangar MySlotHero/MySlotWeapon
        if fs: rmi(c, st, 30465, varint(len([m for m in ms if is_custom(m[2])])) + b''.join(H(ch_) + H(p) + B(t) + B(1) for p, ch_, t in ms if is_custom(t)))  # SendEquipList 30465 = custom parts only, Item::Equip [u16 child][u16 weapon][u8 slot][u8 1]
    elif rid == 36001:  # Room Create: wstr title, wstr pw, u16 map, u8 users, u8 ?, u8 goal, ...
        if os.environ.get('BOTRESTART') == '1' and SELF.get('bot') and (b := SELF.get('botc')) and (b[0].fileno() == -1 or b[1].get('dead')): SELF['bot'] = 0  # bot was killed (tools/dedi.py restarts it after each match): next creator is the fresh bot
        if os.environ.get('DEDI') == '1' and not SELF.get('bot'): SELF['bot'] = 1; st['name'] = 'BOT'; SELF['botc'] = (c, st)  # dedicated: the room creator is the hidden host bot (own name, so a player logging in on the same PC/account doesn't replace its session)
        n, i = read_varint(args, 0); i += 2 * n; n, i = read_varint(args, i); i += 2 * n
        n0, j = read_varint(args, 0); t = args[j:j + 2 * n0].decode('utf-16le')
        prune_rooms()  # abandoned rooms free their numbers (-> game ports, slot/team keys restart at 1)
        if os.environ.get('DEDI') == '1' and st.get('name') == 'BOT':  # restarted bot: rejoin the room whose bot (slot 1) died instead of opening a new one
            for r in ROOMS.values(): r['members'] = [m for m in r['members'] if m[0] is c or m[1].get('name') != 'BOT']  # old bot socket may still look alive -> drop it so the fresh bot always reuses the room (else it opens room 2 and players load a host-less match)
            for no, r in sorted(ROOMS.items()):
                log('bot rejoins room', no); rmi(c, st, 36114); room_enter(c, st, no); return
        if os.environ.get('DEDI') == '1' and st.get('name') != 'BOT':  # dedicated: players never open their own room -> put them in the bot's room (and its running match)
            for no, r in ROOMS.items():
                if any(ss.get('name') == 'BOT' and cc.fileno() != -1 and not ss.get('dead') for cc, ss in r['members']):
                    log('player redirected to bot room', no); rmi(c, st, 36114); room_enter(c, st, no)
                    if r['started']: st['intrude'] = 1; game_start(c, st)
                    return
        no = next(k for k in range(1, 999) if k not in ROOMS)
        mi = bytes.fromhex(os.environ['MAPINFO']) if os.environ.get('MAPINFO') else args[i:i + 5]
        if len(mi) >= 2 and struct.unpack_from('<H', mi)[0] in NOWORLD: log('room create refused: no world for map', struct.unpack_from('<H', mi)[0]); rmi(c, st, 36115, I(0)); return
        if os.environ.get('GOAL'): mi = mi[:4] + bytes([int(os.environ['GOAL'])])  # kill target override (testing)
        kv_set(f"time{no}", str(args[i + 5]) if len(args) > i + 5 and mi[4] and mode_of(mi) in KILL_MODES else '')  # kill modes: the Round byte carries the Time dropdown (minutes)
        ROOMS[no] = {'info': struct.pack('<H', no) + wstr(t) + wstr(st.get('name', 'Player')) + wstr("") + struct.pack('<i', 1) + args[i:i + 5] + bytes(ROOM_TAIL), 'mapinfo': mi, 'rawmi': bytes(args[i:i + 5]), 'max': (args[i + 2] if len(args) > i + 2 else 0) or 16, 'title': t, 'members': [], 'started': False}
        rmi(c, st, 36114)  # AnswerCreateSuccess
        room_enter(c, st, no)
    elif rid == 36002:  # Room Join: u16 room no, wstr pw (guess)
        prune_rooms()
        no = struct.unpack_from('<H', args, 0)[0] if len(args) >= 2 else 0
        if no not in ROOMS: no = next(iter(ROOMS), 0)
        if not no: rmi(c, st, 36117); return
        rmi(c, st, 36116)  # AnswerJoinSuccess
        room_enter(c, st, no)
        if ROOMS[no]['started']: st['intrude'] = 1; game_start(c, st)  # join match in progress (dedicated bot host)
    elif rid == 36003:  # Room Leave (BACK from room) -> AnswerLeaveSuccess; drop member, close room if empty
        r = ROOMS.get(st.get('room'))
        if r: r['members'] = [(cc, ss) for cc, ss in r['members'] if cc is not c]; r['gl'] = [x for x in r.get('gl', []) if x[0] is not c]; room_refresh(r)
        st.pop('room', None); st.pop('gidx', None); rmi(c, st, 36118); prune_rooms()
    elif rid in (36004, 36005) and st.get('room') in ROOMS:  # TeamChange (or Setting) -> flip team, refresh everyone in the room
        st['team'] = 1 - tm(st); rmi(c, st, 36122 if rid == 36005 else 36120)
        for cc, ss in ROOMS[st['room']]['members']:
            try: room_state(cc, ss, ROOMS[st['room']])
            except OSError: pass
    elif rid == 36006:  # RequestReady. Leader's READY stands in for START (the client never sends 36007) -> start everybody in the room
        r = ROOMS.get(st.get('room'))
        if F('FIX_ROOMUSER') and r and os.environ.get('DEDI') != '1':  # AnswerReadySuccess + NotifyStateInfo(u32 user, u8 0 wait/2 ready) to the room; only the leader starts
            live = [(cc, ss) for cc, ss in r['members'] if cc.fileno() != -1 and not ss.get('dead')]
            lead = st.get('gidx') == min([ss.get('gidx', 99) for _, ss in live] or [st.get('gidx')])  # leader = room user 1 (lowest live slot if 1 left)
            st['rstate'] = 2 if lead else (0 if st.get('rstate') == 2 else 2)
            rmi(c, st, 36124)
            for cc, ss in live:
                try: rmi(cc, ss, 36110, struct.pack('<I', st.get('gidx', 1)) + B(st['rstate']))
                except OSError: pass
            if not lead: return
            for _, ss in live: ss['rstate'] = 0  # back from the match everyone is waiting again
        rmi(c, st, 36126)  # AnswerGameStartSuccess
        if r and r['started'] and (os.environ.get('DEDI') == '1'):  # restarted bot in a running room: only the bot starts (players already wait on botready)
            if st.get('name') != 'BOT': log('player start -> join running bot match'); st['intrude'] = 1; game_start(c, st); return  # player clicked START/READY: join the bot's match (waits for botready)
            for cc, ss in [x for x in r['members'] if x[1].get('gidx') == 1]: game_start(cc, ss)
            return
        if r: r['started'] = True; kv_set(f"nplay{st.get('room', 1)}", str(len(r['members'])))  # game server: round modes wait for this many 37004 before 37425
        for cc, ss in (r['members'] if r else [(c, st)]):
            try: game_start(cc, ss)
            except OSError: pass
    elif rid in (35504, 35507) and not prune_rooms():  # RoomList / RefreshRoomList -> SendRoomList(CFastArray<Room::Info>) + answer
        rmi(c, st, 35610, varint(len(ROOMS)) + b''.join(room_info(r) for r in ROOMS.values()))
        rmi(c, st, 35608 if rid == 35504 else 35631)
    elif rid == 36903 and F('FIX_HITCOUNT'):  # RequestRoomGameLeave (player quits the match) -> AnswerLeaveSuccess
        rmi(c, st, 36953)
    elif rid == 36904:  # RequestHitCount(5 x u16), sent once back in the room after GameEnd -> used as our 'back from the match' signal
        rmi(c, st, 36955 if F('FIX_HITCOUNT') else 36953)  # AnswerHitCountSuccess (FIX_HITCOUNT=0: old AnswerLeaveSuccess); room-return side effects below are kept either way
        if os.environ.get('ROOMGAME0', '1') == '1': rmi(c, st, 36105, B(0))  # NotifyRoomGame off: room no longer in-game (else host client auto-reloads the level)
        r = ROOMS.get(st.get('room'))
        log(f"36904 gidx={st.get('gidx')} room={st.get('room')} r={'yes' if r else 'NONE'} name={st.get('name')}")
        if r: room_state(c, st, r)
        if F('FIX_REWARD') and os.environ.get('NOCHAR') != '1': rmi(c, st, 30157, char_note(st.get('name', 'Player')))  # back from the match: refresh level / exp in the lobby UI
        if r and (os.environ.get('DEDI') == '1') and not (st.get('gidx') == 1 and os.environ.get('BOTRESTART') == '1'):  # BOTRESTART: tools/dedi.py kills + relaunches the bot instead  # dedicated: bot re-hosts a new match, players follow automatically
            r['started'] = True
            if st.get('gidx') == 1 and os.environ.get('NOREHOST') == '1':  # bot reloads the level by itself after GameEnd (host auto-reload); a second explicit start hangs it -> just mark ready
                threading.Timer(6, lambda: kv_set(f"botready{st.get('room', 1)}", '1')).start()
            else: threading.Timer(4 if st.get('gidx') == 1 else float(os.environ.get('REJOIN_DELAY', '25')), lambda: game_start(c, st)).start()
    elif rid == 35501:
        rmi(c, st, 35601, B(args[0] if args else 1))  # lobby AnswerJoinSuccess(u8 lobby)
        rmi(c, st, 36133, varint(len(MAPS)) + b"".join(B(m) + struct.pack('<HH', i, 0) for i, m in MAPS))  # NotifyModeMapList (u8 mode,u16 map,u16 ?)
        rmi(c, st, 36139, varint(len(MAPS)) + b"".join(struct.pack('<H', i) + B(i not in NOWORLD) for i, m in MAPS))  # NotifyOpenMapList (u16 map,u8 open)
    elif rid == 35502:  # lobby Leave -> back on Channels screen: answer + resend channel list (else list is empty, JOIN dead)
        rmi(c, st, 35603); rmi(c, st, 35103, varint(1) + channel(1, os.environ.get("CHAN_NAME", "Z_Beginner"), ip_for(c), GAME_PORT)); rmi(c, st, 35101)
    elif rid == 35002: rmi(c, st, 35104, B(1))  # channel AnswerJoinSuccess(u8 channel)
    elif rid == 39002: rmi(c, st, 39103, B(5 if st.get('room') in ROOMS else 4))  # hangar AnswerCloseSuccess(u8 where): ZNetwork 0x100679a0: 4 -> lobby (state 2), 5 -> room (state 3), else stays put (soft-lock)
    elif rid == 39003:  # hangar RequestBuyItem(i32 ItemIndex) -> AnswerBuyItemSuccess(u16 serial, i32): everything is owned already
        idx = struct.unpack_from('<i', args)[0] if len(args) >= 4 else 0
        if not F('FIX_STORE'): rmi(c, st, 39105, H(st.get('byidx', {}).get(idx, 0)) + I(idx))  # old: serial 0 for items outside ITEMS ('invalid data')
        elif idx in st.get('byidx', {}) and (st['byidx'][idx] <= BASE_N or not ival(gitem(idx), 'IsMerge')): rmi(c, st, 39105, H(st['byidx'][idx]))  # owned already (fixed list, or non-stacking)
        elif idx <= 0 or (gtab('d3') and not gitem(idx)): rmi(c, st, 39106, I(0)); return  # AnswerBuyItemFailed [u32]
        else:  # new item / stack: SendItem 30456 or SendItemValue 30462, then AnswerBuyItemSuccess [u16 serial]
            e, new = inv_add(st.get('name', 'Player'), idx); st.setdefault('inv', {})[e[0]] = (idx, e[3]); st.setdefault('byidx', {}).setdefault(idx, e[0])
            rmi(c, st, 30456, item_row(*e)) if new else rmi(c, st, 30462, H(e[0]) + I(e[2]) + B(1)); rmi(c, st, 39105, H(e[0]))
        rmi(c, st, 30255, struct.pack('<q', MONEY)); rmi(c, st, 30355, struct.pack('<q', MONEY))
    elif rid == 39004:  # hangar RequestEquipItem(u16 serial) -> AnswerEquipItemSuccess(u16) + SendEquipSlot + SendEquip; remember per account (used in matches)
        equip_item(c, st, struct.unpack_from('<H', args)[0])  # FIX_STORE: no fake 30466 weapon rows; serial 0 (store 'equip now' prompt) just answers
    elif F('FIX_STORE') and rid in (39008, 39009, 39010, 39011, 39012, 39404, 39604, 39605, 39606): store(c, st, rid, args)
    elif F('FIX_FRIENDS') and 41001 <= rid <= 41006: friends(c, st, rid, args)
    elif F('FIX_CLAN') and 42001 <= rid <= 42026 and not GAME: clan(c, st, rid, args)
    elif GAME and rid == 37018:  # in-match weapon select (N): RequestChangeWeapon(u8, 5 x u16 inventory serial, 0 = keep) -> save + AnswerChangeWeaponSuccess(u8) + NotifyUserWeaponInfo to all
        me = st.get('acct') or pname(uid(st) + 1)  # account recorded at 37001; fallback = old guess (display only, never saved)
        if len(args) >= 11 and st.get('acct'):
            sl = slots_of(me)
            for i in range(5):
                n = struct.unpack_from('<H', args, 1 + 2 * i)[0]
                if 2 <= n <= len(ITEMS) + 1: sl[0x15 + i] = ITEMS[n - 2][0]  # serial 1 = PVE ticket, 2.. = ITEMS (same order as SendItemList)
                elif n > BASE_N and F('FIX_STORE'): sl[0x15 + i] = next((e[1] for e in inv_of(me)['x'] if e[0] == n), sl.get(0x15 + i))  # bought weapon
            kv_set('slots_' + me, json.dumps(sl))
        else: log(f'37018 short payload ({len(args)} bytes): keeping saved loadout')
        e = equip_of(me)
        rmi(c, st, 37467, args[:1] or B(0))
        g = float(os.environ.get('LOADOUT_GRACE', '0'))
        if g > 0 and len(args) >= 11 and 0 <= time.time() - st.get('spawn_t', 0) <= g:  # loadout grace: re-spawn in place so the new weapons apply now
            log('loadout grace respawn uid', uid(st)); st['spawn_t'] = 0  # once per life
            def _gr(c=c, st=st, u=uid(st)):
                try: rmi(c, st, 37442, B(u)); rmi(c, st, 37424, L24(0)); rmi(c, st, 37424, L24(u))
                except OSError: return
                for cc, ss in [x for x in PLAYERS if x[0].fileno() != -1] or [(c, st)]:
                    try: rmi(cc, ss, 37444, B(u))
                    except OSError: pass
            threading.Timer(0.3, _gr).start()
        for cc, ss in [x for x in PLAYERS if x[0].fileno() != -1] or [(c, st)]:  # NotifyUserWeaponInfo(u8 user, 5 x i32 weapons, 6 x i32 parts) - ZNetwork 0x100a0ae0
            try: rmi(cc, ss, 37469, B(uid(st)) + b''.join(I(x) for x in e[:5]) + b''.join(I(x) for x in (e[5:11] if F('FIX_DEATH') else e[9:15])))  # FIX_DEATH: 6 custom-part slots follow the 5 weapons
            except OSError: pass
    elif rid in (38001, 38002, 38003) and F('FIX_CHAT'): chat(c, st, rid, args)
    elif rid == 30901 and F('FIX_RECORDS'):  # PLAYER INFO: AnswerLoginSuccess + SendMapQuestList(varint n, [u16 map][11 x u32: win, draw, lose, kill, hs, 0, death, 0 x4]) PvP row map 204, PvE row map 704
        r = {}
        try: r = json.loads(kv_get('rec_' + st.get('name', '')) or '{}')
        except ValueError: pass
        rmi(c, st, 30951)
        rmi(c, st, 30953, varint(2) + H(204) + struct.pack('<11I', r.get('win', 0), r.get('draw', 0), r.get('lose', 0), r.get('kill', 0), 0, 0, r.get('death', 0), 0, 0, 0, 0) + H(704) + bytes(44))
    elif rid in AUTO: rmi(c, st, AUTO[rid])
    elif NAMES.get(rid + 50) == "AnswerLoginSuccess": rmi(c, st, rid + 50)  # per-service RequestLogin

LOCK = threading.RLock()  # all shared state (ROOMS/PLAYERS/KD/...) is touched under this lock
_on_rmi = on_rmi
def on_rmi(c, st, rid, args):
    with LOCK:
        st['sent'] = []
        try: return _on_rmi(c, st, rid, args)
        except Exception as e:  # bad input / state: log + matching AnswerXFailed [u32 0] so the client isn't left waiting
            log(f"rmi {rid} bad args/state: {e!r}"); n = NAMES.get(rid, '')
            fid = next((k for k in range(rid, rid + 300) if n.startswith('Request') and NAMES.get(k) == 'Answer' + n[7:] + 'Failed'), 0)
            if fid and not any(NAMES.get(k) == 'Answer' + n[7:] + 'Success' for k in st.get('sent', ())):
                try: rmi(c, st, fid, I(0))
                except Exception: pass
_prune_rooms = prune_rooms
def prune_rooms():
    with LOCK: return _prune_rooms()

def injector(c, st):
    f = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"cmd_{PORT}.txt")
    while not st.get('dead'):
        time.sleep(0.5)
        try: ev = kv_get(f"ended{st['room']}") if not GAME and st.get('room') else None
        except OSError: continue  # unreadable this round: retry next tick
        if ev is not None and ev != st.setdefault('ended_seen', ev):  # baseline on first look: ignore older matches
            st['ended_seen'] = ev
            try: rmi(c, st, 36105, B(0)); log('pre-end: room game flag off')
            except OSError: pass
        if os.path.exists(f) and "aes" in st:
            mine = f + f".{st['port']}"
            try: os.replace(f, mine)
            except OSError: continue  # another connection took it
            txt = open(mine).read(); os.remove(mine)
            for line in txt.split("\n"):
                if line.strip() == 'END': end_match(); continue
                if line.strip():
                    rid, *h = line.split(); pl = bytes.fromhex(h[0]) if h else b""
                    for cc, ss in ([x for x in PLAYERS if x[0].fileno() != -1] if GAME and PLAYERS else [(c, st)]):  # game server: broadcast
                        try: rmi(cc, ss, int(rid), pl)
                        except OSError: pass

def handle(c, a):
    log("connect", a); buf = b""; st = {'port': a[1], 'ip': a[0]}
    threading.Thread(target=injector, args=(c, st), daemon=True).start()
    try:
        while (d := c.recv(65536)):
            st['last'] = time.time()
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
    log("disconnect", a); st['dead'] = True
    if GAME and os.environ.get('DEDI') != '1' and uid(st) == 1 and any(ss is st for _, ss in PLAYERS):
        log('host left mid-match -> end match'); threading.Thread(target=end_match, daemon=True).start()
    try: c.close()
    except OSError: pass
    if not GAME and F('FIX_CLAN') and st.get('clan_login'):  # members see me go offline
        try:
            with LOCK: clan_presence(st.get('name', ''))
        except Exception as e: log('clan presence err', e)
    prune_rooms()

try:  # dev convenience: replace a stale server on this port
    import psutil
    for cn in psutil.net_connections("tcp"):
        if cn.laddr.port == PORT and cn.status == "LISTEN" and cn.pid != os.getpid(): psutil.Process(cn.pid).kill()
    time.sleep(0.5)
except ImportError: pass
s = socket.socket(); s.bind((os.environ.get("BIND", "0.0.0.0"), PORT)); s.listen()  # BIND=127.0.0.1 for Steam-tunnel hosting (no firewall prompt)
log("listening", PORT)
while True:
    c, a = s.accept(); threading.Thread(target=handle, args=(c, a), daemon=True).start()
