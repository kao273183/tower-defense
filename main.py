import pygame, sys, math, random, os
from game_config import CREEP_CONFIG, get_wave_creeps

import game_config as CFG

# --- detect web (pygbag/pyodide) ---
IS_WEB = (sys.platform == "emscripten")


# 《塔路之戰》 Pygame 版 v0.0.5 
"""
V0.0.3 新增：主選單
V0.0.4 新增：抽卡機制
V0.0.5 新增：地圖選擇
V0.0.51 新增：錢幣卡片、機率調整
V0.0.52 新增：多了幾個怪物
V0.0.53 修正:怪物血量、攻擊力、速度調整
未來規劃
"""
TITLENAME = "塔路之戰-V0.0.56-Beta"
pygame.init()
try:
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
except Exception:
    pass
towers=[]; creeps=[]; bullets=[]; hits=[]; corpses=[]; gains=[]; upgrades=[]
W, H = 1280, 720
CELL = 40
# --- 地圖格數與畫面偏移 ---
COLS, ROWS = 15, 9
LEFT = (W - COLS * CELL) // 2
TOP  = 60

# --- 讀取外部設定：將 game_config.py 中的大寫常數覆蓋到此 ---
def apply_external_config():
    global LEFT, TOP
    if not CFG:
        return
    provided = set()
    for name in dir(CFG):
        if name.isupper():
            globals()[name] = getattr(CFG, name)
            provided.add(name)
    # 若外部設定未提供 LEFT/TOP，依目前 W/COLS/CELL 重新計算置中
    if 'LEFT' not in provided:
        globals()['LEFT'] = (globals()['W'] - globals()['COLS'] * globals()['CELL']) // 2
    if 'TOP' not in provided:
        # 若外部未提供，保留現值（預設 60）
        globals()['TOP'] = globals().get('TOP', 60)

# 套用一次外部設定（需在載入圖片與地圖之前）
apply_external_config()
towers=[]; creeps=[]; bullets=[]; hits=[]; corpses=[]; gains=[]; upgrades=[]
current_spawn = None   # 本波實際出怪口
next_spawn = None      # 下一波預告出怪口（按 N 前就會看見）

# --- 遊戲狀態（主選單 / 遊戲中 / 說明） ---
GAME_MENU    = 'menu'
GAME_MAPSEL  = 'mapselect'   # 新增：地圖選擇
GAME_PLAY    = 'play'
GAME_HELP    = 'help'
GAME_LOADING = 'loading'
game_state   = GAME_LOADING

# 主選單按鈕樣式
BTN_W, BTN_H = 260, 56
BTN_GAP = 18
# ---- 外部地圖檔設定 ----
MAP_USE_FILE    = True
MAP_FILE_PATH   = "assets/map/map1.txt"  # 可用字元: '0'=可建, '1'=道路, '2'=牆, '3'=不可建, 'S'=出怪, 'C'=主堡

# --- 地圖選擇相關 ---
MAPS_DIR        = "assets/map"
MAP_CHOICES     = []   # [{'name': 'map1', 'path': 'assets/map/map1.txt'}, ...]
RANDOM_MAP_TOKEN = "__RANDOM_MAP__"
selected_map_idx = 0

def discover_maps():
    """掃描 MAPS_DIR 取得所有 .txt 地圖清單（固定 ROWSxCOLS 才列入）。"""
    global MAP_CHOICES, selected_map_idx
    MAP_CHOICES = []
    if os.path.isdir(MAPS_DIR):
        for fname in sorted(os.listdir(MAPS_DIR)):
            if not fname.lower().endswith(".txt"):
                continue
            fpath = os.path.join(MAPS_DIR, fname)
            # 粗略驗證：讀第一行長度是否為 COLS，行數是否為 ROWS，不合則仍可列出但加上標註
            ok = True
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    lines = [l.rstrip("\n") for l in f if l.strip()]
                ok = (len(lines) == ROWS and (len(lines[0]) if lines else 0) == COLS)
            except Exception:
                ok = False
            name = os.path.splitext(fname)[0]
            if ok:
                MAP_CHOICES.append({'name': name, 'path': fpath})
            else:
                # 仍列出，供玩家嘗試；但名稱後面標註尺寸不符
                MAP_CHOICES.append({'name': f"{name} (尺寸不符)", 'path': fpath})
    if not MAP_CHOICES:
        # 無檔案時，至少提供目前預設 MAP_FILE_PATH
        MAP_CHOICES = [{'name': os.path.basename(MAP_FILE_PATH), 'path': MAP_FILE_PATH}]
    # 預設選第一個
    selected_map_idx = 0

def set_current_map(path):
    """設定目前地圖檔並重新載入路徑。"""
    global MAP_FILE_PATH
    MAP_FILE_PATH = path
    load_map_from_file()
    # 若已定義路徑重建函式，立即重建；若尚未定義（啟動早期），稍後全域會呼叫一次 rebuild_paths()
    try:
        rebuild_paths()
    except NameError:
        pass

def load_map_from_file():
    global MAP, ROWS, COLS, SPAWNS, CASTLE_ROW, CASTLE_COL
    if not (MAP_USE_FILE and os.path.exists(MAP_FILE_PATH)):
        return False
    with open(MAP_FILE_PATH, 'r', encoding='utf-8') as f:
        lines = [line.rstrip("\n") for line in f if line.strip()]
    if not lines:
        return False
    rows = len(lines)
    cols = len(lines[0])
    # 僅接受與目前設定相同尺寸，否則退回預設
    if rows != ROWS or cols != COLS:
        print(f"[map] size mismatch: file={cols}x{rows}, expected={COLS}x{ROWS}, fallback to default")
        return False
    m = [[0 for _ in range(COLS)] for _ in range(ROWS)]
    spawns = []
    castle_r, castle_c = 0, COLS // 2
    for r, line in enumerate(lines):
        for c, ch in enumerate(line):
            if ch == '0':
                m[r][c] = 0
            elif ch == '1':
                m[r][c] = 1
            elif ch == '2':
                m[r][c] = 2
            elif ch == '3':
                m[r][c] = 3  # 不可建造區
            elif ch.upper() == 'S':
                m[r][c] = 1  # 視覺上當路
                spawns.append((r, c))
            elif ch.upper() == 'C':
                m[r][c] = 2  # 主堡格不可建，由 draw_map 顯示城堡圖
                castle_r, castle_c = r, c
            else:
                m[r][c] = 0
    MAP = m
    SPAWNS = spawns if spawns else [(ROWS-1, COLS//2)]
    CASTLE_ROW, CASTLE_COL = castle_r, castle_c
    return True
#卡牌設定
# === 卡片系統 ===
CARD_COST_DRAW = 5       # 抽卡花費
CARD_COST_BUILD = 10     # Basic_Tower 建置花費（與 BUILD_COST 保持一致或直接以此為主）
CARD_POOL = ["basic", "fire", "wind", "water", "land", "upgrade", "1money", "2money", "3money"]
# 卡面圖與費用（使用你的素材）
CARD_IMAGES = {
    "basic":   "assets/pic/Basic_Tower.png",
    "fire":    "assets/pic/fireCard.png",
    "wind":    "assets/pic/WindCard.png",
    "water":   "assets/pic/waterCard.png",
    "land":    "assets/pic/landCard.png",
    "upgrade": "assets/pic/UpgradeCard.png",   # 升級卡（請將圖放在此路徑）
    "1money": "assets/pic/money1.png",
    "2money": "assets/pic/money2.png",
    "3money": "assets/pic/money3.png",
    "bg":      "assets/pic/BgCard.png",        # 卡底背景
}

# 某些卡面本身已含有外框，避免再疊一層底圖（否則看起來像多重外框）
CARD_SKIP_SLOT_BG = {"upgrade"}
# === 抽卡權重（可被 game_config.py 覆蓋） ===
# key 必須對應 hand / use_card_on_grid 內使用的卡名：basic, fire, water, land, wind, upgrade
CARD_COSTS = {
    "basic":   CARD_COST_BUILD,  # 10
    "fire":    CARD_COST_DRAW,   # 5
    "wind":    CARD_COST_DRAW,
    "water":   CARD_COST_DRAW,
    "land":    CARD_COST_DRAW,
    "upgrade": 0,                # 升級卡本身不再額外扣金幣
    "1money": 0,
    "2money": 0,
    "3money": 0,
}

CARD_RATES_DEFAULT = [
    {'type': 'basic',   'weight': 45},
    {'type': 'fire',    'weight': 2},
    {'type': 'water',   'weight': 2},
    {'type': 'land',    'weight': 2},
    {'type': 'wind',    'weight': 2},
    {'type': 'upgrade', 'weight': 2},
    {'type': '1money', 'weight': 20},#金幣卡
    {'type': '2money', 'weight': 15},#金幣卡
    {'type': '3money', 'weight': 10},#金幣卡
]

def _get_card_rates():
    # 若外部設定有提供 CARD_RATES，且格式正確，則使用外部；否則用預設
    rates = getattr(CFG, 'CARD_RATES', None)
    if isinstance(rates, (list, tuple)) and rates:
        cleaned = []
        for item in rates:
            if isinstance(item, dict) and 'type' in item and 'weight' in item:
                try:
                    w = float(item['weight'])
                except Exception:
                    continue
                if item['type'] in CARD_POOL and w > 0:
                    cleaned.append({'type': item['type'], 'weight': w})
        if cleaned:
            return cleaned
    return CARD_RATES_DEFAULT

def _weighted_choice(card_rates):
    total = sum(c['weight'] for c in card_rates)
    r = random.uniform(0, total)
    upto = 0.0
    for c in card_rates:
        w = c['weight']
        if upto + w >= r:
            return c['type']
        upto += w
    return card_rates[-1]['type']  # 理論上不會到這裡

def _card_display_name(name):
    mapping = {
        'basic': '普通塔',
        'fire': '火元素',
        'water': '水元素',
        'land': '地元素',
        'wind': '風元素',
        'upgrade': '升級',
        '1money': '新增金幣1元',
        '2money': '新增金幣2元',
        '3money': '新增金幣3元',
    }
    return mapping.get(name, name)
# === 卡片圖快取與縮放 ===
CARD_SLOT_SIZE = (80, 110)   # 固定每張卡片在手牌列的顯示尺寸
CARD_SURFACES = {}          # 原始圖
CARD_SURF_SCALED = {}       # 縮放後圖 (依 slot 尺寸)
BG_CARD_IMG = None          # 預先縮好的卡底

def _init_card_assets():
    """一次性載入卡片圖並縮放到卡槽尺寸，避免每幀重複 load/scale。"""
    global CARD_SURFACES, CARD_SURF_SCALED, BG_CARD_IMG
    CARD_SURFACES = {}
    CARD_SURF_SCALED = {}
    # 載入所有卡圖
    for k, p in CARD_IMAGES.items():
        if p and os.path.exists(p):
            try:
                CARD_SURFACES[k] = pygame.image.load(p).convert_alpha()
            except Exception:
                pass
    # 預縮卡底
    if 'bg' in CARD_SURFACES:
        BG_CARD_IMG = pygame.transform.smoothscale(CARD_SURFACES['bg'], CARD_SLOT_SIZE)

def get_card_scaled(name):
    """取得縮放後的卡面圖（快取），保證在 CARD_SLOT_SIZE 內留邊距並置中。"""
    key = (name, CARD_SLOT_SIZE)
    if key in CARD_SURF_SCALED:
        return CARD_SURF_SCALED[key]
    src = CARD_SURFACES.get(name)
    if not src:
        return None
    slot_w, slot_h = CARD_SLOT_SIZE
    # 統一留邊，避免不同素材看起來大小不一
    pad_x, pad_y = 6, 8
    avail_w = max(1, slot_w - pad_x*2)
    avail_h = max(1, slot_h - pad_y*2)
    iw, ih = src.get_width(), src.get_height()
    scale = min(avail_w / iw, avail_h / ih)
    img = pygame.transform.smoothscale(src, (int(iw * scale), int(ih * scale)))
    CARD_SURF_SCALED[key] = img
    return img
# 玩家卡資料
hand = []                # 目前手牌（最多可先不限制或自行加上上限）
selected_card = None     # 被選取的手牌索引或名稱
MAX_HAND_CARDS = 5
HAND_UI_RECTS = []  # 每幀重建：[(rect, index)]
#主堡設定
CASTLE = {
    'hp': 50,      # 當前血量
    'max_hp': 50,  # 最大血量
    'level': 1,      # 當前等級
    'upgrade_cost': 20,  # 下一次升級所需金幣
    'hp_increase': 20,  # 每升級增加血量
}
# --- 小怪（grunt）圖示設定（可用圖片或程式繪圖） ---
GRUNT_USE_IMAGE   = True                 # True: 用圖片；False: 用下方程式繪圖
GRUNT_IMG_PATH    = "assets/pic/monster.png" # 你的小怪圖片路徑（請放到專案 assets/）
GRUNT_IMG_SIZE    = 32                   # 載入後縮放到這個正方形大小 (px)
# 下方為程式繪圖備援（若圖片不存在或載入失敗會使用）
GRUNT_RADIUS      = 14                   # 半徑（整體大小）
GRUNT_FILL        = (120, 200, 120)      # 內部填色
#GRUNT_OUTLINE     = (15, 19, 32)         # 外框顏色
GRUNT_OUTLINE     = (15, 19, 32)         # 外框顏色
GRUNT_OUTLINE_W   = 2                    # 外框線寬

# --- 其他怪物（runner / brute / boss）圖片設定 ---
RUNNER_USE_IMAGE = True
RUNNER_IMG_PATH  = "assets/pic/runner.png"
RUNNER_IMG_SIZE  = 32

BRUTE_USE_IMAGE  = True
BRUTE_IMG_PATH   = "assets/pic/brute.png"
BRUTE_IMG_SIZE   = 36

BOSS_USE_IMAGE   = True
BOSS_IMG_PATH    = "assets/pic/boss.png"
BOSS_IMG_SIZE    = 44
# 怪物圖片
SLIME_USE_IMAGE  = True
SLIME_IMG_PATH   = "assets/pic/slime.png"
SLIME_IMG_SIZE   = 32
BAT_USE_IMAGE    = True
BAT_IMG_PATH     = "assets/pic/bat.png"
BAT_IMG_SIZE     = 32
GIANT_USE_IMAGE  = True
GIANT_IMG_PATH   = "assets/pic/giant.png"
GIANT_IMG_SIZE   = 32
# --- 擊中效果（命中時的爆炸/特效）---
HIT_USE_IMAGE = True
HIT_IMG_PATH  = "assets/pic/blast.png"
HIT_IMG_SIZE  = 32   # 會在繪製時做些微放大縮小
# --- 死亡圖示（怪物死亡時顯示）---
DEATH_USE_IMAGE = True
DEATH_IMG_PATH  = "assets/pic/dead.png"
DEATH_IMG_SIZE  = 40

# --- 擊殺掉落金幣：浮動「+金幣」提示 ---
GAIN_USE_IMAGE   = True
GAIN_IMG_PATH    = "assets/pic/game-coin.png"
GAIN_IMG_SIZE    = 20      # 小圖示大小
GAIN_TTL         = 30      # 存在幀數（約 0.5 秒）
GAIN_RISE        = 0.6     # 每幀向上飄的像素值
GAIN_TEXT_COLOR  = (255, 234, 140)

# 預告用箭頭：顯示下一波的 S 出口
ARROW_IMG = None
ARROW_IMG_PATH = "assets/pic/up-arrow.png"
ARROW_IMG_SIZE = 28

# 右上角狀態圖示（開始/暫停）
PLAY_IMG = None
PAUSE_IMG = None
PLAY_IMG_PATH  = "assets/pic/play.png"
PAUSE_IMG_PATH = "assets/pic/pause.png"
STATUS_ICON_SIZE = 24
STATUS_ICON_MARGIN = 12  # 與右上角邊距

# --- 背景與 Logo ---
BG_IMG = None
BG_IMG_PATH = "assets/pic/bg.jpg"   # 建議 1920x1080 或 1280x720，會自動縮放
LOGO_IMG = None
LOGO_IMG_PATH = "assets/pic/logo.png"
LOGO_MAX_W = 420

# --- 音效與 BGM ---
SFX_SHOOT   = None
SFX_HIT     = None
SFX_DEATH   = None
SFX_COIN    = None
SFX_LEVELUP = None
SFX_CLICK   = None
BGM_PATH    = "assets/sfx/bgm.WAV"
SFX_DIR     = "assets/sfx"
SFX_VOL     = 0.6   # 全局音量（0~1）
BGM_VOL     = 0.35

# --- 防禦塔各等級圖片設定（缺圖則退回程式繪圖） ---
TOWER_USE_IMAGES = True
TOWER_IMG_PATHS = {
    0: "assets/pic/tower_lv1.png",
    1: "assets/pic/tower_lv2.png",
    2: "assets/pic/tower_lv3.png",
    3: "assets/pic/tower_lv3.png",   # 最高等沿用第三張
}

# 單一等級塔圖示大小
TOWER_IMG_SIZE  = 36  # 圖片縮放邊長（像素）

ROCKET_TOWER_IMG       = None
ROCKET_TOWER_IMG_PATH  = "assets/pic/rocket_tower.png"

# 四元素塔 ICON（依元素顯示）
FIRE_TOWER_IMG  = None
WATER_TOWER_IMG = None
LAND_TOWER_IMG  = None
WIND_TOWER_IMG  = None

FIRE_TOWER_IMG_PATH  = "assets/pic/firetower.png"
WATER_TOWER_IMG_PATH = "assets/pic/watertower.png"
LAND_TOWER_IMG_PATH  = "assets/pic/landtower.png"
WIND_TOWER_IMG_PATH  = "assets/pic/windtower.png"

# --- 升級特效（LEVEL UP） ---
LEVELUP_USE_IMAGE = True
LEVELUP_IMG_PATH  = "assets/pic/level-up.png"
LEVELUP_IMG_SIZE  = 40
LEVELUP_TTL       = 24
# --- 建塔 / 升級成本設定 ---
LEVELUP_RISE      = 0.5
# --- 建塔 / 升級成本設定 ---
# --- 建塔 / 升級成本設定 ---
BUILD_COST = 10  # 蓋一座箭塔消耗金幣

# --- 價格表（建塔 / 升級 / 進化）---
PRICES = {
    'build': {
        'arrow': BUILD_COST,    # 基本箭塔建造費
        # 若未來要直接建造分支塔，可在此補：'rocket': 6
    },
    'upgrade': {
        # 依等級索引（0→1, 1→2, 2→進化）
        'arrow':  [10, 15, 20],    # 升到 1/2/3 級的費用（到 3 級時觸發進化邏輯）
        'rocket': [40, 50],       # 0→1、1→2（若你定義 2 級為滿級）
    },
    'evolve': {
        # 從箭塔進化為分支塔的費用（可在設定檔覆蓋）
        'rocket': 60,
    }
}

# --- UI 通知（置頂小提示）---
NOTICES = []  # [{'text': str, 'ttl': int, 'color': (r,g,b), 'x': int|None, 'y': int|None, 'align': 'left'|'right'|'center'}]
NOTICE_TTL = 90
# 預設通知顯示位置與樣式（可改）
NOTICE_X = 500
NOTICE_Y = 610
NOTICE_LINE_GAP = 22
NOTICE_ALIGN_DEFAULT = 'left'  # 'left' | 'right' | 'center'
#基本開局
# 開局給三張基本塔卡
def init_starting_hand():
    global hand, selected_card
    hand = ["basic", "basic", "basic"]  # 對應 Basic_Tower.png
    selected_card = None
def add_notice(text, color=(255, 120, 120), ttl=NOTICE_TTL, x=None, y=None, align=None):
    NOTICES.append({
        'text': text,
        'ttl': ttl,
        'color': color,
        'x': x,
        'y': y,
        'align': (align or NOTICE_ALIGN_DEFAULT)
    })
    if len(NOTICES) > 6:
        del NOTICES[:-6]
#
# 成本查詢輔助
def get_build_cost(ttype='arrow'):
    return PRICES['build'].get(ttype, BUILD_COST)

# 升級成本查詢
def get_upgrade_cost(tower):
    ttype = tower.get('type', 'arrow')
    lv = tower.get('level', 0)
    table = PRICES['upgrade'].get(ttype, [])
    if lv < len(table):
        return table[lv]
    return None

# 進化成本查詢
def get_evolve_cost(target_type):
    return PRICES.get('evolve', {}).get(target_type, 60)
#箭塔設定
TOWER_TYPES = {
    'arrow': {
        0: {'atk': 1, 'range': 2, 'rof': 1.0},
        1: {'atk': 2, 'range': 2, 'rof': 1.2},
        2: {'atk': 2, 'range': 3, 'rof': 1.6},
        3: {'atk': 3, 'range': 3, 'rof': 2.0},
    },
    'rocket': {
        0: {'atk': 3, 'range': 3, 'rof': 0.8},
        1: {'atk': 4, 'range': 3, 'rof': 1.0},
        2: {'atk': 5, 'range': 3, 'rof': 1.2},
        3: {'atk': 6, 'range': 4, 'rof': 1.4},
    },
    'fire': {      # 火元素塔：高攻擊中速
        0: {'atk': 4, 'range': 3, 'rof': 1.2},
        1: {'atk': 6, 'range': 3, 'rof': 1.4},
        2: {'atk': 8, 'range': 4, 'rof': 1.6},
        3: {'atk': 10, 'range': 4, 'rof': 1.8},
    },
    'water': {     # 水元素塔：中攻擊、高減速
        0: {'atk': 2, 'range': 4, 'rof': 1.5},
        1: {'atk': 3, 'range': 4, 'rof': 1.8},
        2: {'atk': 4, 'range': 5, 'rof': 2.0},
        3: {'atk': 5, 'range': 5, 'rof': 2.2},
    },
    'land': {      # 土元素塔：高防禦、穩定攻擊
        0: {'atk': 3, 'range': 3, 'rof': 1.0},
        1: {'atk': 4, 'range': 3, 'rof': 1.2},
        2: {'atk': 5, 'range': 4, 'rof': 1.3},
        3: {'atk': 7, 'range': 4, 'rof': 1.4},
    },
    'wind': {      # 風元素塔：低攻擊、高速連射
        0: {'atk': 1, 'range': 3, 'rof': 2.0},
        1: {'atk': 2, 'range': 3, 'rof': 2.5},
        2: {'atk': 3, 'range': 4, 'rof': 3.0},
        3: {'atk': 4, 'range': 4, 'rof': 3.5},
    },
}

# ---- Optional: override tower attack from external config (game_config.py) ----
def _apply_tower_overrides_from_cfg():
    """
    支援三種覆蓋方式（擇一或混用）：
    1) 直接提供完整的 TOWER_TYPES 於 game_config.py
    2) 只提供每塔各等級攻擊力：TOWER_ATK = {'arrow':[...], 'rocket':[...], 'thunder':[...]}
    3) 只提供倍率：TOWER_ATK_MULT = {'arrow':1.2, 'rocket':0.9, ...}
    """
    global TOWER_TYPES
    try:
        # 1) 完整覆蓋
        if hasattr(CFG, 'TOWER_TYPES') and isinstance(CFG.TOWER_TYPES, dict):
            TOWER_TYPES = CFG.TOWER_TYPES
            return
        # 2) 局部修改 atk 數值
        atk_cfg = getattr(CFG, 'TOWER_ATK', None)
        if isinstance(atk_cfg, dict):
            for ttype, atk_list in atk_cfg.items():
                if ttype in TOWER_TYPES and isinstance(atk_list, (list, tuple)):
                    for lv, val in enumerate(atk_list):
                        if lv in TOWER_TYPES[ttype]:
                            try:
                                TOWER_TYPES[ttype][lv]['atk'] = int(val)
                            except Exception:
                                pass
        # 3) 以倍率整體放大/縮小各塔各等級的 atk
        mult_cfg = getattr(CFG, 'TOWER_ATK_MULT', None)
        if isinstance(mult_cfg, dict):
            for ttype, mul in mult_cfg.items():
                if ttype in TOWER_TYPES:
                    try:
                        mul = float(mul)
                    except Exception:
                        continue
                    for lv in TOWER_TYPES[ttype]:
                        base = TOWER_TYPES[ttype][lv].get('atk', 1)
                        TOWER_TYPES[ttype][lv]['atk'] = max(1, int(round(base * mul)))
    except Exception:
        # 靜默失敗，維持預設數值
        pass

# 套用外部設定（若 game_config.py 有提供）
_apply_tower_overrides_from_cfg()
# ==== Elemental effect helpers ====
def _get_elem_cfg(elem, lvl):
    # 讀 game_config.ELEMENT_EFFECTS；不存在則給預設
    cfg = getattr(CFG, 'ELEMENT_EFFECTS', {}) if hasattr(CFG, 'ELEMENT_EFFECTS') else {}
    if elem == 'fire':
        base = {'type':'burn','duration':1.0,'scale_per_lv':0.01}
    elif elem == 'water':
        base = {'type':'slow','duration':1.0,'scale_per_lv':0.01}
    elif elem == 'land':
        base = {'type':'bleed','duration':0.5,'scale_per_lv':0.015}
    elif elem == 'wind':
        base = {'type':'knockback','base_knockback':1,'scale_per_lv':1}
    else:
        return None
    merged = dict(base)
    if elem in cfg and isinstance(cfg[elem], dict):
        merged.update(cfg[elem])
    # 持續時間依等級成長（秒）
    if merged.get('type') in ('burn','slow','bleed'):
        dur = merged.get('duration', 1.0)
        scale = merged.get('scale_per_lv', 0.0)
        merged['duration'] = float(dur) * (1.0 + scale * max(0, int(lvl)))
    # 擊退格數
    if merged.get('type') == 'knockback':
        base_kb = int(merged.get('base_knockback', 1))
        inc = int(merged.get('scale_per_lv', 1))
        merged['grids'] = max(1, base_kb + inc * max(0, int(lvl)))
    return merged

def _apply_status_on_hit(target, elem_cfg, atk_val):
    if not elem_cfg:
        return
    etype = elem_cfg.get('type')
    eff = target.setdefault('effects', {})
    if etype == 'burn':
        frames = int(60 * elem_cfg.get('duration', 1.0))
        eff['burn'] = {'ttl': frames, 'tick': 10, 'acc': 0, 'dmg': max(1, int(round(atk_val * 0.3)))}
    elif etype == 'slow':
        frames = int(60 * elem_cfg.get('duration', 1.0))
        eff['slow'] = {'ttl': frames, 'ratio': 0.6}
    elif etype == 'bleed':
        frames = int(60 * elem_cfg.get('duration', 0.5))
        eff['bleed'] = {'ttl': frames, 'tick': 10, 'acc': 0, 'dmg': max(1, int(round(atk_val * 0.25)))}
    elif etype == 'knockback':
        # 擊退在命中瞬間處理，這裡不存狀態
        pass

def _do_knockback(creep, grids):
    # 依路徑往回推若干格（若沒有路徑，忽略）
    route = creep.get('route') or []
    wp = int(creep.get('wp', 1))
    if not route:
        return
    target_wp = max(0, wp - 1 - int(grids))
    tr, tc = route[target_wp]
    creep['r'], creep['c'] = float(tr), float(tc)
    creep['wp'] = target_wp + 1
def find_ch_font():
    # On web, system fonts are unavailable; prefer bundled font
    web_font = os.path.join("assets", "font", "NotoSansCJK-Regular.otf")
    if IS_WEB and os.path.exists(web_font):
        return web_font
    paths = [
        "C:/Windows/Fonts/msjh.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    # fallback: try bundled font even on desktop if present
    if os.path.exists(web_font):
        return web_font
    return None

font_path = find_ch_font()
if font_path:
    FONT = pygame.font.Font(font_path, 18)
    BIG  = pygame.font.Font(font_path, 28)
else:
    FONT = pygame.font.SysFont("arial", 18); BIG = pygame.font.SysFont("arial", 28, True)


# Define SMALL font for use in draw_hand_bar()
SMALL = pygame.font.Font(font_path, 14) if font_path else pygame.font.SysFont("arial", 14)

# 將手牌列往上抬高一些，避免被底部遮擋
HAND_BAR_MARGIN_BOTTOM = 36  # 將手牌列往上抬高一些，避免被底部遮擋

screen = pygame.display.set_mode((W, H))
#標題
pygame.display.set_caption(TITLENAME)

# === Loading Screen Helpers ===
LOADING = True
LOAD_STEP = 0
LOAD_TOTAL = 8  # 大致分 8 個階段顯示進度

def draw_loading(message, step=None, total=None):
    # 清背景
    screen.fill((16, 20, 35))
    # 背景圖若已存在可先鋪上
    try:
        if 'BG_IMG' in globals() and BG_IMG:
            screen.blit(BG_IMG, (0, 0))
    except Exception:
        pass
    # 半透明罩
    dim = pygame.Surface((W, H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 140))
    screen.blit(dim, (0, 0))
    # 文字
    title = BIG.render("載入中…", True, (235, 242, 255))
    screen.blit(title, (W//2 - title.get_width()//2, H//2 - 60))
    msg = FONT.render(str(message), True, (210, 220, 235))
    screen.blit(msg, (W//2 - msg.get_width()//2, H//2 - 24))
    # 進度條
    if step is not None and total:
        bw, bh = 420, 16
        bx = W//2 - bw//2
        by = H//2 + 8
        pygame.draw.rect(screen, (40, 55, 96), (bx, by, bw, bh), border_radius=8)
        ratio = max(0.0, min(1.0, float(step)/float(total)))
        pygame.draw.rect(screen, (90, 180, 255), (bx, by, int(bw*ratio), bh), border_radius=8)
    pygame.display.flip()

def loading_tick(message):
    global LOAD_STEP
    draw_loading(message, LOAD_STEP, LOAD_TOTAL)
    # 不阻塞主線，只是畫面更新

# 嘗試載入各怪物圖片與特效（失敗則退回程式繪圖）
MONSTER_IMG = None   # generic
SLIME_IMG   = None
RUNNER_IMG  = None
BRUTE_IMG   = None
BAT_IMG     = None
BOSS_IMG    = None
BOSS_IMG    = None
BLAST_IMG   = None   # 擊中圖片
DEAD_IMG    = None   # 死亡圖片
COIN_IMG    = None   # +金幣 圖示
TOWER_IMGS  = {}     # 依等級載入
LEVELUP_IMG = None   # 升級特效圖
CASTLE_IMG = None    # 城堡圖片
WALL_IMG = None      # 牆壁圖片
CASTLE_IMG_PATH = "assets/pic/castle.png"
WALL_IMG_PATH = "assets/pic/wall.png"
CASTLE_IMG_SIZE = 48
WALL_IMG_SIZE = 40
try:
    LOAD_STEP = 0
    loading_tick("初始化資源…")
    if GRUNT_USE_IMAGE and os.path.exists(GRUNT_IMG_PATH):
        _raw = pygame.image.load(GRUNT_IMG_PATH).convert_alpha()
        MONSTER_IMG = pygame.transform.smoothscale(_raw, (GRUNT_IMG_SIZE, GRUNT_IMG_SIZE))
    if SLIME_USE_IMAGE and os.path.exists(SLIME_IMG_PATH):
        _raw = pygame.image.load(SLIME_IMG_PATH).convert_alpha()
        SLIME_IMG = pygame.transform.smoothscale(_raw, (SLIME_IMG_SIZE, SLIME_IMG_SIZE))
    if RUNNER_USE_IMAGE and os.path.exists(RUNNER_IMG_PATH):
        _raw = pygame.image.load(RUNNER_IMG_PATH).convert_alpha()
        RUNNER_IMG = pygame.transform.smoothscale(_raw, (RUNNER_IMG_SIZE, RUNNER_IMG_SIZE))
    if BRUTE_USE_IMAGE and os.path.exists(BRUTE_IMG_PATH):
        _raw = pygame.image.load(BRUTE_IMG_PATH).convert_alpha()
        BRUTE_IMG = pygame.transform.smoothscale(_raw, (BRUTE_IMG_SIZE, BRUTE_IMG_SIZE))
    if BAT_USE_IMAGE and os.path.exists(BAT_IMG_PATH):
        _raw = pygame.image.load(BAT_IMG_PATH).convert_alpha()
        BAT_IMG = pygame.transform.smoothscale(_raw, (BAT_IMG_SIZE, BAT_IMG_SIZE))
    if BOSS_USE_IMAGE and os.path.exists(BOSS_IMG_PATH):
        _raw = pygame.image.load(BOSS_IMG_PATH).convert_alpha()
        BOSS_IMG = pygame.transform.smoothscale(_raw, (BOSS_IMG_SIZE, BOSS_IMG_SIZE))
    LOAD_STEP = 1
    loading_tick("載入怪物素材…")
    if HIT_USE_IMAGE and os.path.exists(HIT_IMG_PATH):
        BLAST_IMG = pygame.image.load(HIT_IMG_PATH).convert_alpha()
    if DEATH_USE_IMAGE and os.path.exists(DEATH_IMG_PATH):
        _raw = pygame.image.load(DEATH_IMG_PATH).convert_alpha()
        DEAD_IMG = pygame.transform.smoothscale(_raw, (DEATH_IMG_SIZE, DEATH_IMG_SIZE))
    if GAIN_USE_IMAGE and os.path.exists(GAIN_IMG_PATH):
        _raw = pygame.image.load(GAIN_IMG_PATH).convert_alpha()
        COIN_IMG = pygame.transform.smoothscale(_raw, (GAIN_IMG_SIZE, GAIN_IMG_SIZE))
    LOAD_STEP = 2
    loading_tick("載入特效素材…")
    if TOWER_USE_IMAGES:
        for lv, p in TOWER_IMG_PATHS.items():
            if p and os.path.exists(p):
                _raw = pygame.image.load(p).convert_alpha()
                TOWER_IMGS[lv] = pygame.transform.smoothscale(_raw, (TOWER_IMG_SIZE, TOWER_IMG_SIZE))
    LOAD_STEP = 3
    loading_tick("載入防禦塔素材…")
    if LEVELUP_USE_IMAGE and os.path.exists(LEVELUP_IMG_PATH):
        _raw = pygame.image.load(LEVELUP_IMG_PATH).convert_alpha()
        LEVELUP_IMG = pygame.transform.smoothscale(_raw, (LEVELUP_IMG_SIZE, LEVELUP_IMG_SIZE))
    LOAD_STEP = 4
    loading_tick("載入升級素材…")
    if os.path.exists(CASTLE_IMG_PATH):
        _raw = pygame.image.load(CASTLE_IMG_PATH).convert_alpha()
        CASTLE_IMG = pygame.transform.smoothscale(_raw, (CASTLE_IMG_SIZE, CASTLE_IMG_SIZE))
    if os.path.exists(WALL_IMG_PATH):
        _raw = pygame.image.load(WALL_IMG_PATH).convert_alpha()
        WALL_IMG = pygame.transform.smoothscale(_raw, (WALL_IMG_SIZE, WALL_IMG_SIZE))
    if os.path.exists(ARROW_IMG_PATH):
        _raw = pygame.image.load(ARROW_IMG_PATH).convert_alpha()
        ARROW_IMG = pygame.transform.smoothscale(_raw, (ARROW_IMG_SIZE, ARROW_IMG_SIZE))
    if os.path.exists(PLAY_IMG_PATH):
        _raw = pygame.image.load(PLAY_IMG_PATH).convert_alpha()
        PLAY_IMG = pygame.transform.smoothscale(_raw, (STATUS_ICON_SIZE, STATUS_ICON_SIZE))
    if os.path.exists(PAUSE_IMG_PATH):
        _raw = pygame.image.load(PAUSE_IMG_PATH).convert_alpha()
        PAUSE_IMG = pygame.transform.smoothscale(_raw, (STATUS_ICON_SIZE, STATUS_ICON_SIZE))
    # 分支塔圖
    if os.path.exists(ROCKET_TOWER_IMG_PATH):
        _raw = pygame.image.load(ROCKET_TOWER_IMG_PATH).convert_alpha()
        ROCKET_TOWER_IMG = pygame.transform.smoothscale(_raw, (TOWER_IMG_SIZE, TOWER_IMG_SIZE))

    # 四元素圖示（用於依元素覆蓋顯示）
    if os.path.exists(FIRE_TOWER_IMG_PATH):
        _raw = pygame.image.load(FIRE_TOWER_IMG_PATH).convert_alpha()
        FIRE_TOWER_IMG = pygame.transform.smoothscale(_raw, (TOWER_IMG_SIZE, TOWER_IMG_SIZE))
    if os.path.exists(WATER_TOWER_IMG_PATH):
        _raw = pygame.image.load(WATER_TOWER_IMG_PATH).convert_alpha()
        WATER_TOWER_IMG = pygame.transform.smoothscale(_raw, (TOWER_IMG_SIZE, TOWER_IMG_SIZE))
    if os.path.exists(LAND_TOWER_IMG_PATH):
        _raw = pygame.image.load(LAND_TOWER_IMG_PATH).convert_alpha()
        LAND_TOWER_IMG = pygame.transform.smoothscale(_raw, (TOWER_IMG_SIZE, TOWER_IMG_SIZE))
    if os.path.exists(WIND_TOWER_IMG_PATH):
        _raw = pygame.image.load(WIND_TOWER_IMG_PATH).convert_alpha()
        WIND_TOWER_IMG = pygame.transform.smoothscale(_raw, (TOWER_IMG_SIZE, TOWER_IMG_SIZE))

    LOAD_STEP = 5
    loading_tick("載入地圖與介面圖示…")

    # 背景 / Logo
    if os.path.exists(BG_IMG_PATH):
        _raw = pygame.image.load(BG_IMG_PATH).convert()
        BG_IMG = pygame.transform.smoothscale(_raw, (W, H))
    if os.path.exists(LOGO_IMG_PATH):
        _raw = pygame.image.load(LOGO_IMG_PATH).convert_alpha()
        # 等比例縮到 LOGO_MAX_W 寬
        w, h = _raw.get_width(), _raw.get_height()
        if w > LOGO_MAX_W:
            scale = LOGO_MAX_W / float(w)
            LOGO_IMG = pygame.transform.smoothscale(_raw, (int(w*scale), int(h*scale)))
        else:
            LOGO_IMG = _raw

    LOAD_STEP = 6
    loading_tick("載入背景與標誌…")

    # 音效載入（安全載入）
    def _load_sfx(name, vol=SFX_VOL):
        p = os.path.join(SFX_DIR, name)
        if os.path.exists(p):
            s = pygame.mixer.Sound(p)
            s.set_volume(vol)
            return s
        return None
    SFX_SHOOT   = _load_sfx('shoot.wav',   0.35)
    SFX_HIT     = _load_sfx('hit.wav',     0.30)
    SFX_DEATH   = _load_sfx('death.wav',   0.50)
    SFX_COIN    = _load_sfx('coin.wav',    0.55)
    SFX_LEVELUP = _load_sfx('levelup.wav', 0.6)
    SFX_CLICK   = _load_sfx('click.wav',   0.45)
    SFX_DRAW    = _load_sfx('draw.wav',    0.55)

    LOAD_STEP = 7
    loading_tick("載入音效…")

    # BGM
    if os.path.exists(BGM_PATH) and not IS_WEB:  # web 端可改為點擊開始後再播放，避免自動播放限制
        try:
            pygame.mixer.music.load(BGM_PATH)
            pygame.mixer.music.set_volume(BGM_VOL)
            pygame.mixer.music.play(-1)
        except Exception:
            pass
except Exception:
    pass
_init_card_assets()
LOAD_STEP = 8
draw_loading("完成！", LOAD_STEP, LOAD_TOTAL)
LOADING = False
# 掃描可用地圖並套用預設第一張
discover_maps()
if MAP_CHOICES:
    set_current_map(MAP_CHOICES[0]['path'])
game_state = GAME_MENU
# 新增：地圖選擇畫面
def draw_map_select():
    screen.fill((16, 20, 35))
    if BG_IMG:
        screen.blit(BG_IMG, (0,0))
        dim = pygame.Surface((W,H), pygame.SRCALPHA); dim.fill((0,0,0,120)); screen.blit(dim,(0,0))
    title = BIG.render("選擇地圖", True, (250, 245, 255))
    screen.blit(title, (W//2 - title.get_width()//2, 80))
    tip = FONT.render("↑/↓ 切換 R隨機生成地圖，Enter 確認；Esc 返回主選單", True, (210,220,235))
    screen.blit(tip, (W//2 - tip.get_width()//2, 120))

    # 列表
    cx = W//2 - 420//2
    y0 = 170
    item_w, item_h = 420, 44
    gap = 10

    mx, my = pygame.mouse.get_pos()
    for i, item in enumerate(MAP_CHOICES):
        r = pygame.Rect(cx, y0 + i*(item_h+gap), item_w, item_h)
        if r.collidepoint(mx, my):
            hover = True
        else:
            hover = False
        sel = (i == selected_map_idx)
        base = (40,55,96) if (hover or sel) else (31,42,68)
        pygame.draw.rect(screen, base, r, border_radius=8)
        pygame.draw.rect(screen, (90,120,200) if sel else (70,90,130), r, 2, border_radius=8)
        label = FONT.render(item['name'], True, (235,242,255))
        screen.blit(label, (r.x + 12, r.y + (item_h - label.get_height())//2))

BG=(11,16,32); PANEL=(27,34,56); TEXT=(230,237,243); GRID=(31,42,68)
ROAD=(180,127,37,140); LAND=(17,168,125,120); BLOCK=(40,48,73,200);GREY=(100,100,100,100)
CYAN=(34,178,234); WHITE=(226,232,240)

# === Click performance tuning ===
ENABLE_CLICK_SFX = False   # 關閉滑鼠點擊音效避免卡頓（可改 True 重新開啟）
CLICK_DEBOUNCE_MS = 80     # 在此時間內的連續點擊將被忽略
_last_click_ts = 0




clock = pygame.time.Clock()

# --- tiny helpers ---
def sfx(sound):
    try:
        if not sound:
            return
        # 避免點擊音造成卡頓：可用 ENABLE_CLICK_SFX 控制
        if (sound is SFX_CLICK) and (not ENABLE_CLICK_SFX) and (game_state in (GAME_PLAY,)):
            return
        sound.play()
    except Exception:
        pass

# --- 地圖載入：優先讀外部檔，否則使用預設的直線版 ---
CASTLE_ROW = 0
CASTLE_COL = COLS // 2

# 預設：先建立 ROWS x COLS 的可建地
MAP = [[0 for _ in range(COLS)] for _ in range(ROWS)]
# 最上排鋪牆（包含城堡那格也標成不可建，純顯示由 draw_map 決定）
for c in range(COLS):
    MAP[CASTLE_ROW][c] = 2
SPAWNS = [(ROWS-1, CASTLE_COL)]

# 嘗試讀外部地圖檔（成功就覆蓋 MAP / SPAWNS / CASTLE_*）
load_map_from_file()
# ---- 路徑：依 MAP 中的道路(1) 從每個 S 走到 C ----
PATHS = {}  # {(sr,sc): [(r,c), ... , (CASTLE_ROW,CASTLE_COL)]}

def _passable(r, c):
    # 道路可走；城堡格視為終點可進入（使用內嵌邊界判定避免先後順序問題）
    return (0 <= r < ROWS and 0 <= c < COLS) and (MAP[r][c] == 1 or (r == CASTLE_ROW and c == CASTLE_COL))

def _neighbors(r, c):
    for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
        rr, cc = r+dr, c+dc
        if _passable(rr, cc):
            yield rr, cc

def _bfs_path(start, goal):
    from collections import deque
    sr, sc = start; gr, gc = goal
    q = deque([(sr, sc)])
    prev = { (sr,sc): None }
    while q:
        r, c = q.popleft()
        if (r, c) == (gr, gc):
            break
        for rr, cc in _neighbors(r, c):
            if (rr, cc) not in prev:
                prev[(rr, cc)] = (r, c)
                q.append((rr, cc))
    if (gr, gc) not in prev:
        return None
    path = []
    cur = (gr, gc)
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path

def _fallback_path(start, goal):
    # 若找不到路，就用直線靠近
    sr, sc = start; gr, gc = goal
    path = [(sr, sc)]
    r, c = sr, sc
    while r != gr:
        r += -1 if gr < r else 1
        path.append((r, c))
    while c != gc:
        c += -1 if gc < c else 1
        path.append((r, c))
    return path

def rebuild_paths():
    global PATHS
    PATHS = {}
    goal = (CASTLE_ROW, CASTLE_COL)
    for s in SPAWNS:
        p = _bfs_path(s, goal)
        if not p:
            p = _fallback_path(s, goal)
        PATHS[s] = p

# 建立所有出怪點的路徑
rebuild_paths()
# ---- Boss 出場設定：在這些固定波數出現 Boss（於本波第 9 次出怪）----
BOSS_WAVES = {w for w in range(10, 999, 10)}       
BOSS_SPAWN_INDEX = 8         # 第 0~8 次出怪中的最後一次（第 9 隊）

def in_bounds(r,c): return 0<=r<ROWS and 0<=c<COLS
def is_buildable(r,c): return in_bounds(r,c) and MAP[r][c]==0

TOWER = TOWER_TYPES['arrow']
CREEP= {
    "slime": {
        "name": "史萊姆",
        "hp": 10,
        "speed": 0.01,
        "reward": 1,
        "attack": 1,
        "color": (120, 255, 120),
        "image": SLIME_IMG_PATH
    },
    "runner": {
        "name": "鬼魂",
        "hp": 10,
        "speed": 0.02,
        "reward": 2,
        "attack": 2,
        "color": (180, 130, 90),
        "image": RUNNER_IMG_PATH
    },
    "bat": {
        "name": "蝙蝠",
        "hp": 20,
        "speed": 0.02,
        "reward": 1,
        "attack": 1,
        "color": (120, 120, 220),
        "image": BAT_IMG_PATH
    },
    "giant": {
        "name": "巨人",
        "hp": 60,
        "speed": 0.05,
        "reward": 10,
        "attack": 5,
        "color": (200, 80, 80),
        "image":GIANT_IMG_PATH
    },
    "boss": {
        "name": "魔王",
        "hp": 1000,
        "speed": 0.06,
        "reward": 50,
        "attack": 20,
        "color": (255, 60, 60)
    }
}

# 將外部設定的怪物資料合併進內建表，確保新種類（如 grunt）能取得顏色與獎勵等屬性
for _cname, _cfg in CREEP_CONFIG.items():
    merged = CREEP.get(_cname, {}).copy()
    merged.update(_cfg)
    CREEP[_cname] = merged

running=False; speed=1; tick=0; gold=100; life=20; wave=0; wave_incoming=False; spawn_counter=0
towers=[]; creeps=[]; bullets=[]; hits=[]; corpses=[]; gains=[]; upgrades=[];effects = []

ids={'tower':1,'creep':1}
wave_spawn_queue=[]; SPAWN_INTERVAL=60
sel=None

def grid_to_px(r,c): return LEFT+c*CELL, TOP+r*CELL
def center_px(r,c): x,y=grid_to_px(r,c); return x+CELL/2,y+CELL/2
def manhattan(a,b):
    return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))

def draw_panel():
    pygame.draw.rect(screen, PANEL, (0,0,W,TOP))
    txt = FONT.render(f"$ {gold}    Wave {wave}{' (spawning)' if wave_incoming else ''}    Speed x{speed}", True, TEXT)
    screen.blit(txt, (16, 10))
    tips = FONT.render("C升級主堡 S回收｜Space暫停/開始｜N下一波｜R重置｜1/2/3速度", True, TEXT)
    screen.blit(tips, (16, TOP-28))
    if not wave_incoming and next_spawn:
        nr, nc = next_spawn
        info = FONT.render(f"＊＊下一波出口：怪物 在 ({nr},{nc})——按 N 開始＊＊", True, (255, 0, 0))
        screen.blit(info, (16, 620))

    # 右上角：開始/暫停圖示
    icon = (PLAY_IMG if running else PAUSE_IMG)
    if icon:
        rect = icon.get_rect()
        rect.top = (TOP - rect.height)//2
        rect.right = W - STATUS_ICON_MARGIN
        screen.blit(icon, rect)
    else:
        # 備援：文字
        s = FONT.render("PLAY" if running else "PAUSE", True, TEXT)
        screen.blit(s, (W - STATUS_ICON_MARGIN - s.get_width(), (TOP - s.get_height())//2))

    # 價格提示（放在面板右下角）
    #price_hint = FONT.render(f"建塔${PRICES['build']['arrow']}｜升級(箭) ${'/'.join(map(str,PRICES['upgrade']['arrow']))}", True, (200,210,230))
    #screen.blit(price_hint, (16, 600))

    # 浮動通知（可自訂座標與對齊；未指定則用全域預設）
    alive = []
    cursor_y = NOTICE_Y
    for n in NOTICES:
        # 漸隱顯示：依剩餘存活時間調整 alpha
        life_ratio = max(0.0, min(1.0, n['ttl'] / float(NOTICE_TTL)))
        col = n['color']
        txt = FONT.render(n['text'], True, col)
        try:
            txt.set_alpha(int(255 * life_ratio))
        except Exception:
            pass
        draw_x = n['x'] if n['x'] is not None else NOTICE_X
        draw_y = n['y'] if n['y'] is not None else cursor_y
        align = (n.get('align') or NOTICE_ALIGN_DEFAULT)
        if align == 'right':
            pos = (draw_x - txt.get_width(), draw_y)
        elif align == 'center':
            pos = (draw_x - txt.get_width()//2, draw_y)
        else:
            pos = (draw_x, draw_y)
        screen.blit(txt, pos)
        if n['y'] is None:
            cursor_y += NOTICE_LINE_GAP
        n['ttl'] -= 1
        if n['ttl'] > 0:
            alive.append(n)
    NOTICES[:] = alive
    #主堡
    # 顯示主堡狀態
    castle_txt = FONT.render(f"主堡Lv{CASTLE['level']}  HP:{CASTLE['hp']}", True, (255,255,255))
    screen.blit(castle_txt, (16, 80))

    # 若想顯示血條
    bar_x, bar_y, bar_w, bar_h = 16, 100, 160, 8
    hp_ratio = CASTLE['hp'] / CASTLE['max_hp']
    pygame.draw.rect(screen, (60,60,60), (bar_x, bar_y, bar_w, bar_h))
    pygame.draw.rect(screen, (180,60,60), (bar_x, bar_y, int(bar_w * hp_ratio), bar_h))
#選取卡片
def draw_hand_bar():
    global HAND_UI_RECTS
    HAND_UI_RECTS = []

    # 底條與提示（根據卡片尺寸自動計算高度，讓卡片完整包含在框內）
    slot_w, slot_h = CARD_SLOT_SIZE
    gap = 10
    bar_h = slot_h + 24  # 上下各留 12px 內距
    bar_y = H - (bar_h + HAND_BAR_MARGIN_BOTTOM)

    # 藍色光框底（比卡片高，確保卡片完全在框內）
    glow_rect = pygame.Rect(16, bar_y, W - 32, bar_h)
    pygame.draw.rect(screen, (50, 120, 255), glow_rect, 2, border_radius=12)

    # 提示文字
    tip = f"D 抽卡(-${CARD_COST_DRAW})｜左鍵：地圖出牌建塔/升級｜右鍵手牌：丟棄"
    if selected_card is not None and 0 <= selected_card < len(hand):
        tip += f"｜已選：{hand[selected_card]}"
    hint = FONT.render(tip, True, (220, 230, 240))
    screen.blit(hint, (W // 2 - hint.get_width() // 2, bar_y - 22))  # 置中提示文字
    # 新增：含抽卡堆，多一張
    hand_count = min(len(hand), 8)
    total_w = (hand_count + 1) * slot_w + (hand_count) * gap  # 多一張抽卡堆
    start_x = (W - total_w) // 2
    y = bar_y + (bar_h - slot_h) // 2

    bg_img = BG_CARD_IMG

    # 先畫最左的「抽卡堆」圖示
    draw_x = start_x
    deck_rect = pygame.Rect(draw_x, y, slot_w, slot_h)
    # 畫卡底或藍色光框
    # ===== 抽卡背面圖處理 =====
    if bg_img:
        # 使用 slot size
        deck_img_w, deck_img_h = slot_w, slot_h
        scaled_bg = pygame.transform.smoothscale(bg_img, (deck_img_w, deck_img_h))

        # 把它放在 deck_rect 的中間，但略往上移一點
        deck_img_x = deck_rect.centerx - deck_img_w // 2
        deck_img_y = deck_rect.centery - deck_img_h // 2 - 5  # ← 向上 10px
        screen.blit(scaled_bg, (deck_img_x, deck_img_y))
    else:
        # 沒有圖就畫藍色光框
        pygame.draw.rect(screen, (31, 42, 68), deck_rect, border_radius=10)
        pygame.draw.rect(screen, (50, 120, 255), deck_rect, 4, border_radius=10)
    # 上方加文字
    deck_label = SMALL.render("抽卡區", True, (180, 210, 255))
    deck_label_x = deck_rect.centerx - deck_label.get_width() // 2
    deck_label_y = deck_rect.top - deck_label.get_height() + 6
    screen.blit(deck_label, (deck_label_x, deck_label_y))
    # deck_rect 不加入 HAND_UI_RECTS，避免被點選

    draw_x += slot_w + gap

    # 畫手牌
    for i, name in enumerate(hand[:8]):
        rect = pygame.Rect(draw_x, y, slot_w, slot_h)
        HAND_UI_RECTS.append((rect, i))

        # 卡面圖
        img = get_card_scaled(name)
        if img:
            ir = img.get_rect(center=(rect.centerx, rect.centery))
            screen.blit(img, ir)
        else:
            label = FONT.render(name[:6], True, (235, 242, 255))
            screen.blit(label, (rect.x + 6, rect.y + 6))

        # 選取高亮框
        if selected_card == i:
            pygame.draw.rect(screen, (255, 240, 160), rect, 4, border_radius=10)

        draw_x += slot_w + gap

# =========================
# 主選單繪製
def draw_main_menu():
    screen.fill((16, 20, 35))
    if BG_IMG:
        screen.blit(BG_IMG, (0,0))
        # 蓋一層半透明深色讓文字更清楚
        dim = pygame.Surface((W,H), pygame.SRCALPHA); dim.fill((0,0,0,120)); screen.blit(dim,(0,0))
    if LOGO_IMG:
        lr = LOGO_IMG.get_rect()
        lr.midtop = (W//2, 40)
        screen.blit(LOGO_IMG, lr)
    title = BIG.render("塔路之戰 - 作者：Ethan.Kao", True, (250, 245, 255))
    subtitle = FONT.render("Tower Defense - 主選單", True, (190, 200, 220))
    screen.blit(title, (W//2 - title.get_width()//2, 120))
    screen.blit(subtitle, (W//2 - subtitle.get_width()//2, 160))
    if IS_WEB:
        hint = FONT.render("(Web) 點擊開始後才會啟用音效，屬於瀏覽器限制", True, (200, 208, 224))
        screen.blit(hint, (W//2 - hint.get_width()//2, 180))

    # 計算三個按鈕位置
    cx = W//2 - BTN_W//2
    y0 = 240
    buttons = [
        ("開始遊戲 (Enter)", cx, y0),
        ("操作說明 (H)",     cx, y0 + BTN_H + BTN_GAP),
        ("離開 (Esc)",       cx, y0 + (BTN_H + BTN_GAP)*2)
    ]
    mx, my = pygame.mouse.get_pos()
    for text, bx, by in buttons:
        r = pygame.Rect(bx, by, BTN_W, BTN_H)
        hover = r.collidepoint(mx, my)
        pygame.draw.rect(screen, (40, 55, 96) if hover else (31, 42, 68), r, border_radius=8)
        pygame.draw.rect(screen, (90, 120, 200), r, 2, border_radius=8)
        label = FONT.render(text, True, (235, 242, 255))
        screen.blit(label, (bx + (BTN_W - label.get_width())//2, by + (BTN_H - label.get_height())//2))

    tip = FONT.render("Enter/Space 開始｜H 說明｜Esc 離開", True, (200, 208, 224))
    screen.blit(tip, (W//2 - tip.get_width()//2, H - 80))


def draw_help_screen():
    screen.fill((16, 20, 35))
    if BG_IMG:
        screen.blit(BG_IMG, (0,0))
        dim = pygame.Surface((W,H), pygame.SRCALPHA); dim.fill((0,0,0,120)); screen.blit(dim,(0,0))
    title = BIG.render("操作說明", True, (250, 245, 255))
    screen.blit(title, (W//2 - title.get_width()//2, 120))
    lines = [
        "D抽卡  左鍵使用卡片建塔/升級｜S 回收｜C 升級主堡",
        "可抽到：普通塔(10)、元素卡(5)、升級卡(0)，升級卡可將任一塔升到最高 Lv3",
        "1/2/3 調整速度",
        "每波開始前：右上顯示開始/暫停，紅箭頭預告下一個 S 出口",
        "清空當波怪物後，才會顯示下一波預告",
        "按 Enter/Space 回到遊戲，或 Esc 返回主選單"
    ]
    y = 180
    for ln in lines:
        t = FONT.render(ln, True, (220, 228, 240))
        screen.blit(t, (W//2 - t.get_width()//2, y))
        y += 30

def draw_map():
    for r in range(ROWS):
        for c in range(COLS):
            x, y = grid_to_px(r, c)
            rect = pygame.Rect(x, y, CELL, CELL)
            s = pygame.Surface((CELL, CELL), pygame.SRCALPHA)

            # 先畫底色：依 MAP 值決定
            if MAP[r][c] == 1:
                s.fill(ROAD)
            elif MAP[r][c] == 0:
                s.fill(LAND)
            elif MAP[r][c] == 3:
                s.fill(GREY)
            else:  # 2 = 牆/障礙（含主堡格視覺顯示）
                s.fill(BLOCK)
            screen.blit(s, rect)

            # 覆蓋主堡 / 牆壁圖示
            if (r == CASTLE_ROW and c == CASTLE_COL) and CASTLE_IMG:
                img_rect = CASTLE_IMG.get_rect(center=(x + CELL//2, y + CELL//2))
                screen.blit(CASTLE_IMG, img_rect)
            elif MAP[r][c] == 2 and WALL_IMG:
                # 非主堡的 2 都當牆壁圖示
                img_rect = WALL_IMG.get_rect(center=(x + CELL//2, y + CELL//2))
                screen.blit(WALL_IMG, img_rect)

            # 格線
            pygame.draw.rect(screen, GRID, rect, 1)
            # 預告箭頭：在下一波的 S 出口上方顯示
            if not wave_incoming and next_spawn:
                if (r, c) == next_spawn and ARROW_IMG:
                    ar = ARROW_IMG.get_rect(center=(x + CELL//2, y + CELL//2))
                    screen.blit(ARROW_IMG, ar)

def draw_selection():
    if not sel: return
    x,y = grid_to_px(sel[0], sel[1]); pygame.draw.rect(screen, CYAN, (x+1,y+1,CELL-2,CELL-2), 2)

def draw_tower_icon(t):
    # t: {'r','c','level','type',...}
    r, c = t['r'], t['c']
    level = t.get('level', 0)
    ttype = t.get('type', 'arrow')
    x, y = grid_to_px(r, c)
    cx, cy = x + CELL//2, y + CELL//2

    # 若有元素，優先用對應的元素圖示覆蓋顯示
    elem = t.get('element')
    if elem:
        elem_img = {
            'fire':  FIRE_TOWER_IMG,
            'water': WATER_TOWER_IMG,
            'land':  LAND_TOWER_IMG,
            'wind':  WIND_TOWER_IMG,
        }.get(elem)
        if elem_img:
            rect = elem_img.get_rect(center=(cx, cy))
            screen.blit(elem_img, rect)
            return

    if ttype == 'rocket':
        if 'ROCKET_TOWER_IMG' in globals() and ROCKET_TOWER_IMG:
            rect = ROCKET_TOWER_IMG.get_rect(center=(cx, cy))
            screen.blit(ROCKET_TOWER_IMG, rect)
        else:
            pygame.draw.circle(screen, (220,80,60), (cx, cy), CELL//2 - 6)
        return
    else:
        # arrow：先嘗試用等級圖示，否則退回程式繪圖
        img = TOWER_IMGS.get(level)
        if img:
            rect = img.get_rect(center=(cx, cy))
            screen.blit(img, rect)
            return
        # 備援：原本程式繪圖
        body_h = 18 if level<2 else 22
        body_y = y + CELL//2 - body_h//2 + (-4 if level>=2 else 0)
        rect = pygame.Rect(cx-14, body_y, 28, body_h)
        pygame.draw.rect(screen, (91,100,116), rect, border_radius=6)
        pygame.draw.rect(screen, (25,30,43), rect, 2, border_radius=6)
        pygame.draw.line(screen, (67,74,90), (rect.left, rect.centery), (rect.right, rect.centery), 2)
        if level>=2:
            top = pygame.Rect(cx-14, rect.top-10, 28, 10)
            pygame.draw.rect(screen, (91,100,116), top); pygame.draw.rect(screen, (25,30,43), top, 2)
            for i in range(4):
                cren = pygame.Rect(cx-12 + i*6, rect.top-14, 4, 6)
                pygame.draw.rect(screen, (91,100,116), cren); pygame.draw.rect(screen, (25,30,43), cren, 2)
        pts = [(cx, y+6), (cx-16, rect.top+2), (cx+16, rect.top+2)]
        pygame.draw.polygon(screen, (230,127,57), pts); pygame.draw.polygon(screen, (25,30,43), pts, 2)

def draw_monster_icon(m):
    mtype = m.get('type', 'slime')
    x,y = grid_to_px(int(m['r']), int(m['c']))
    cx, cy = x + CELL//2, y + CELL//2
    color = CREEP.get(mtype, {}).get('color', (200, 200, 200))
    if mtype == "runner":
        if RUNNER_IMG:
            rect = RUNNER_IMG.get_rect(center=(cx, cy))
            screen.blit(RUNNER_IMG, rect)
        else:
            pts = [(cx-14,cy+8),(cx-4,cy-8),(cx+18,cy-2),(cx+10,cy+10)]
            pygame.draw.polygon(screen, color, pts); pygame.draw.polygon(screen, (15,19,32), pts, 2)
            pygame.draw.circle(screen, (255,255,255), (cx-2,cy-4), 3); pygame.draw.circle(screen, (255,255,255), (cx+6,cy-6), 3)
    elif mtype == "brute":
        if BRUTE_IMG:
            rect = BRUTE_IMG.get_rect(center=(cx, cy))
            screen.blit(BRUTE_IMG, rect)
        else:
            pygame.draw.rect(screen, color, (cx-18,cy-8,36,22), border_radius=8)
            pygame.draw.rect(screen, (15,19,32), (cx-18,cy-8,36,22), 2, border_radius=8)
            pygame.draw.rect(screen, color, (cx-10,cy-18,20,12), border_radius=6)
    elif mtype == "bat":
        if BAT_IMG:
            rect = BAT_IMG.get_rect(center=(cx, cy))
            screen.blit(BAT_IMG, rect)
        else:
            wing_span = CELL//2
            pts = [(cx-wing_span, cy), (cx, cy-10), (cx+wing_span, cy), (cx, cy+10)]
            pygame.draw.polygon(screen, color, pts); pygame.draw.polygon(screen, (15,19,32), pts, 2)
            pygame.draw.circle(screen, (255, 255, 255), (cx-4, cy-2), 3)
            pygame.draw.circle(screen, (255, 255, 255), (cx+4, cy-2), 3)
    elif mtype == "boss":
        if BOSS_IMG:
            rect = BOSS_IMG.get_rect(center=(cx, cy))
            screen.blit(BOSS_IMG, rect)
        else:
            pygame.draw.circle(screen, color, (cx,cy), 16); pygame.draw.circle(screen, (15,19,32), (cx,cy), 16, 2)
            pygame.draw.circle(screen, (167,139,250), (cx,cy-2), 12); pygame.draw.circle(screen, (15,19,32), (cx,cy-2), 12, 2)
    elif mtype == "slime":
        if 'SLIME_IMG' in globals() and SLIME_IMG:
            rect = SLIME_IMG.get_rect(center=(cx, cy))
            screen.blit(SLIME_IMG, rect)
        else:
            r = GRUNT_RADIUS
            pygame.draw.circle(screen, color, (cx, cy-2), r)
            pygame.draw.circle(screen, (15,19,32), (cx, cy-2), r, GRUNT_OUTLINE_W)
    else:
        if MONSTER_IMG:
            rect = MONSTER_IMG.get_rect(center=(cx, cy))
            screen.blit(MONSTER_IMG, rect)
        else:
            r = GRUNT_RADIUS
            pygame.draw.circle(screen, GRUNT_FILL, (cx, cy-2), r)
            pygame.draw.circle(screen, GRUNT_OUTLINE, (cx, cy-2), r, GRUNT_OUTLINE_W)
            mouth_rect = pygame.Rect(cx - r//2, cy - 2, r, r//2)
            pygame.draw.arc(screen, (255, 230, 180), mouth_rect, math.radians(20), math.radians(160), 2)

def draw_bullets():
    for b in bullets:
        if len(b['trail'])>=2:
            pygame.draw.lines(screen, (180,190,200), False, b['trail'], 2)
        pygame.draw.circle(screen, WHITE, (int(b['x']), int(b['y'])), 3)

def draw_hits():
    alive = []
    for h in hits:
        life_ratio = h['ttl'] / 12.0
        alpha = max(0, min(255, int(255 * life_ratio)))
        if BLAST_IMG:
            scale = 1.0 + (1.0 - life_ratio) * 0.3  # 命中瞬間稍微變大
            size = int(HIT_IMG_SIZE * scale)
            img = pygame.transform.smoothscale(BLAST_IMG, (size, size)).copy()
            img.set_alpha(alpha)
            rect = img.get_rect(center=(h['x'], h['y']))
            screen.blit(img, rect)
        else:
            # 備援：舊版小爆光
            s = pygame.Surface((16,16), pygame.SRCALPHA)
            pygame.draw.circle(s, (255,240,180, alpha), (8,8), 6)
            screen.blit(s, (h['x']-8, h['y']-8))

        if 'dmg' in h:
            dmg = h['dmg']
            dmg_text = f"{int(dmg)}"
            color = h.get('color', (255, 200, 120))
            text_surf = SMALL.render(dmg_text, True, color)
            text_surf.set_alpha(alpha)
            float_up = (1.0 - life_ratio) * 18
            text_rect = text_surf.get_rect()
            text_rect.midleft = (h['x'] + 18, h['y'] - float_up)
            screen.blit(text_surf, text_rect)

        h['ttl'] -= 1
        if h['ttl'] > 0:
            alive.append(h)
    hits[:] = alive

def draw_corpses():
    # 死亡圖示：逐步淡出 + 輕微縮放（若無圖片則畫簡易符號）
    alive = []
    for d in corpses:
        life_ratio = d['ttl'] / 24.0
        alpha = max(0, min(255, int(255 * life_ratio)))
        if DEAD_IMG:
            scale = 1.0 + (1.0 - life_ratio) * 0.1
            size = int(DEATH_IMG_SIZE * scale)
            img = pygame.transform.smoothscale(DEAD_IMG, (size, size)).copy()
            img.set_alpha(alpha)
            rect = img.get_rect(center=(d['x'], d['y']))
            screen.blit(img, rect)
        else:
            # 備援：簡單表情
            r = 16
            face = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(face, (255, 210, 60, alpha), (r, r), r)
            # X 眼
            pygame.draw.line(face, (20,20,20,alpha), (6,8), (14,16), 3)
            pygame.draw.line(face, (20,20,20,alpha), (14,8), (6,16), 3)
            pygame.draw.line(face, (20,20,20,alpha), (r+6,8), (r+14,16), 3)
            pygame.draw.line(face, (20,20,20,alpha), (r+14,8), (r+6,16), 3)
            # 吐舌
            pygame.draw.rect(face, (230, 100, 70, alpha), (r-4, r+2, 10, 8), border_radius=3)
            screen.blit(face, (d['x']-r, d['y']-r))
        d['ttl'] -= 1
        if d['ttl'] > 0:
            alive.append(d)
    corpses[:] = alive


def draw_gains():
    # 擊殺彈出：小金幣 + "+數字"，向上飄並淡出
    alive = []
    for g in gains:
        g['y'] -= GAIN_RISE
        life_ratio = g['ttl'] / float(GAIN_TTL)
        alpha = max(0, min(255, int(255 * life_ratio)))
        x, y = int(g['x']), int(g['y'])
        # 圖示
        if COIN_IMG:
            coin = COIN_IMG.copy(); coin.set_alpha(alpha)
            rect = coin.get_rect(center=(x, y))
            screen.blit(coin, rect)
            text_x = rect.right + 6; text_y = rect.centery
        else:
            text_x = x; text_y = y
        # 文字
        txt = FONT.render(f"+{g['amt']}", True, GAIN_TEXT_COLOR)
        try:
            txt.set_alpha(alpha)
        except Exception:
            pass
        screen.blit(txt, (text_x, text_y - txt.get_height()//2))
        g['ttl'] -= 1
        if g['ttl'] > 0:
            alive.append(g)
    gains[:] = alive

def upgrade_castle():
    global gold, CASTLE
    cost = CASTLE['upgrade_cost']
    if gold < cost:
        add_notice(f"金幣不足：升級主堡需要 ${cost}", (255,120,120))
        return
    gold -= cost
    CASTLE['level'] += 1
    CASTLE['max_hp'] += CASTLE['hp_increase']
    CASTLE['hp'] = CASTLE['max_hp']  # 回滿血
    CASTLE['upgrade_cost'] = int(cost * 1.5)  # 每次升級成本上升
    add_notice(f"主堡升級至 Lv{CASTLE['level']}！血量上限 {CASTLE['max_hp']}", (180,235,160))
    sfx(SFX_LEVELUP)
# 每一波擊殺金幣提升：比上一波多 1%
# 例：第 1 波=1.01x，第 10 波≈1.1046x
def reward_for(kind):
    base = CREEP.get(kind, {}).get('reward', 1)
    mult = 1.01 ** max(0, int(wave))  # 與血量一致：用 1.01 ** wave
    return max(1, int(round(base * mult)))
def draw_upgrades():
    # 升級特效：在塔的位置顯示 LevelUp 圖示，往上飄並淡出
    alive = []
    for u in upgrades:
        u['y'] -= LEVELUP_RISE
        life_ratio = u['ttl'] / float(LEVELUP_TTL)
        alpha = max(0, min(255, int(255 * life_ratio)))
        if LEVELUP_IMG:
            img = LEVELUP_IMG.copy(); img.set_alpha(alpha)
            rect = img.get_rect(center=(int(u['x']), int(u['y'])))
            screen.blit(img, rect)
        else:
            # 備援：綠色箭頭 + 文字
            txt = BIG.render("LEVEL UP", True, (80, 220, 120))
            txt.set_alpha(alpha)
            screen.blit(txt, (int(u['x']-txt.get_width()/2), int(u['y']-txt.get_height()/2)))
        u['ttl'] -= 1
        if u['ttl'] > 0:
            alive.append(u)
    upgrades[:] = alive

def get_creep_by_id(cid):
    for m in creeps:
        if m['id']==cid: return m
    return None

def tower_fire(t):
    global gold
    ttype = t.get('type', 'arrow')
    stat = TOWER_TYPES[ttype][t['level']]
    in_range = [m for m in creeps if m['alive'] and manhattan((t['r'], t['c']), (int(m['r']), int(m['c']))) <= stat['range']]
    if not in_range: return

    # 特殊塔行為

    # 一般與火箭塔共用射擊邏輯
    target = sorted(in_range, key=lambda m: m['r'])[0]
    sx, sy = center_px(t['r'], t['c'])
    tx, ty = center_px(target['r'], int(target['c']))
    dx, dy = tx - sx, ty - sy
    length = math.hypot(dx, dy) or 1.0
    spd = 8.0
    vx, vy = dx / length * spd, dy / length * spd
    sfx(SFX_SHOOT)
    bullets.append({
        'x': sx, 'y': sy, 'vx': vx, 'vy': vy,
        'dmg': stat['atk'] * (1.5 if ttype == 'rocket' else 1),
        'target_id': target['id'],
        'ttl': 120, 'trail': [(sx, sy)],
        'aoe': (ttype == 'rocket'),
        'element': t.get('element'),
        'tlevel': t.get('level', 0)
    })

def spawn_logic():
    """
    依 get_wave_creeps(wave) 建立本波出怪佇列，並按 SPAWN_INTERVAL 出怪。
    - 每 10 波：只會有 1 隻 boss（在 get_wave_creeps 已處理）
    - 其他波：總數量介於 10~20，種類隨機（在 get_wave_creeps 已處理）
    - 血量每波 +1%，速度每波 +3%
    """
    global spawn_counter, wave_incoming, creeps, ids
    global next_spawn, current_spawn, wave_spawn_queue

    if not wave_incoming:
        return

    # 首次進入本波：建立出怪佇列 & 確認本波出口
    if spawn_counter == 0 and not wave_spawn_queue:
        plan = get_wave_creeps(wave)  # 例如 [{'type':'slime','count':5}, {'type':'runner','count':3}]
        wave_spawn_queue = []
        for item in plan:
            ctype = item.get('type')
            cnt   = int(item.get('count', 1))
            for _ in range(max(1, cnt)):
                wave_spawn_queue.append(ctype)

        # 非 boss-only 波才洗牌
        if not (wave > 0 and wave % 10 == 0):
            random.shuffle(wave_spawn_queue)

        # 決定本波出怪口：沿用先前指定；若有預告則覆寫；最後才隨機
        if next_spawn is not None:
            current_spawn = next_spawn
        elif current_spawn is None:
            current_spawn = random.choice(SPAWNS) if SPAWNS else (ROWS-1, COLS//2)
        next_spawn = None  # 用掉預告

    # 到點出怪
    if spawn_counter % SPAWN_INTERVAL == 0 and wave_spawn_queue:
        kind = wave_spawn_queue.pop(0)

        # 從設定讀取基礎屬性（缺就用舊 CREEP 值當備援）
        cfg = CREEP_CONFIG.get(kind, {})
        base_hp    = int(cfg.get('hp',     CREEP.get(kind, {}).get('hp', 10)))
        base_speed = float(cfg.get('speed', CREEP.get(kind, {}).get('speed', 0.02)))
        reward     = int(cfg.get('reward', CREEP.get(kind, {}).get('reward', 1)))

        sr, sc = current_spawn if current_spawn else (SPAWNS[0] if SPAWNS else (ROWS-1, COLS//2))
        route  = PATHS.get((sr, sc)) or [(sr, sc), (CASTLE_ROW, CASTLE_COL)]

        # 成長：血量每波 +1%，速度每波 +3%
        hp_scaled  = max(1, int(round(base_hp * (1.01 ** max(0, int(wave))))))
        spd_scaled = base_speed * (1.0 + 0.03 * max(0, int(wave)))

        creeps.append({
            'id': ids['creep'],
            'type': kind,
            'r': float(sr), 'c': float(sc),
            'wp': 1, 'route': route,
            'hp': hp_scaled, 'alive': True,
            'speed': spd_scaled, 'reward': reward,
            'effects': {},
            'rewarded': False
        })
        ids['creep'] += 1

    spawn_counter += 1

    # 本波結束條件：佇列清空後就結束本波（預告在主循環「怪清空」時抽）
    if not wave_spawn_queue and spawn_counter > 0:
        wave_incoming = False
        spawn_counter = 0
        # 不立刻抽 next_spawn，讓主循環在「怪物清空」後再抽（你已有這段邏輯）

def move_creeps():
    global life, creeps
    alive = []
    for m in creeps:
        if not m['alive']:
            continue
        # 狀態效果處理（DOT、緩速）
        eff = m.get('effects') or {}
        # DOT：burn / bleed 每 10 幀扣一次血
        for key in ('burn','bleed'):
            e = eff.get(key)
            if e:
                e['ttl'] -= 1
                e['acc'] = e.get('acc', 0) + 1
                if e['acc'] >= e.get('tick', 10):
                    e['acc'] = 0
                    m['hp'] -= max(1, int(e.get('dmg', 1)))
                    if m['hp'] <= 0:
                        m['alive'] = False
                        cx, cy = center_px(m['r'], int(m['c']))
                        corpses.append({'x': cx, 'y': cy, 'ttl': 24})
                        reward_amt = reward_for(m['type'])
                        gains.append({'x': cx, 'y': cy - 6, 'ttl': GAIN_TTL, 'amt': reward_amt})
                        global gold
                        gold += reward_amt
                        m['rewarded'] = True
                        sfx(SFX_DEATH); sfx(SFX_COIN)
                        eff[key] = None
                        break
                if e['ttl'] <= 0:
                    eff[key] = None
        # 移除過期 None
        for k in list(eff.keys()):
            if not eff[k]:
                eff.pop(k, None)
        # 緩速：在本幀速度上套用
        slow_ratio = 1.0
        if 'slow' in eff and eff['slow'] and eff['slow']['ttl'] > 0:
            eff['slow']['ttl'] -= 1
            slow_ratio = min(slow_ratio, eff['slow'].get('ratio', 0.6))
            if eff['slow']['ttl'] <= 0:
                eff.pop('slow', None)
        #--
        route = m.get('route')
        wp = m.get('wp', 1)

        # 沒路徑就保險直線上移
        if not route or wp >= len(route):
            m['r'] -= m['speed']
            if int(m['r']) <= CASTLE_ROW:
                dmg = (3 if m['type'] == 'boss' else 1)
                CASTLE['hp'] = max(0, CASTLE['hp'] - dmg)
                add_notice(f"主堡受攻擊！-{dmg} HP", (255,100,100))
                if CASTLE['hp'] <= 0:
                    life = 0  # 觸發遊戲結束
            else:
                alive.append(m)
            continue

        tr, tc = route[wp]
        dr, dc = tr - m['r'], tc - m['c']
        dist = math.hypot(dr, dc)
        step = m['speed'] * slow_ratio  # 單位：格/幀

        if dist <= step:
            # 到達當前 waypoint
            m['r'], m['c'] = float(tr), float(tc)
            m['wp'] = wp + 1
            if m['wp'] >= len(route):  # 到達終點（城堡）
                dmg = (3 if m['type'] == 'boss' else 1)
                CASTLE['hp'] = max(0, CASTLE['hp'] - dmg)
                add_notice(f"主堡受攻擊！-{dmg} HP", (255,100,100))
                if CASTLE['hp'] <= 0:
                    life = 0  # 觸發遊戲結束
            else:
                alive.append(m)
        else:
            # 朝 waypoint 前進
            m['r'] += (dr / dist) * step
            m['c'] += (dc / dist) * step
            alive.append(m)
    creeps[:] = alive
    # Fallback: ensure any newly-dead creeps grant rewards once
    for m in creeps:
        if (not m.get('alive')) and (not m.get('rewarded')):
            cx, cy = center_px(m['r'], int(m['c']))
            reward_amt = reward_for(m.get('type', 'slime'))
            gains.append({'x': cx, 'y': cy - 6, 'ttl': GAIN_TTL, 'amt': reward_amt})
            gold += reward_amt
            m['rewarded'] = True
            sfx(SFX_COIN)
def towers_step():
    for t in towers:
        stat = TOWER_TYPES[t.get('type','arrow')][t['level']]
        cd_need = max(1, int(30 / stat['rof']))
        t['cool'] = t.get('cool',0) + 1
        if t['cool'] >= cd_need:
            tower_fire(t)
            t['cool']=0

def bullets_step():
    global gold
    alive = []
    for b in bullets:
        b['x'] += b['vx']; b['y'] += b['vy']
        if len(b['trail'])==0 or (abs(b['trail'][-1][0]-b['x'])+abs(b['trail'][-1][1]-b['y']))>2:
            b['trail'].append((b['x'], b['y'])); 
            if len(b['trail'])>8: b['trail'].pop(0)
        b['ttl'] -= 1
        target = get_creep_by_id(b['target_id'])
        if target and target['alive']:
            tx, ty = center_px(target['r'], int(target['c']))
            if math.hypot(b['x']-tx, b['y']-ty) < 10:
                target['hp'] -= b['dmg']; hits.append({'x':tx,'y':ty,'ttl':12,'dmg': b['dmg']}); sfx(SFX_HIT)
                if target['hp'] <= 0:
                    target['alive'] = False
                    corpses.append({'x': tx, 'y': ty, 'ttl': 24})
                    reward_amt = reward_for(target['type'])
                    gains.append({'x': tx, 'y': ty - 6, 'ttl': GAIN_TTL, 'amt': reward_amt})
                    gold += reward_amt
                    target['rewarded'] = True
                    sfx(SFX_DEATH); sfx(SFX_COIN)
                continue
            # 元素效果（單體）
            if b.get('element') in ('water','land','wind','fire'):
                ecfg = _get_elem_cfg(b['element'], b.get('tlevel',0))
                if ecfg:
                    if ecfg.get('type') == 'knockback':
                        _do_knockback(target, ecfg.get('grids',1))
                    else:
                        _apply_status_on_hit(target, ecfg, b['dmg'])
            if b.get('aoe'):
                ax, ay = tx, ty
                radius = 60
                for m in list(creeps):
                    if (not m['alive']) or m['id'] == target['id']:
                        continue
                    mx, my = center_px(m['r'], int(m['c']))
                    if math.hypot(mx-ax, my-ay) <= radius:
                        splash_dmg = max(1, int(round(b['dmg'] * 0.6)))
                        m['hp'] -= splash_dmg
                        hits.append({'x': mx, 'y': my, 'ttl': 8, 'dmg': splash_dmg})
                        # 火元素：爆炸附帶灼傷
                        ecfg = _get_elem_cfg('fire', b.get('tlevel',0))
                        _apply_status_on_hit(m, ecfg, b['dmg'])
                        if m['hp'] <= 0:
                            m['alive'] = False
                            corpses.append({'x': mx, 'y': my, 'ttl': 24})
                            reward_amt = reward_for(m['type'])
                            gains.append({'x': mx, 'y': my - 6, 'ttl': GAIN_TTL, 'amt': reward_amt})
                            gold += reward_amt
                            m['rewarded'] = True
                            sfx(SFX_DEATH); sfx(SFX_COIN)
        if 0 <= b['x'] <= W and 0 <= b['y'] <= H and b['ttl']>0: alive.append(b)
    bullets[:] = alive

    # Fallback: ensure any newly-dead creeps grant rewards once
    for m in creeps:
        if (not m.get('alive')) and (not m.get('rewarded')):
            cx, cy = center_px(m['r'], int(m['c']))
            reward_amt = reward_for(m.get('type', 'slime'))
            gains.append({'x': cx, 'y': cy - 6, 'ttl': GAIN_TTL, 'amt': reward_amt})
            gold += reward_amt
            m['rewarded'] = True
            sfx(SFX_COIN)

def draw_world():
    draw_map()
    for t in towers: draw_tower_icon(t)
    draw_upgrades()
    for m in creeps: draw_monster_icon(m)
    draw_bullets(); draw_hits(); draw_corpses(); draw_gains(); draw_selection()

def add_tower(r,c):
    global gold, towers, ids
    cost = get_build_cost('arrow')
    # 不可建地、已有塔
    if (not is_buildable(r,c)) or any(t['r']==r and t['c']==c for t in towers):
        return
    if gold < cost:
        add_notice(f"金幣不足：建塔需要 ${cost}", (255, 120, 120))
        return
    gold -= cost
    towers.append({'id': ids['tower'], 'r': r, 'c': c, 'type': 'arrow', 'level': 0, 'cool': 0})
    ids['tower'] += 1
    add_notice(f"- ${cost} 建造箭塔", (160, 235, 170))

def upgrade_tower_at(r, c):
    global gold, towers
    for t in towers:
        if t['r']==r and t['c']==c:
            # 進化點：箭塔等級2再升級→分支（需額外收費）
            if t['type'] == 'arrow' and t['level'] == 2:
                # 進化為分支塔需要花費
                branch = random.choice(['rocket', 'thunder'])
                evolve_cost = get_evolve_cost(branch)
                if gold < evolve_cost:
                    add_notice(f"金幣不足：進化為 {branch} 需要 ${evolve_cost}", (255,120,120))
                    return
                gold -= evolve_cost
                t['type'] = branch
                t['level'] = 0
                cx, cy = center_px(r, c)
                upgrades.append({'x': cx, 'y': cy - 8, 'ttl': LEVELUP_TTL})
                sfx(SFX_LEVELUP)
                add_notice(f"- ${evolve_cost} 進化成功：{branch} 塔", (170, 220, 255))
                return
            # 一般升級費用
            cost = get_upgrade_cost(t)
            if cost is None:
                return
            if gold < cost:
                add_notice(f"金幣不足：升級需要 ${cost}", (255, 120, 120))
                return
            gold -= cost
            t['level'] += 1
            cx, cy = center_px(r, c)
            upgrades.append({'x': cx, 'y': cy - 8, 'ttl': LEVELUP_TTL})
            sfx(SFX_LEVELUP)
            add_notice(f"- ${cost} 升級完成 (Lv{t['level']})", (160, 235, 170))
            return

def sell_tower_at(r,c):
    global gold, towers
    for i,t in enumerate(towers):
        if t['r']==r and t['c']==c:
            refund = max(1, BUILD_COST - 1) + t['level']
            gold += refund
            towers.pop(i)
            add_notice(f"+ ${refund} 回收防禦塔", (255, 230, 120))
            return

def next_wave():
    global wave, wave_incoming, spawn_counter, current_spawn, next_spawn
    if wave_incoming: return
    wave += 1
    wave_incoming = True
    spawn_counter = 0
    # 使用預告的出口，若沒有則抽一個
    if next_spawn:
        current_spawn = next_spawn
        next_spawn = None
    else:
        current_spawn = random.choice(SPAWNS) if SPAWNS else (ROWS-1, COLS//2)

def reset_game():
    global running, tick, gold, life, wave, wave_incoming, spawn_counter, towers, creeps, bullets, hits, corpses, gains, upgrades
    running=False; tick=0; gold=100; life=20; wave=0; wave_incoming=False; spawn_counter=0
    towers=[]; creeps=[]; bullets=[]; hits=[]; corpses=[]; gains=[]; upgrades=[]
    towers=[]; creeps=[]; bullets=[]; hits=[]; corpses=[]; gains=[]; upgrades=[]
    globals()['current_spawn'] = None
    globals()['current_spawn'] = None
    globals()['next_spawn'] = None
    init_starting_hand()
    # 重置主堡狀態
    CASTLE['level'] = 1
    CASTLE['max_hp'] = 50
    CASTLE['hp'] = CASTLE['max_hp']
    CASTLE['upgrade_cost'] = 20
#新模式0.0.4 抽卡系統------
def can_draw_card():
    # 僅當沒有怪物且不在出怪狀態時才允許抽卡，且金幣足夠
    return (not wave_incoming) and (len(creeps) == 0) and (gold >= CARD_COST_DRAW)

def draw_card():
    global gold, hand, effects

    # 僅在「非出怪」且「場上無怪」且「金幣足夠」時可抽卡
    if not can_draw_card():
        add_notice("現在不可抽卡：需等該波結束且金幣足夠", (255, 180, 120))
        sfx(SFX_CLICK)
        return

    # 手牌滿：不允許抽卡也不扣費
    if len(hand) >= MAX_HAND_CARDS:
        add_notice("⚠️ 手牌已滿，無法抽卡。", (255, 120, 120))
        sfx(SFX_CLICK)
        return

    # 抽卡花費
    if gold < CARD_COST_DRAW:
        add_notice(f"金幣不足：抽卡需要 ${CARD_COST_DRAW}", (255,120,120))
        sfx(SFX_CLICK)
        return
    gold -= CARD_COST_DRAW

    # 隨機抽卡（權重決定機率）
    rates = _get_card_rates()
    card_type = random.choices(
        [c['type'] for c in rates],
        weights=[c['weight'] for c in rates]
    )[0]

    # 播放抽卡音效
    sfx(SFX_CLICK)
    try:
        sfx(SFX_DRAW)
    except Exception:
        pass
    effects.append({'type': 'flip', 'timer': 20, 'total': 20, 'img_from': BG_CARD_IMG, 'img_to_name': card_type, 'pos': (W//2, H//2)})

    # === 金幣卡立即生效 ===
    money_gain = 0
    if card_type == '1money':
        money_gain = 1
    elif card_type == '2money':
        money_gain = 2
    elif card_type == '3money':
        money_gain = 3

    if False and money_gain > 0:
        gold += money_gain
        add_notice(f"💰 獲得金幣 +{money_gain}！", (255, 236, 140))
        sfx(SFX_COIN)
        # 視覺效果：中心閃光
        effects.append({
            'type': 'flash',
            'timer': 20,
            'color': (255, 255, 100),
            'alpha': 200,
            'radius': 80,
            'pos': (W//2, H//2)
        })
        # 閃光特效
        effects.append({
            'type': 'flash',
            'timer': 20,              # 持續 20 frame
            'color': (255, 255, 100),
            'alpha': 200,
            'radius': 80,
            'pos': (W//2, H//2)
        })
        return  # 金幣卡不進手牌

    # === 其他卡：加入手牌 ===
    if len(hand) < MAX_HAND_CARDS:
        hand.append(card_type)
        add_notice(f"抽到『{_card_display_name(card_type)}』", (180, 220, 255))
    else:
        add_notice("⚠️ 手牌已滿，無法抽卡。", (255, 120, 120))
def draw_effects():
    remove_fx = []
    for fx in effects:
        if fx.get('type') == 'flash':
            s = pygame.Surface((W, H), pygame.SRCALPHA)
            # 以剩餘時間做淡出
            life_ratio = max(0.0, min(1.0, fx.get('timer', 0) / 20.0))
            alpha = int(fx.get('alpha', 200) * life_ratio)
            color = fx.get('color', (255,255,100))
            pos   = fx.get('pos', (W//2, H//2))
            radius = fx.get('radius', 80)
            pygame.draw.circle(s, (*color, alpha), pos, radius)
            screen.blit(s, (0, 0))
            fx['timer'] = fx.get('timer', 0) - 1
            if fx['timer'] <= 0:
                remove_fx.append(fx)
        elif fx.get('type') == 'flip':
            total = fx.get('total', 20)
            timer = fx.get('timer', total)
            progress = 1.0 - max(0.0, min(1.0, float(timer) / float(total)))
            import math as _m
            scale_x = max(0.05, abs(_m.cos(progress * _m.pi)))
            pos = fx.get('pos', (W//2, H//2))
            img = fx.get('img_from') if progress < 0.5 else get_card_scaled(fx.get('img_to_name', 'basic'))
            slot_w, slot_h = CARD_SLOT_SIZE
            if img is None:
                w = max(1, int(slot_w * scale_x)); h = slot_h
                rect = pygame.Rect(0, 0, w, h); rect.center = pos
                pygame.draw.rect(screen, (31, 42, 68), rect, border_radius=10)
                pygame.draw.rect(screen, (50, 120, 255), rect, 2, border_radius=10)
            else:
                base = pygame.transform.smoothscale(img, (slot_w, slot_h)) if img.get_size() != (slot_w, slot_h) else img
                w = max(1, int(slot_w * scale_x)); h = slot_h
                simg = pygame.transform.smoothscale(base, (w, h))
                rect = simg.get_rect(center=pos)
                screen.blit(simg, rect)
            fx['timer'] = timer - 1
            if fx['timer'] <= 0:
                remove_fx.append(fx)
    for fx in remove_fx:
        effects.remove(fx)

def use_card_on_grid(r, c):
    """根據手牌第一張(或選中的)來建塔/升級塔。"""
    global hand, gold, selected_card
    if not hand:
        add_notice("沒有手牌可用", (255,120,120))
        return
    # 這裡示範：使用手牌第 1 張
    card_index = selected_card if (selected_card is not None and 0 <= selected_card < len(hand)) else 0
    card = hand[card_index]

    # ---- 金幣卡：直接獲得 1/2/3 元，不需點地圖格 ----
    if card in ("1money", "2money", "3money"):
        try:
            amt = int(card[0])  # '1money' -> 1, '2money' -> 2, '3money' -> 3
        except Exception:
            amt = 1
        hand.pop(card_index)
        gold += amt
        add_notice(f"+ ${amt} 金幣卡", (255, 236, 140))
        sfx(SFX_COIN)
        selected_card = None
        return

    if card == "basic":
        # 基本塔建置
        if gold < CARD_COST_BUILD:
            add_notice(f"金幣不足：建塔需要 ${CARD_COST_BUILD}", (255,120,120))
            return
        if not is_buildable(r, c) or any(t['r']==r and t['c']==c for t in towers):
            add_notice("此處不可建塔", (255,120,120))
            return
        # 消耗卡片與金幣 → 直接建立箭塔
        hand.pop(card_index)
        gold -= CARD_COST_BUILD
        add_notice(f"- ${CARD_COST_BUILD} 使用『普通塔』卡建置", (160,235,170))
        # 原本 add_tower 會再扣一次金幣；改寫一個專用建塔，不再扣金幣
        towers.append({'id': ids['tower'], 'r': r, 'c': c, 'type': 'arrow', 'level': 0, 'cool': 0})
        ids['tower'] += 1
        selected_card = None
        return

    # ---- 升級卡：將已有塔等級 +1（最高 3 級）----
    if card == "upgrade":
        for t in towers:
            if t['r'] == r and t['c'] == c:
                max_lv = 3
                if t.get('level', 0) >= max_lv:
                    add_notice("此塔已是最高等級 (Lv3)", (255,180,120))
                    return
                # 消耗卡片（不扣金幣）
                hand.pop(card_index)
                t['level'] = t.get('level', 0) + 1
                cx, cy = center_px(r, c)
                upgrades.append({'x': cx, 'y': cy - 8, 'ttl': LEVELUP_TTL})
                sfx(SFX_LEVELUP)
                add_notice(f"升級成功：Lv{t['level']}", (160,235,170))
                selected_card = None
                return
        add_notice("此格沒有防禦塔可升級", (255,120,120))
        return

    # 元素卡：升級已有塔（把該格塔進化成元素塔）
    # (邏輯：找到該格塔→花 5 元→轉型與/或提升能力)
    for t in towers:
        if t['r']==r and t['c']==c:
            if gold < CARD_COST_DRAW:
                add_notice(f"金幣不足：元素升級需要 ${CARD_COST_DRAW}", (255,120,120))
                return
            # 消耗卡片與金幣
            hand.pop(card_index)
            spend = CARD_COST_DRAW
            # 將元素映射到現有分支
            mapping = {
                "fire": "rocket",
                "wind": "arrow",   # 例如改為高攻速箭塔（可在 TOWER_TYPES['arrow'] 另設元素旗標）
                "water": "arrow",  # 不再使用 thunder 型塔，水元素以箭塔型呈現（效果仍由元素 slow 觸發）
                "land": "arrow",   # 例如防禦/更高傷害（可在 arrow 上設 buff）
            }
            new_type = mapping.get(card, "arrow")
            gold -= spend
            t['type'] = new_type
            t['element'] = card  # 'fire'/'water'/'land'/'wind'
            # 可以視需要重置 level 或保留：這裡保留 level
            cx, cy = center_px(r, c)
            upgrades.append({'x': cx, 'y': cy - 8, 'ttl': LEVELUP_TTL})
            sfx(SFX_LEVELUP)
            add_notice(f"- ${spend} 使用『{card}』卡 → {new_type} 塔", (170,220,255))
            selected_card = None
            return

    add_notice("沒有選到已建塔的格子可升級", (255,120,120))
#-----------

# =========================
# 遊戲狀態切換輔助
def start_game():
    global game_state
    reset_game()           # 重置資源與佈局
    game_state = GAME_PLAY # 進入遊戲（預設暫停狀態，等玩家按 Space/N）


def go_menu():
    global game_state, running
    running = False
    game_state = GAME_MENU


def handle_keys(ev):
    global game_state, running, speed, sel, selected_map_idx
    if game_state == GAME_MENU:
        if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
            sfx(SFX_CLICK)
            if IS_WEB:
                try:
                    pygame.mixer.stop()
                except Exception:
                    pass
            # 進入地圖選擇畫面
            discover_maps()
            game_state = GAME_MAPSEL
        elif ev.key == pygame.K_h:
            sfx(SFX_CLICK)
            game_state = GAME_HELP
        elif ev.key == pygame.K_ESCAPE:
            sfx(SFX_CLICK)
            pygame.quit(); sys.exit()
        return
    elif game_state == GAME_MAPSEL:
        if ev.key == pygame.K_ESCAPE:
            sfx(SFX_CLICK)
            game_state = GAME_MENU
            return
        if ev.key in (pygame.K_UP, pygame.K_w):
            sfx(SFX_CLICK)
            selected_map_idx = (selected_map_idx - 1) % len(MAP_CHOICES)
            return
        if ev.key in (pygame.K_DOWN, pygame.K_s):
            sfx(SFX_CLICK)
            selected_map_idx = (selected_map_idx + 1) % len(MAP_CHOICES)
            return
        if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
            sfx(SFX_CLICK)
            set_current_map(MAP_CHOICES[selected_map_idx]['path'])
            start_game()
            return
        elif ev.key == pygame.K_r:
            # 直接使用隨機地圖開始
            sfx(SFX_CLICK)
            generate_random_map()
            try:
                rebuild_paths()
            except Exception:
                pass
            start_game()
            return
    elif game_state == GAME_HELP:
        if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
            sfx(SFX_CLICK)
            game_state = GAME_PLAY
        elif ev.key == pygame.K_ESCAPE:
            sfx(SFX_CLICK)
            go_menu()
        return

    # 遊戲中
    if ev.key == pygame.K_SPACE:
        running = not running
    elif ev.key == pygame.K_n:
        next_wave()
    elif ev.key == pygame.K_r:
        start_game()
    elif ev.key == pygame.K_1:
        speed = 1
    elif ev.key == pygame.K_2:
        speed = 2
    elif ev.key == pygame.K_3:
        speed = 4
    # Disabled manual build/upgrade by keyboard:
    # elif ev.key == pygame.K_b and sel: add_tower(sel[0], sel[1])
    # elif ev.key == pygame.K_u and sel: upgrade_tower_at(sel[0], sel[1])
    elif ev.key == pygame.K_s and sel:
        sell_tower_at(sel[0], sel[1])
    elif ev.key == pygame.K_h:
        sfx(SFX_CLICK)
        game_state = GAME_HELP
    elif ev.key == pygame.K_ESCAPE:
        sfx(SFX_CLICK)
        go_menu()
    elif ev.key == pygame.K_c:
        upgrade_castle()
    elif ev.key == pygame.K_d:
        draw_card()

def handle_click(pos):
    global sel, game_state, selected_card, hand, gold, effects
    mx, my = pos

    # --- MENU / HELP 畫面：不做去抖，立即回應 ---
    if game_state == GAME_MENU:
        # 檢查是否點擊三個按鈕
        cx = W//2 - BTN_W//2
        y0 = 240
        btns = [
            ("start", pygame.Rect(cx, y0, BTN_W, BTN_H)),
            ("help",  pygame.Rect(cx, y0 + BTN_H + BTN_GAP, BTN_W, BTN_H)),
            ("quit",  pygame.Rect(cx, y0 + (BTN_H + BTN_GAP)*2, BTN_W, BTN_H)),
        ]
        for name, r in btns:
            if r.collidepoint(mx, my):
                sfx(SFX_CLICK)
                if name == 'start':
                    if IS_WEB:
                        try: pygame.mixer.stop()
                        except Exception: pass
                    # 進入地圖選擇畫面
                    discover_maps()
                    game_state = GAME_MAPSEL
                elif name == 'help':
                    game_state = GAME_HELP
                else:
                    pygame.quit(); sys.exit()
                return
        return
    elif game_state == GAME_MAPSEL:
        # 滑鼠選地圖
        cx = W//2 - 420//2
        y0 = 170
        item_w, item_h = 420, 44
        gap = 10
        mx, my = pos
        for i, item in enumerate(MAP_CHOICES):
            r = pygame.Rect(cx, y0 + i*(item_h+gap), item_w, item_h)
            if r.collidepoint(mx, my):
                sfx(SFX_CLICK)
                if item.get('path') == RANDOM_MAP_TOKEN:
                    generate_random_map()
                    try:
                        rebuild_paths()
                    except Exception:
                        pass
                else:
                    set_current_map(item['path'])
                start_game()
                return
        # 點擊空白不做事
        return
    elif game_state == GAME_HELP:
        game_state = GAME_PLAY
        return

    # --- 遊戲中：去抖以防止誤觸，但允許「選牌後馬上點地圖」 ---
    global _last_click_ts
    now = pygame.time.get_ticks()
    if now - _last_click_ts < CLICK_DEBOUNCE_MS:
        return
    _last_click_ts = now

    # 先判斷是否點到手牌列（選牌）
    for rct, idx in HAND_UI_RECTS:
        if rct.collidepoint(mx, my):
            # 若點到的是金幣卡，立即生效（不需再點地圖）
            if 0 <= idx < len(hand):
                cn = hand[idx]
                if cn in ("1money", "2money", "3money"):
                    try:
                        amt = int(cn[0])
                    except Exception:
                        amt = 1
                    hand.pop(idx)
                    gold += amt
                    add_notice(f"+ ${amt} 金幣卡", (255, 236, 140))
                    sfx(SFX_COIN)
                    effects.append({
                        'type': 'flash', 'timer': 20,
                        'color': (255, 255, 100), 'alpha': 200,
                        'radius': 80, 'pos': (W//2, H//2)
                    })
                    if selected_card is not None and selected_card >= len(hand):
                        selected_card = None
                    return
            # 點擊手牌：切換/選擇
            if selected_card == idx:
                selected_card = None
            else:
                selected_card = idx
            # 允許立即在地圖上點擊出牌（重置去抖狀態）
            _last_click_ts = 0
            return
    # 遊戲中：原點擊選格邏輯
    if my < TOP or my > TOP + ROWS*CELL: return
    if mx < LEFT or mx > LEFT + COLS*CELL: return
    c = (mx - LEFT) // CELL; r = (my - TOP) // CELL
    sel = (int(r), int(c))
    # 點擊地圖出牌：必須有選中卡片才能出牌
    if selected_card is not None and 0 <= selected_card < len(hand):
        use_card_on_grid(int(r), int(c))
    else:
        add_notice("請先選擇要使用的卡片", (255,180,120))


# 新增：右鍵手牌丟棄
def handle_right_click(pos):
    global selected_card, hand, gold
    mx, my = pos
    # 只處理在遊戲中
    if game_state not in (GAME_PLAY,):
        return
    # 檢查是否點到手牌列：右鍵丟棄
    for rct, idx in HAND_UI_RECTS:
        if rct.collidepoint(mx, my):
            if 0 <= idx < len(hand):
                discarded = hand.pop(idx)
                # 丟棄回收：+1 金幣
                gold += 1
                add_notice("+ $1 丟棄回收", (255, 236, 140))
                sfx(SFX_COIN)
                # 調整已選索引
                if selected_card is not None:
                    if selected_card == idx:
                        selected_card = None
                    elif selected_card > idx:
                        selected_card -= 1
                add_notice(f"丟棄 {discarded} 卡牌", (200,150,255))
            return

def generate_random_map():
    """隨機產生一張可用地圖。
    - 在頂部放置主堡（2）
    - 在底部隨機放置 1~3 個出怪點（存於 SPAWNS）
    - 挖出從每個出怪點通往主堡的道路（1）
    其餘格為 0（可建造）
    """
    global MAP, SPAWNS, CASTLE_ROW, CASTLE_COL
    rows, cols = ROWS, COLS
    m = [[0 for _ in range(cols)] for _ in range(rows)]
    CASTLE_ROW = 0
    CASTLE_COL = max(1, min(cols-2, cols // 2))
    m[CASTLE_ROW][CASTLE_COL] = 2
    spawn_cnt = random.randint(1, 3)
    spawn_cols = sorted(random.sample(range(1, cols-1), k=spawn_cnt))
    SPAWNS = [(rows-1, c) for c in spawn_cols]
    for sr, sc in SPAWNS:
        r, c = sr, sc
        m[r][c] = 1
        safety = rows*cols*4
        while not (r == CASTLE_ROW and c == CASTLE_COL) and safety>0:
            safety -= 1
            step_choices = []
            if r > CASTLE_ROW:
                step_choices.append((-1, 0))
            if c < CASTLE_COL:
                step_choices.append((0, 1))
            if c > CASTLE_COL:
                step_choices.append((0, -1))
            if random.random() < 0.2:
                step_choices += [(0, 1), (0, -1)]
            if not step_choices:
                break
            dr, dc = random.choice(step_choices)
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                r, c = nr, nc
                if m[r][c] != 2:
                    m[r][c] = 1
        m[CASTLE_ROW][CASTLE_COL] = 2
    MAP = m
    return True

def main():
    global tick, life, running, next_spawn, game_state
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: pygame.quit(); sys.exit()
            elif ev.type == pygame.KEYDOWN: handle_keys(ev)
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1: handle_click(ev.pos)
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3: handle_right_click(ev.pos)

        if game_state == GAME_LOADING:
            # 若仍在載入（極少數情況），持續顯示載入畫面
            draw_loading("載入中…", LOAD_STEP, LOAD_TOTAL)
            pygame.display.flip(); clock.tick(60)
            # 當 LOADING 結束時，狀態會在載入階段最後自動切回 MENU
            continue

        if game_state == GAME_MENU:
            draw_main_menu()
            pygame.display.flip(); clock.tick(60)
            continue
        elif game_state == GAME_MAPSEL:
            draw_map_select()
            pygame.display.flip(); clock.tick(60)
            continue
        elif game_state == GAME_HELP:
            draw_help_screen()
            pygame.display.flip(); clock.tick(60)
            continue

        # === 遊戲中 ===
        if running and life>0:
            for _ in range(speed):
                tick += 1
                spawn_logic(); move_creeps(); towers_step(); bullets_step()
        # 無論是否暫停：當不再出怪且場上沒有怪時，才抽下一波預告出口
        if not wave_incoming and next_spawn is None and not creeps and SPAWNS:
            next_spawn = random.choice(SPAWNS)

        if BG_IMG:
            screen.blit(BG_IMG, (0,0))
        else:
            screen.fill(BG)
        draw_panel(); draw_world(); draw_hand_bar()
        draw_effects()
        if life<=0:
            s = pygame.Surface((W,H), pygame.SRCALPHA); s.fill((0,0,0,160)); screen.blit(s,(0,0))
            txt = BIG.render("Game Over - 按 R 重來", True, TEXT); rect = txt.get_rect(center=(W//2, H//2)); screen.blit(txt, rect)
        pygame.display.flip(); clock.tick(60)

if __name__ == "__main__":
    main()
