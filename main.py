# -*- coding:utf-8 -*-
import pygame, sys, math, random, os
from collections import Counter
from game_config import CREEP_CONFIG, get_wave_creeps
from talent_battle_config import (
    TALENT_POOL, RARITY_WEIGHTS_BY_TIER,
    roll_talent_choices, apply_talent_effect,
    format_talent_text
)

import game_config as CFG

# --- detect web (pygbag/pyodide) ---
IS_WEB = (sys.platform == "emscripten")


# 《塔路之戰》 Pygame 版 v0.0.7 
"""
V0.0.3 新增：主選單
V0.0.4 新增：抽卡機制
V0.0.5 新增：地圖選擇
V0.0.6 新增：出怪口隨機出現
V0.0.7 新增：伐木場機制
v0.0.8 新增：天賦系統
未來規劃
"""
TITLENAME = "塔路之戰-V0.0.81-Beta"
pygame.init()
try:
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
except Exception:
    pass
towers=[]; creeps=[]; bullets=[]; hits=[]; corpses=[]; gains=[]; upgrades=[]; lightning_effects=[]
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
towers=[]; creeps=[]; bullets=[]; hits=[]; corpses=[]; gains=[]; upgrades=[]; lightning_effects=[]
current_spawns = None  # 本波實際出怪口（可為多個座標）
next_spawns = None     # 下一波預告出怪口清單（2~3 或僅 1 個）
_spawn_rot = 0         # 本波輪替用索引，於每次出怪遞增

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
CARD_POOL = [
    "basic", "fire", "wind", "water", "land", "upgrade",
    "ice", "poison", "thunder",
    "1money", "2money", "3money", "lumberyard"
]
# 伐木場資源與修復設定（可於 game_config.py 覆蓋）
WOOD_PER_SECOND_PER_YARD = getattr(CFG, 'WOOD_PER_SECOND_PER_YARD', 1)
WOOD_REPAIR_COST = getattr(CFG, 'WOOD_REPAIR_COST', 5)          # 花費木材數量
WOOD_REPAIR_HP = getattr(CFG, 'WOOD_REPAIR_HP', 10)              # 單次修復 HP 量
WOOD_REPAIR_LIMIT_PER_CLICK = getattr(CFG, 'WOOD_REPAIR_LIMIT_PER_CLICK', 1)  # 單次修復可自訂倍數
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
    "lumberyard": "assets/pic/lumberyardCard.png",#伐物場
    "thunder": "assets/pic/lightningCard.png",
    "ice": "assets/pic/iceCard.png",
    "poison": "assets/pic/poisonCard.png",
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
    "lumberyard": 0,
    "thunder": CARD_COST_DRAW,
    "ice": CARD_COST_DRAW,
    "poison": CARD_COST_DRAW,
}

def _load_element_fusions():
    default = {('wind', 'water'): 'thunder'}
    src = getattr(CFG, 'ELEMENT_FUSIONS', None)
    mapping = {}
    raw = src if isinstance(src, dict) else default
    if src is None:
        raw = default
    for key, result in raw.items():
        if isinstance(key, (list, tuple)):
            items = [str(k) for k in key]
            ingredients = tuple(sorted(items))
        else:
            continue
        if not ingredients:
            continue
        out = str(result)
        mapping[ingredients] = out
    if not mapping and default:
        for key, result in default.items():
            if isinstance(key, (list, tuple)):
                items = [str(k) for k in key]
                ingredients = tuple(sorted(items))
            else:
                continue
            if not ingredients:
                continue
            mapping[ingredients] = str(result)
    if not mapping:
        mapping = default
    return mapping

ELEMENT_FUSIONS = _load_element_fusions()
FUSION_BASE_SET = set(k for combo in ELEMENT_FUSIONS.keys() for k in combo)
FUSION_REQUIRED_LENGTHS = set(len(combo) for combo in ELEMENT_FUSIONS.keys()) or {2}

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
        'lumberyard':'伐木場',
        'thunder':'雷電元素',
        'ice':'冰元素',
        'poison':'毒元素'
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
WOOD_REPAIR_BTN_RECT = None
FUSION_BTN_RECT = None
fusion_active = False
fusion_selection = []  # list of手牌索引
FUSION_UI_RECTS = []
FUSION_PANEL_RECT = None
FUSION_CANCEL_RECT = None
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
SANTELMO_USE_IMAGE = True
SANTELMO_IMG_PATH = "assets/pic/santelmo.png"
SANTELMO_IMG_SIZE = 32
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
BGM_PATH    = "assets/sfx/bgMusic.WAV"
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

FIREBALL_IMG_PATH = "assets/pic/fireball.png"
FIREBALL_IMG = None
FIREBALL_IMG_SIZE = getattr(CFG, 'FIREBALL_IMG_SIZE', 28)

WIND_PROJECTILE_IMG_PATH = "assets/pic/wind.png"
WIND_PROJECTILE_IMG = None
WIND_PROJECTILE_IMG_SIZE = getattr(CFG, 'WIND_PROJECTILE_IMG_SIZE', 26)

ICE_PROJECTILE_IMG_PATH = "assets/pic/snowball.png"
ICE_PROJECTILE_IMG = None
ICE_PROJECTILE_IMG_SIZE = getattr(CFG, 'ICE_PROJECTILE_IMG_SIZE', 26)

DEFAULT_ELEMENT_TOWER_PATHS = {
    'fire':    "assets/pic/firetower.png",
    'water':   "assets/pic/watertower.png",
    'land':    "assets/pic/landtower.png",
    'wind':    "assets/pic/windtower.png",
    'thunder': "assets/pic/thundertower.png",
}
ELEMENT_TOWER_IMAGE_PATHS = dict(DEFAULT_ELEMENT_TOWER_PATHS)
if hasattr(CFG, 'ELEMENT_TOWER_IMAGES') and isinstance(CFG.ELEMENT_TOWER_IMAGES, dict):
    for _elem, _path in CFG.ELEMENT_TOWER_IMAGES.items():
        if isinstance(_elem, str) and isinstance(_path, str):
            ELEMENT_TOWER_IMAGE_PATHS[_elem] = _path
ELEMENT_TOWER_IMGS = {}
# --- 伐木場 ---
LUMBERYARD_IMG_PATH = "assets/pic/lumberyard.png"
LUMBERYARD_IMG = None
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

# --- 雷電特效 ---
LIGHTNING_IMG_PATH = "assets/pic/lightning.png"
LIGHTNING_IMG_MAX_HEIGHT = getattr(CFG, 'LIGHTNING_IMG_MAX_HEIGHT', 180)
LIGHTNING_IMG = None
LIGHTNING_ARC_IMG = None
LIGHTNING_BOLT_IMG = None

# --- 火焰特效 ---
BURN_IMG_PATH = "assets/pic/burn.png"
BURN_IMG = None
BURN_IMG_SIZE = getattr(CFG, 'BURN_IMG_SIZE', 54)

# --- 冰凍特效 ---
ICE_HIT_IMG_PATH = "assets/pic/IcePickhit.png"
ICE_HIT_IMG = None
ICE_HIT_IMG_SIZE = getattr(CFG, 'ICE_HIT_IMG_SIZE', 56)


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

# --- 天賦系統狀態 ---
talent_state = {}
talent_runtime = {
    'kill_counter': 0,
    'last_offer_wave': 0,
    'last_cleared_wave': 0,
}
talent_choices = []
talent_ui_active = False
talent_ui_rects = []
talent_panel_rect = None

ELEMENT_ALIAS = {
    'thunder': 'lightning',
    'lightning': 'lightning',
    'wind': 'wind',
    'fire': 'fire',
    'water': 'water',
    'ice': 'ice',
    'poison': 'poison',
    'land': 'earth',
    'earth': 'earth',
}

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


def _ensure_talent_refs():
    if not talent_state:
        return
    refs = talent_state.setdefault('refs', {})
    refs['PRICES'] = PRICES
    refs['ELEMENT_EFFECTS'] = getattr(CFG, 'ELEMENT_EFFECTS', {})


def init_talent_state():
    global talent_state, talent_runtime, talent_choices, talent_ui_active, talent_ui_rects, talent_panel_rect
    talent_state = {
        'picked_talents': set(),
        'tower_mod': {
            'global_atk_mul': 1.0,
            'global_rof_mul': 1.0,
            'global_range_add': 0.0,
            'element_mod': {},
        },
        'economy': {},
        'skills': {},
        'set_bonuses': {},
        'refs': {},
    }
    talent_runtime = {
        'kill_counter': 0,
        'last_offer_wave': 0,
        'last_cleared_wave': 0,
    }
    talent_choices = []
    talent_ui_active = False
    talent_ui_rects = []
    talent_panel_rect = None
    _ensure_talent_refs()


def _tower_element_keys(tower):
    keys = []
    elem = tower.get('element')
    ttype = tower.get('type', 'arrow')
    for raw in filter(None, (elem, ttype)):
        alias = ELEMENT_ALIAS.get(raw, raw)
        if raw not in keys:
            keys.append(raw)
        if alias not in keys:
            keys.append(alias)
    return keys


def compute_tower_stats(tower):
    ttype = tower.get('type', 'arrow')
    level = tower.get('level', 0)
    base_def = TOWER_TYPES.get(ttype, {}).get(level)
    if not base_def:
        base_def = {'atk': 1, 'range': 2, 'rof': 1.0}
    stat = {
        'atk': float(base_def.get('atk', 1)),
        'range': float(base_def.get('range', 2)),
        'rof': float(base_def.get('rof', 1.0)),
    }
    tm = talent_state.get('tower_mod', {}) if talent_state else {}
    stat['atk'] *= tm.get('global_atk_mul', 1.0)
    stat['rof'] *= tm.get('global_rof_mul', 1.0)
    stat['range'] += tm.get('global_range_add', 0.0)
    emods = tm.get('element_mod', {})
    for key in _tower_element_keys(tower):
        mod = emods.get(key)
        if not mod:
            continue
        if 'atk_mul' in mod:
            stat['atk'] *= mod.get('atk_mul', 1.0)
        if 'rof_mul' in mod:
            stat['rof'] *= mod.get('rof_mul', 1.0)
        if 'range_add' in mod:
            stat['range'] += mod.get('range_add', 0.0)
    stat['atk'] = max(1.0, stat['atk'])
    stat['rof'] = max(0.1, stat['rof'])
    stat['range'] = max(1.0, stat['range'])
    return stat


def _talent_on_creep_kill(creep):
    if not talent_state:
        return
    econ = talent_state.get('economy', {})
    every = econ.get('kill_reward_every')
    bonus = econ.get('kill_reward_bonus_flat', 0)
    if every and bonus:
        talent_runtime['kill_counter'] = talent_runtime.get('kill_counter', 0) + 1
        if talent_runtime['kill_counter'] >= every:
            talent_runtime['kill_counter'] = 0
            global gold
            gold += bonus
            add_notice(f"天賦獎勵 +${bonus}", (255, 236, 140))
            sfx(SFX_COIN)


def talent_on_wave_cleared():
    if not talent_state:
        return
    talent_runtime['kill_counter'] = 0
    if talent_state.get('double_loot_this_wave'):
        talent_state['double_loot_this_wave'] = False


def _talent_choice_text(talent, idx):
    txt = format_talent_text(talent)
    header = f"[{idx+1}] "
    lines = txt.splitlines()
    if lines:
        lines[0] = header + lines[0]
    else:
        lines = [header + talent.get('name', 'Talent')]
    return lines


def open_talent_selection():
    global talent_ui_active, talent_choices, talent_ui_rects, talent_panel_rect
    if talent_ui_active or fusion_active:
        return
    if wave <= 0:
        return
    global running
    running = False
    _ensure_talent_refs()
    picked = talent_state.get('picked_talents', set())
    choices = roll_talent_choices(wave, picked_ids=picked, k=3)
    if not choices:
        return
    talent_choices = choices
    talent_ui_active = True
    talent_ui_rects = []
    talent_panel_rect = None
    talent_runtime['last_offer_wave'] = wave


def close_talent_selection():
    global talent_ui_active, talent_choices, talent_ui_rects, talent_panel_rect
    talent_ui_active = False
    talent_choices = []
    talent_ui_rects = []
    talent_panel_rect = None


def accept_talent_choice(index):
    if not talent_ui_active:
        return
    if not (0 <= index < len(talent_choices)):
        return
    choice = talent_choices[index]
    talent_state['current_wave'] = wave
    apply_talent_effect(choice['id'], talent_state)
    add_notice(f"獲得天賦：{choice['name']}", (200, 230, 255))
    sfx(SFX_LEVELUP)
    close_talent_selection()


def maybe_offer_talent():
    if talent_ui_active or fusion_active:
        return
    if game_state != GAME_PLAY or life <= 0:
        return
    if wave <= 0:
        return
    if talent_runtime.get('last_offer_wave', 0) >= wave:
        return
    if len(talent_state.get('picked_talents', [])) >= len(TALENT_POOL):
        return
    open_talent_selection()


def draw_talent_overlay():
    if not talent_ui_active:
        return
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))
    panel_w, panel_h = 640, 480
    panel = pygame.Rect(W//2 - panel_w//2, H//2 - panel_h//2, panel_w, panel_h)
    pygame.draw.rect(screen, (36, 48, 84), panel, border_radius=14)
    pygame.draw.rect(screen, (140, 180, 255), panel, 3, border_radius=14)
    title = BIG.render("選擇一項天賦", True, (235, 242, 255))
    screen.blit(title, (panel.centerx - title.get_width()//2, panel.y + 24))
    hint = SMALL.render("按 1~3 選擇天賦，或按 ESC 跳過", True, (210, 220, 235))
    screen.blit(hint, (panel.centerx - hint.get_width()//2, panel.y + 60))
    choice_h = 110
    gap = 16
    start_y = panel.y + 100
    global talent_ui_rects, talent_panel_rect
    talent_ui_rects = []
    talent_panel_rect = panel
    for idx, talent in enumerate(talent_choices):
        rect = pygame.Rect(panel.x + 28, start_y + idx * (choice_h + gap), panel.width - 56, choice_h)
        pygame.draw.rect(screen, (52, 68, 110), rect, border_radius=10)
        pygame.draw.rect(screen, (160, 200, 255), rect, 2, border_radius=10)
        lines = _talent_choice_text(talent, idx)
        for i, line in enumerate(lines):
            font = SMALL if i else FONT
            txt = font.render(line, True, (235, 242, 255))
            screen.blit(txt, (rect.x + 16, rect.y + 12 + i * 22))
        rarity = FONT.render(talent.get('rarity', 'R'), True, (255, 220, 160))
        screen.blit(rarity, (rect.right - rarity.get_width() - 16, rect.y + 12))
        talent_ui_rects.append((rect, idx))


init_talent_state()

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
        cost = table[lv]
        if talent_state:
            cost = max(1, cost - talent_state.get('upgrade_cost_minus', 0))
        return cost
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
    'thunder': {
        0: {'atk': 2, 'range': 3, 'rof': 1.5},
        1: {'atk': 3, 'range': 3, 'rof': 1.7},
        2: {'atk': 4, 'range': 4, 'rof': 1.9},
        3: {'atk': 5, 'range': 4, 'rof': 2.1},
    },
    'ice': {
        0: {'atk': 1, 'range': 2, 'rof': 1.6},
        1: {'atk': 2, 'range': 2, 'rof': 1.8},
        2: {'atk': 2, 'range': 3, 'rof': 2.0},
        3: {'atk': 3, 'range': 3, 'rof': 2.2},
    },
    'poison': {
        0: {'atk': 1, 'range': 3, 'rof': 1.4},
        1: {'atk': 2, 'range': 3, 'rof': 1.6},
        2: {'atk': 3, 'range': 4, 'rof': 1.8},
        3: {'atk': 4, 'range': 4, 'rof': 2.0},
    },
}
ARROW_EVOLVE_LEVEL = getattr(CFG, 'ARROW_EVOLVE_LEVEL', 2)

# ---- Optional: override tower stats from external config (game_config.py) ----
def _apply_tower_overrides_from_cfg():
    """
    支援三種覆蓋方式（擇一或混用）：
    1) 直接提供完整的 TOWER_TYPES 於 game_config.py
    2) 透過 TOWER_LEVEL_RULES 給定最大等級與攻擊成長、自訂 range/rof
    3) 只提供每塔各等級攻擊力：TOWER_ATK = {'arrow':[...], 'rocket':[...], 'thunder':[...]}
    4) 只提供倍率：TOWER_ATK_MULT = {'arrow':1.2, 'rocket':0.9, ...}
    """
    global TOWER_TYPES
    try:
        # 1) 完整覆蓋
        if hasattr(CFG, 'TOWER_TYPES') and isinstance(CFG.TOWER_TYPES, dict):
            TOWER_TYPES = CFG.TOWER_TYPES
            return
        # 2) 依照成長規則重建
        level_rules = getattr(CFG, 'TOWER_LEVEL_RULES', None)
        if isinstance(level_rules, dict) and level_rules:
            def _pick(seq, idx, fallback):
                if isinstance(seq, (list, tuple)):
                    if not seq:
                        return fallback
                    if idx < len(seq):
                        return seq[idx]
                    return seq[-1]
                if isinstance(seq, dict):
                    return seq.get(idx, fallback)
                if seq is not None:
                    return seq
                return fallback
            for ttype, rule in level_rules.items():
                try:
                    max_level = int(rule.get('max_level', 3))
                except Exception:
                    max_level = 3
                max_level = max(0, max_level)
                try:
                    atk_base = float(rule.get('atk_base', 1))
                except Exception:
                    atk_base = 1.0
                try:
                    atk_growth = float(rule.get('atk_growth', 1))
                except Exception:
                    atk_growth = 1.0
                range_seq = rule.get('range')
                rof_seq = rule.get('rof')
                existing = TOWER_TYPES.get(ttype, {})
                default_range = existing.get(0, {}).get('range', 2)
                default_rof = existing.get(0, {}).get('rof', 1.0)
                new_levels = {}
                for lv in range(max_level + 1):
                    atk_val = atk_base + atk_growth * lv
                    rng_val = _pick(range_seq, lv, default_range)
                    rof_val = _pick(rof_seq, lv, default_rof)
                    new_levels[lv] = {
                        'atk': max(1, int(round(atk_val))),
                        'range': float(rng_val) if isinstance(rng_val, (int, float)) else default_range,
                        'rof': float(rof_val) if isinstance(rof_val, (int, float)) else default_rof,
                    }
                TOWER_TYPES[ttype] = new_levels
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
    elif elem == 'thunder':
        base = {'type':'chain','base_targets':2,'targets_per_lv':1}
    elif elem == 'ice':
        base = {'type':'freeze','duration':0.5,'duration_per_lv':0.0}
    elif elem == 'poison':
        base = {'type':'poison_cloud','radius':2.0,'duration':2.0,'duration_per_lv':0.0}
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
    if merged.get('type') == 'freeze':
        dur = float(merged.get('duration', 0.5)) + float(merged.get('duration_per_lv', 0.0)) * max(0, int(lvl))
        merged['duration_total'] = max(0.05, dur)
    if merged.get('type') == 'poison_cloud':
        merged['radius_total'] = float(merged.get('radius', 2.0)) + float(merged.get('radius_per_lv', 0.0)) * max(0, int(lvl))
        dur = float(merged.get('duration', 2.0)) + float(merged.get('duration_per_lv', 0.0)) * max(0, int(lvl))
        merged['duration_total'] = max(0.1, dur)
    merged['level'] = lvl
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
    elif etype == 'chain':
        lvl = max(0, int(elem_cfg.get('level', 0))) if 'level' in elem_cfg else 0
        eff['chain'] = {
            'remaining': max(0, int(elem_cfg.get('base_targets', 2))) + max(0, int(elem_cfg.get('targets_per_lv', 1))) * lvl,
            'visited': set()
        }
    elif etype == 'freeze':
        duration = float(elem_cfg.get('duration_total', elem_cfg.get('duration', 0.5)))
        frames = max(1, int(round(duration * 60)))
        eff['freeze'] = {'ttl': frames}
    elif etype == 'poison_cloud':
        pass

def _normalize_effect_name(name):
    if name is None:
        return None
    if isinstance(name, str):
        norm = name.strip().lower()
        return norm or None
    try:
        norm = str(name).strip().lower()
        return norm or None
    except Exception:
        return None

def _creep_can_receive_effect(creep, etype):
    if not etype:
        return True
    # Boss 永遠會受到效果影響（忽略任何免疫設定）
    if creep.get('type') == 'boss':
        return True
    norm = _normalize_effect_name(etype)
    if not norm:
        return True
    immune = creep.get('immune_effects')
    if not immune:
        return True
    if isinstance(immune, str):
        immune = {_normalize_effect_name(immune)}
    elif isinstance(immune, (list, tuple, set)):
        if not isinstance(immune, set):
            immune = {_normalize_effect_name(x) for x in immune if _normalize_effect_name(x)}
        else:
            immune = { _normalize_effect_name(x) for x in immune }
    else:
        return True
    immune.discard(None)
    creep['immune_effects'] = immune
    if not immune:
        return True
    if 'all' in immune:
        return False
    return norm not in immune

def _spawn_lightning_arc(x1, y1, x2, y2, ttl=12):
    global lightning_effects
    if (x1 == x2) and (y1 == y2):
        return
    try:
        ttl = int(ttl)
    except Exception:
        ttl = 12
    ttl = max(1, ttl)
    bolt = {
        'start': (float(x1), float(y1)),
        'end': (float(x2), float(y2)),
        'ttl': ttl,
        'ttl_max': ttl
    }
    lightning_effects.append(bolt)

def _do_knockback(creep, grids):
    # 依路徑往回推若干格（若沒有路徑，忽略）
    global hits
    route = creep.get('route') or []
    wp = int(creep.get('wp', 1))
    if not route:
        return
    target_wp = max(0, wp - 1 - int(grids))
    tr, tc = route[target_wp]
    creep['r'], creep['c'] = float(tr), float(tc)
    creep['wp'] = target_wp + 1
    cx, cy = center_px(tr, tc)
    hits.append({'x': int(round(cx)), 'y': int(round(cy)), 'ttl': 8, 'ttl_max': 8, 'color': (170, 235, 255)})

def _perform_chain_lightning(primary, elem_cfg, bullet):
    remaining = max(0, int(elem_cfg.get('base_targets', 2)))
    remaining += max(0, int(elem_cfg.get('targets_per_lv', 1))) * max(0, int(elem_cfg.get('level', 0)))
    if bullet and talent_state:
        lightning_mod = talent_state.get('tower_mod', {}).get('element_mod', {})
        lm = lightning_mod.get('lightning') or lightning_mod.get('thunder')
        if lm:
            extra_targets = int(lm.get('extra_targets', 0))
            chance = float(lm.get('chain_chance', 0.0))
            if extra_targets > 0:
                if chance <= 0.0 or random.random() < chance:
                    remaining += extra_targets
    if remaining <= 0:
        return
    dmg = max(1, int(round(bullet.get('dmg', 1))))
    visited = set()
    if primary.get('id') is not None:
        visited.add(primary['id'])
    last = primary
    global hits, corpses, gains, gold, creeps
    for _ in range(remaining):
        last_x, last_y = center_px(last['r'], int(last['c']))
        next_target = None
        best_dist = None
        for cand in creeps:
            if not cand.get('alive'):
                continue
            cid = cand.get('id')
            if cid in visited:
                continue
            cx, cy = center_px(cand['r'], int(cand['c']))
            dist = (cx - last_x) ** 2 + (cy - last_y) ** 2
            if best_dist is None or dist < best_dist:
                best_dist = dist
                next_target = cand
        if not next_target:
            break
        cid = next_target.get('id')
        if cid is not None:
            visited.add(cid)
        nx, ny = center_px(next_target['r'], int(next_target['c']))
        _spawn_lightning_arc(last_x, last_y, nx, ny, ttl=12)
        cx, cy = center_px(next_target['r'], int(next_target['c']))
        hits.append({'x': cx, 'y': cy, 'ttl': 12, 'ttl_max': 12, 'dmg': dmg, 'color': (200, 220, 255)})
        next_target['hp'] -= dmg
        sfx(SFX_HIT)
        if next_target['hp'] <= 0:
            next_target['alive'] = False
            corpses.append({'x': cx, 'y': cy, 'ttl': 24})
            reward_amt = reward_for(next_target.get('type', 'slime'))
            gains.append({'x': cx, 'y': cy - 6, 'ttl': GAIN_TTL, 'amt': reward_amt})
            gold += reward_amt
            next_target['rewarded'] = True
            sfx(SFX_DEATH); sfx(SFX_COIN)
            _talent_on_creep_kill(next_target)
        last = next_target

def _spawn_poison_cloud(x, y, elem_cfg, atk_val):
    x = int(round(x))
    y = int(round(y))
    duration = float(elem_cfg.get('duration_total', elem_cfg.get('duration', 2.0)))
    if talent_state:
        pmod = talent_state.get('tower_mod', {}).get('element_mod', {}).get('poison')
        if pmod:
            duration *= pmod.get('duration_mul', 1.0)
    ttl = max(1, int(round(duration * 60)))
    radius_units = float(elem_cfg.get('radius_total', elem_cfg.get('radius', 2.0)))
    if talent_state:
        pmod = talent_state.get('tower_mod', {}).get('element_mod', {}).get('poison')
        if pmod:
            radius_units += pmod.get('range_add', 0.0)
    radius = radius_units * CELL
    radius = max(CELL * 0.5, radius)
    tick = max(1, int(elem_cfg.get('tick_interval', 15)))
    dmg_ratio = float(elem_cfg.get('dmg_ratio', 0.3))
    dmg = max(1, int(round(atk_val * dmg_ratio)))
    cloud = {
        'x': x,
        'y': y,
        'radius': radius,
        'ttl': ttl,
        'ttl_max': ttl,
        'tick': tick,
        'timer': tick,
        'dmg': dmg
    }
    poison_clouds.append(cloud)
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

# 動態載入怪物圖片，支援 game_config.py 中新增的怪物設定
MONSTER_SURFS = {}

def _coerce_image_size(value):
    """將尺寸設定轉為 (w, h) tuple，支援 int / float / list / tuple。"""
    if isinstance(value, (tuple, list)):
        if not value:
            return None
        if len(value) == 1:
            side = int(value[0])
            return (side, side)
        return (int(value[0]), int(value[1]))
    if isinstance(value, (int, float)):
        side = int(value)
        return (side, side)
    return None

def _load_monster_images_from_config():
    """掃描 CREEP_CONFIG 與 game_config 常數，自動載入怪物圖片。"""
    loaded = {}
    if not isinstance(CREEP_CONFIG, dict):
        return loaded
    for mtype, cfg in CREEP_CONFIG.items():
        name_upper = mtype.upper()
        img_attr = f"{name_upper}_IMG"
        existing = globals().get(img_attr)
        if existing:
            loaded[mtype] = existing
            continue
        use_flag = globals().get(f"{name_upper}_USE_IMAGE")
        if use_flag is None:
            use_flag = getattr(CFG, f"{name_upper}_USE_IMAGE", True)
        if use_flag is False:
            continue
        img_path = cfg.get('image')
        if not img_path:
            img_path = globals().get(f"{name_upper}_IMG_PATH")
        if not img_path:
            img_path = getattr(CFG, f"{name_upper}_IMG_PATH", None)
        if not img_path or not os.path.exists(img_path):
            continue
        try:
            surf = pygame.image.load(img_path).convert_alpha()
        except Exception:
            continue
        size_val = cfg.get('image_size')
        if size_val is None:
            size_val = globals().get(f"{name_upper}_IMG_SIZE")
        if size_val is None:
            size_val = getattr(CFG, f"{name_upper}_IMG_SIZE", None)
        target_size = _coerce_image_size(size_val)
        if target_size:
            surf = pygame.transform.smoothscale(surf, target_size)
        loaded[mtype] = surf
        globals()[img_attr] = surf
    return loaded

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
GIANT_IMG   = None
BOSS_IMG    = None
SANTELMO_IMG = None
GREY_IMG    = None
BLAST_IMG   = None   # 擊中圖片
DEAD_IMG    = None   # 死亡圖片
COIN_IMG    = None   # +金幣 圖示
TOWER_IMGS  = {}     # 依等級載入
LEVELUP_IMG = None   # 升級特效圖
CASTLE_IMG = None    # 城堡圖片
WALL_IMG = None      # 牆壁圖片
#CASTLE_IMG_PATH = "assets/pic/castle.png"
CASTLE_IMG_PATH = "assets/pic/christmastown.png"
#GREY_IMG_PATH = "assets/pic/activist.png" # 灰色背景圖片 預設
GREY_IMG_PATH = "assets/pic/tree.png"      # 灰色背景圖片 萬聖節
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
    for key, surf in (
        ('slime', SLIME_IMG),
        ('runner', RUNNER_IMG),
        ('brute', BRUTE_IMG),
        ('bat', BAT_IMG),
        ('boss', BOSS_IMG),
    ):
        if surf:
            MONSTER_SURFS[key] = surf
    if MONSTER_IMG:
        MONSTER_SURFS.setdefault('grunt', MONSTER_IMG)
    
    loading_tick("載入怪物素材…")
    extra_monster_imgs = _load_monster_images_from_config()
    if extra_monster_imgs:
        MONSTER_SURFS.update({k: v for k, v in extra_monster_imgs.items() if v})
    LOAD_STEP = 1
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
    if os.path.exists(GREY_IMG_PATH):
        _raw = pygame.image.load(GREY_IMG_PATH).convert_alpha()
        GREY_IMG = pygame.transform.smoothscale(_raw, (CELL, CELL))
    # 分支塔圖
    if os.path.exists(ROCKET_TOWER_IMG_PATH):
        _raw = pygame.image.load(ROCKET_TOWER_IMG_PATH).convert_alpha()
        ROCKET_TOWER_IMG = pygame.transform.smoothscale(_raw, (TOWER_IMG_SIZE, TOWER_IMG_SIZE))

    if os.path.exists(FIREBALL_IMG_PATH):
        try:
            _raw = pygame.image.load(FIREBALL_IMG_PATH).convert_alpha()
            FIREBALL_IMG = pygame.transform.smoothscale(_raw, (int(FIREBALL_IMG_SIZE), int(FIREBALL_IMG_SIZE)))
        except Exception:
            FIREBALL_IMG = None

    if os.path.exists(WIND_PROJECTILE_IMG_PATH):
        try:
            _raw = pygame.image.load(WIND_PROJECTILE_IMG_PATH).convert_alpha()
            WIND_PROJECTILE_IMG = pygame.transform.smoothscale(_raw, (int(WIND_PROJECTILE_IMG_SIZE), int(WIND_PROJECTILE_IMG_SIZE)))
        except Exception:
            WIND_PROJECTILE_IMG = None

    if os.path.exists(ICE_PROJECTILE_IMG_PATH):
        try:
            _raw = pygame.image.load(ICE_PROJECTILE_IMG_PATH).convert_alpha()
            ICE_PROJECTILE_IMG = pygame.transform.smoothscale(_raw, (int(ICE_PROJECTILE_IMG_SIZE), int(ICE_PROJECTILE_IMG_SIZE)))
        except Exception:
            ICE_PROJECTILE_IMG = None

    if os.path.exists(LIGHTNING_IMG_PATH):
        try:
            _raw = pygame.image.load(LIGHTNING_IMG_PATH).convert_alpha()
            base = _raw
            max_h = LIGHTNING_IMG_MAX_HEIGHT
            if isinstance(max_h, (int, float)) and max_h > 0 and _raw.get_height() != int(max_h):
                scale = float(max_h) / float(_raw.get_height())
                width = max(1, int(round(_raw.get_width() * scale)))
                height = max(1, int(round(max_h)))
                base = pygame.transform.smoothscale(_raw, (width, height))
            LIGHTNING_IMG = base
            LIGHTNING_ARC_IMG = base
            bolt_scale = getattr(CFG, 'LIGHTNING_PROJECTILE_SCALE', 0.4)
            try:
                bolt_scale = float(bolt_scale)
            except Exception:
                bolt_scale = 0.4
            bolt_scale = max(0.05, min(1.0, bolt_scale))
            bolt_w = max(8, int(round(base.get_width() * bolt_scale)))
            bolt_h = max(12, int(round(base.get_height() * bolt_scale)))
            LIGHTNING_BOLT_IMG = pygame.transform.smoothscale(base, (bolt_w, bolt_h))
        except Exception:
            LIGHTNING_IMG = None
            LIGHTNING_ARC_IMG = None
            LIGHTNING_BOLT_IMG = None

    if os.path.exists(BURN_IMG_PATH):
        try:
            _raw = pygame.image.load(BURN_IMG_PATH).convert_alpha()
            BURN_IMG = pygame.transform.smoothscale(_raw, (int(BURN_IMG_SIZE), int(BURN_IMG_SIZE)))
        except Exception:
            BURN_IMG = None

    if os.path.exists(ICE_HIT_IMG_PATH):
        try:
            _raw = pygame.image.load(ICE_HIT_IMG_PATH).convert_alpha()
            ICE_HIT_IMG = pygame.transform.smoothscale(_raw, (int(ICE_HIT_IMG_SIZE), int(ICE_HIT_IMG_SIZE)))
        except Exception:
            ICE_HIT_IMG = None

    # 四元素圖示（用於依元素覆蓋顯示）
    for _elem, _path in ELEMENT_TOWER_IMAGE_PATHS.items():
        if not _path:
            continue
        try:
            if os.path.exists(_path):
                _raw = pygame.image.load(_path).convert_alpha()
                ELEMENT_TOWER_IMGS[_elem] = pygame.transform.smoothscale(_raw, (TOWER_IMG_SIZE, TOWER_IMG_SIZE))
        except Exception:
            pass
    #if os.path.exists(THUNDER_TOWER_IMG_PATH):
    #   _raw = pygame.image.load(THUNDER_TOWER_IMG_PATH).convert_alpha()
    #    THUNDER_TOWER_IMG = pygame.transform.smoothscale(_raw, (TOWER_IMG_SIZE, TOWER_IMG_SIZE))

    #伐木場
    if os.path.exists(LUMBERYARD_IMG_PATH):
        _raw = pygame.image.load(LUMBERYARD_IMG_PATH).convert_alpha()
        LUMBERYARD_IMG = pygame.transform.smoothscale(_raw, (TOWER_IMG_SIZE, TOWER_IMG_SIZE))
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
            print(int(w*scale), int(h*scale))
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
    # stop BGM outside main menu
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass
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
towers=[]; creeps=[]; bullets=[]; hits=[]; corpses=[]; gains=[]; upgrades=[]; lightning_effects=[]; effects = []
lumberyards = set()
lumberyard_blocked = set()
wood_stock = 0
_wood_timer_acc = 0.0
poison_clouds = []

ids={'tower':1,'creep':1}
wave_spawn_queue=[]; SPAWN_INTERVAL=60
sel=None

def grid_to_px(r,c): return LEFT+c*CELL, TOP+r*CELL
def center_px(r,c): x,y=grid_to_px(r,c); return x+CELL/2,y+CELL/2
def manhattan(a,b):
    return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))

# 決定本波使用哪些出怪口：
# - 若總出口數 <= 3：僅 1 個隨機出口
# - 若總出口數 >= 4：隨機取 2~3 個不重複出口
def choose_wave_spawns():
    n = len(SPAWNS)
    if n <= 0:
        return []
    if n <= 3:
        return [random.choice(SPAWNS)]
    k = random.choice((2, 3))
    k = min(k, n)
    return random.sample(SPAWNS, k)

def get_max_tower_level(ttype):
    levels = TOWER_TYPES.get(ttype, {})
    if not levels:
        return 0
    try:
        return max(int(k) for k in levels.keys())
    except Exception:
        return max(levels.keys())

def get_available_fusions():
    if not ELEMENT_FUSIONS or not hand:
        return []
    usable_counts = Counter(card for card in hand if card in FUSION_BASE_SET)
    options = []
    for combo, result in ELEMENT_FUSIONS.items():
        need = Counter(combo)
        if all(usable_counts[c] >= need[c] for c in need):
            options.append((combo, result))
    return options

def start_fusion_selection():
    global fusion_active, fusion_selection, FUSION_UI_RECTS
    if fusion_active:
        return
    if not get_available_fusions():
        add_notice("目前沒有可融合的元素卡", (255,180,120))
        sfx(SFX_CLICK)
        return
    fusion_active = True
    fusion_selection = []
    FUSION_UI_RECTS = []
    sfx(SFX_CLICK)

def cancel_fusion_selection():
    global fusion_active, fusion_selection, FUSION_UI_RECTS, FUSION_PANEL_RECT, FUSION_CANCEL_RECT
    fusion_active = False
    fusion_selection = []
    FUSION_UI_RECTS = []
    FUSION_PANEL_RECT = None
    FUSION_CANCEL_RECT = None

def _try_complete_fusion():
    global fusion_active, fusion_selection, selected_card
    if not fusion_selection:
        return
    names = []
    for idx in fusion_selection:
        if 0 <= idx < len(hand):
            names.append(hand[idx])
    combo_key = tuple(sorted(names))
    result = ELEMENT_FUSIONS.get(combo_key)
    if result and len(names) in FUSION_REQUIRED_LENGTHS:
        for idx in sorted(fusion_selection, reverse=True):
            if 0 <= idx < len(hand):
                hand.pop(idx)
        selected_card = None
        hand.append(result)
        add_notice(f"融合成功，獲得『{_card_display_name(result)}』", (170, 220, 255))
        sfx(SFX_LEVELUP)
        cancel_fusion_selection()
    else:
        min_need = min(FUSION_REQUIRED_LENGTHS) if FUSION_REQUIRED_LENGTHS else 2
        max_need = max(FUSION_REQUIRED_LENGTHS) if FUSION_REQUIRED_LENGTHS else 2
        if len(names) >= min_need:
            if len(names) > max_need or len(names) in FUSION_REQUIRED_LENGTHS:
                add_notice("組合無效，請重新選擇", (255,120,120))
                fusion_selection = []

def handle_fusion_click(pos):
    global fusion_selection
    mx, my = pos
    if FUSION_CANCEL_RECT and FUSION_CANCEL_RECT.collidepoint(mx, my):
        sfx(SFX_CLICK)
        cancel_fusion_selection()
        return
    for rect, idx in FUSION_UI_RECTS:
        if rect.collidepoint(mx, my):
            if idx in fusion_selection:
                fusion_selection.remove(idx)
            else:
                fusion_selection.append(idx)
            _try_complete_fusion()
            return
    if FUSION_PANEL_RECT and not FUSION_PANEL_RECT.collidepoint(mx, my):
        cancel_fusion_selection()

def draw_fusion_overlay():
    global FUSION_UI_RECTS, FUSION_CANCEL_RECT, FUSION_PANEL_RECT
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))
    panel = pygame.Rect(W//2 - 260, H//2 - 260, 520, 520)
    FUSION_PANEL_RECT = panel
    pygame.draw.rect(screen, (28, 38, 62), panel, border_radius=12)
    pygame.draw.rect(screen, (120, 150, 235), panel, 2, border_radius=12)
    title = BIG.render("融合元素", True, (235, 242, 255))
    screen.blit(title, (panel.x + (panel.width - title.get_width())//2, panel.y + 16))
    info = SMALL.render("選擇要融合的元素卡｜再次點擊可取消選取", True, (210, 220, 235))
    screen.blit(info, (panel.x + (panel.width - info.get_width())//2, panel.y + 56))

    FUSION_UI_RECTS = []
    candidates = [(idx, name) for idx, name in enumerate(hand) if name in FUSION_BASE_SET]
    cols = 4
    slot_w, slot_h = CARD_SLOT_SIZE
    gap_x, gap_y = 20, 12
    start_x = panel.x + 40
    start_y = panel.y + 90
    for i, (idx, name) in enumerate(candidates):
        row = i // cols
        col = i % cols
        rect = pygame.Rect(start_x + col * (slot_w + gap_x), start_y + row * (slot_h + gap_y), slot_w, slot_h)
        FUSION_UI_RECTS.append((rect, idx))
        pygame.draw.rect(screen, (45, 55, 80), rect, border_radius=10)
        img = get_card_scaled(name)
        if img:
            ir = img.get_rect(center=rect.center)
            screen.blit(img, ir)
        if idx in fusion_selection:
            pygame.draw.rect(screen, (255, 220, 120), rect, 4, border_radius=10)
        else:
            pygame.draw.rect(screen, (90, 110, 160), rect, 2, border_radius=10)
    if not candidates:
        empty_msg = SMALL.render("沒有可供融合的元素卡", True, (255, 180, 120))
        screen.blit(empty_msg, (panel.x + (panel.width - empty_msg.get_width())//2, panel.y + panel.height//2))

    cancel_rect = pygame.Rect(panel.right - 120, panel.bottom - 50, 96, 32)
    FUSION_CANCEL_RECT = cancel_rect
    pygame.draw.rect(screen, (60, 40, 40), cancel_rect, border_radius=8)
    pygame.draw.rect(screen, (180, 120, 120), cancel_rect, 2, border_radius=8)
    cancel_label = SMALL.render("取消", True, (235, 220, 220))
    screen.blit(cancel_label, (cancel_rect.x + (cancel_rect.width - cancel_label.get_width())//2,
                               cancel_rect.y + (cancel_rect.height - cancel_label.get_height())//2))

    selected_names = [hand[idx] for idx in fusion_selection if 0 <= idx < len(hand)]
    if selected_names:
        current = SMALL.render("選擇：" + " + ".join(selected_names), True, (200, 230, 255))
        screen.blit(current, (panel.x + 40, panel.bottom - 50))

def update_lumberyards(dt_ms):
    """依據時間流逝累積伐木場產出的木材。"""
    global _wood_timer_acc, wood_stock
    if not lumberyards:
        return
    if WOOD_PER_SECOND_PER_YARD <= 0:
        return
    dt = max(0.0, float(dt_ms) / 1000.0)
    _wood_timer_acc += len(lumberyards) * WOOD_PER_SECOND_PER_YARD * dt
    gained = int(_wood_timer_acc)
    if gained >= 1:
        wood_stock += gained
        _wood_timer_acc -= gained

def poison_clouds_step():
    global poison_clouds, hits, corpses, gains, gold, creeps
    active = []
    for cloud in poison_clouds:
        cloud['ttl'] -= 1
        if cloud['ttl'] <= 0:
            continue
        cloud['timer'] -= 1
        if cloud['timer'] <= 0:
            cloud['timer'] = cloud['tick']
            radius = cloud['radius']
            radius_sq = radius * radius
            for m in list(creeps):
                if not m.get('alive'):
                    continue
                if not _creep_can_receive_effect(m, 'poison_cloud'):
                    continue
                cx, cy = center_px(m['r'], int(m['c']))
                dx = cx - cloud['x']
                dy = cy - cloud['y']
                if dx * dx + dy * dy <= radius_sq:
                    m['hp'] -= cloud['dmg']
                    hits.append({'x': cx, 'y': cy, 'ttl': 10, 'ttl_max': 10, 'dmg': cloud['dmg'], 'color': (120, 255, 150)})
                    if m['hp'] <= 0:
                        m['alive'] = False
                        corpses.append({'x': cx, 'y': cy, 'ttl': 24})
                        reward_amt = reward_for(m.get('type', 'slime'))
                        gains.append({'x': cx, 'y': cy - 6, 'ttl': GAIN_TTL, 'amt': reward_amt})
                        gold += reward_amt
                        m['rewarded'] = True
                        sfx(SFX_DEATH); sfx(SFX_COIN)
                        _talent_on_creep_kill(m)
        active.append(cloud)
    poison_clouds[:] = active

def draw_poison_clouds():
    if not poison_clouds:
        return
    for cloud in poison_clouds:
        radius = int(cloud['radius'])
        if radius <= 0:
            continue
        alpha_ratio = cloud['ttl'] / float(cloud.get('ttl_max', cloud['ttl']) or 1)
        alpha = max(50, min(180, int(200 * alpha_ratio)))
        surface = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
        center = (radius, radius)
        pygame.draw.circle(surface, (60, 200, 120, int(alpha*0.7)), center, radius)
        pygame.draw.circle(surface, (40, 160, 90, alpha), center, max(12, int(radius*0.75)))
        pygame.draw.circle(surface, (20, 110, 60, int(alpha*0.5)), center, max(6, int(radius*0.45)))
        screen.blit(surface, (cloud['x'] - radius, cloud['y'] - radius))

def draw_panel():
    global WOOD_REPAIR_BTN_RECT, FUSION_BTN_RECT
    pygame.draw.rect(screen, PANEL, (0,0,W,TOP))
    txt = FONT.render(f"$ {gold}  Wave {wave}{' (spawning)' if wave_incoming else ''}    Speed x{speed}", True, TEXT)
    screen.blit(txt, (16, 10))
    tips = FONT.render("C 升級主堡 S 回收｜F 修復主堡｜Space暫停/開始｜N下一波｜R重置｜1/2/3速度", True, TEXT)
    screen.blit(tips, (16, TOP-28))
    wood_str = f"木材: {wood_stock}"
    wood_label = FONT.render(wood_str, True, TEXT)
    #wood_x = W - wood_label.get_width() - 16
    screen.blit(wood_label, (16, 120))
    # 修復按鈕
    btn_w, btn_h = 150, 28
    btn_x = 16
    btn_y = 150
    if WOOD_REPAIR_COST > 0 and WOOD_REPAIR_HP > 0:
        WOOD_REPAIR_BTN_RECT = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        can_repair = (wood_stock >= WOOD_REPAIR_COST) and (CASTLE['hp'] < CASTLE['max_hp'])
        bg_color = (48, 74, 110) if can_repair else (30, 40, 58)
        pygame.draw.rect(screen, bg_color, WOOD_REPAIR_BTN_RECT, border_radius=6)
        border_color = (120, 190, 255) if can_repair else (70, 90, 120)
        pygame.draw.rect(screen, border_color, WOOD_REPAIR_BTN_RECT, 2, border_radius=6)
        label = SMALL.render(f"修復 +{WOOD_REPAIR_HP}HP (-{WOOD_REPAIR_COST}木)", True, (235, 242, 255))
        screen.blit(label, (btn_x + (btn_w - label.get_width())//2, btn_y + (btn_h - label.get_height())//2))
    else:
        WOOD_REPAIR_BTN_RECT = None
    fusion_y = btn_y + btn_h + 8
    FUSION_BTN_RECT = pygame.Rect(btn_x, fusion_y, btn_w, btn_h)
    fusion_available = bool(get_available_fusions())
    fusion_bg = (74, 48, 110) if fusion_available else (30, 32, 52)
    fusion_border = (200, 150, 255) if fusion_available else (70, 90, 120)
    if fusion_active:
        fusion_bg = (110, 86, 150)
        fusion_border = (255, 230, 160)
    pygame.draw.rect(screen, fusion_bg, FUSION_BTN_RECT, border_radius=6)
    pygame.draw.rect(screen, fusion_border, FUSION_BTN_RECT, 2, border_radius=6)
    fusion_label = SMALL.render("融合元素", True, (235, 242, 255))
    screen.blit(fusion_label, (FUSION_BTN_RECT.x + (btn_w - fusion_label.get_width())//2,
                               FUSION_BTN_RECT.y + (btn_h - fusion_label.get_height())//2))
    if fusion_available:
        fusion_info = SMALL.render("火+風→雷｜風+水→冰｜土+水→毒", True, (210, 220, 235))
        screen.blit(fusion_info, (btn_x, fusion_y + btn_h + 4))
    if not wave_incoming and next_spawns:
        nr, nc = (next_spawns[0] if next_spawns else (0,0))
        info = FONT.render(f"＊＊下一波出口：怪物 在 ({nr},{nc})——按 N 開始＊＊", True, (255, 0, 0))
        screen.blit(info, (16, 610))

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
    screen.blit(castle_txt, (16, 75))

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
    logo_offset = LEFT if LOGO_IMG else 0
    if LOGO_IMG:
        lr = LOGO_IMG.get_rect()
        lr.topleft = (0, 80)
        screen.blit(LOGO_IMG, lr)
    title = BIG.render("塔路之戰 - 作者：Ethan.Kao", True, (250, 245, 255))
    subtitle = FONT.render("Tower Defense - 主選單", True, (190, 200, 220))
    screen.blit(title, (300, 120))
    screen.blit(subtitle, (380, 160))
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
    # stop BGM outside main menu
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass
    screen.fill((16, 20, 35))
    if BG_IMG:
        screen.blit(BG_IMG, (0,0))
        dim = pygame.Surface((W,H), pygame.SRCALPHA); dim.fill((0,0,0,120)); screen.blit(dim,(0,0))
    title = BIG.render("操作說明", True, (250, 245, 255))
    screen.blit(title, (W//2 - title.get_width()//2, 120))
    left_lines = [
        "D抽卡  左鍵使用卡片建塔/升級｜S 回收｜C 升級主堡",
        "可抽到：普通塔(10)、元素卡(5)、升級卡(0)",
        "升級卡可將任一塔升到最高等級",
        "1/2/3 調整速度",
        "每波開始前：右上顯示開始/暫停，紅箭頭預告下一個 S 出口",
        "清空當波怪物後，才會顯示下一波預告",
        "伐木場：使用卡牌建造後每秒產木材，可查看存量",
        "木材修復：點擊修復按鈕或按 F (Shift+F 一次使用多份) 來回復主堡 HP",
        "融合元素：點擊面板按鈕選擇手牌元素進行合成",
        "按 Enter/Space 回到遊戲，或 Esc 返回主選單"
    ]
    right_lines = [
        "元素融合表：",
        "火 + 風 → 雷電",
        "風 + 水 → 冰",
        "土 + 水 → 毒",
        "",
        "更多提示：",
        "地圖選單：按 R 可使用隨機地圖開局",
        "手牌：右鍵丟棄卡片 + $1 金幣",
        "Shift+F 修復一次可消耗多份木材",
    ]
    # 額外說明：隨機地圖與右鍵丟棄
    try:
        lines += [
            "地圖選單：按 R 可使用隨機地圖開局",
            "手牌：右鍵丟棄卡片，獲得 +$1 金幣",
        ]
    except Exception:
        pass
    left_x = W//2 - 420
    right_x = W//2 + 170
    base_y = 180
    line_gap = 32
    y = base_y
    for ln in left_lines:
        t = FONT.render(ln, True, (220, 228, 240))
        screen.blit(t, (left_x, y))
        y += line_gap
    y = base_y
    for ln in right_lines:
        t = FONT.render(ln, True, (220, 228, 240))
        screen.blit(t, (right_x, y))
        y += line_gap

def draw_map():
    for r in range(ROWS):
        for c in range(COLS):
            x, y = grid_to_px(r, c)
            rect = pygame.Rect(x, y, CELL, CELL)
            s = pygame.Surface((CELL, CELL), pygame.SRCALPHA)

            # 先畫底色：依 MAP 值決定
            tile = MAP[r][c]
            if tile == 3 and GREY_IMG:
                screen.blit(GREY_IMG, rect)
            else:
                if tile == 1:
                    s.fill(ROAD)
                elif tile == 0:
                    s.fill(LAND)
                elif tile == 3:
                    s.fill(GREY)
                else:  # 2 = 牆/障礙（含主堡格視覺顯示）
                    s.fill(BLOCK)
                screen.blit(s, rect)

            # 覆蓋伐木場圖示
            if (r, c) in lumberyards:
                yard_img = LUMBERYARD_IMG
                if yard_img:
                    img_rect = yard_img.get_rect(center=(x + CELL//2, y + CELL//2))
                    screen.blit(yard_img, img_rect)

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
            if not wave_incoming and next_spawns:
                if ((r, c) in next_spawns) and ARROW_IMG:
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
    elem_img = ELEMENT_TOWER_IMGS.get(elem) if elem else None

    if elem_img:
        rect = elem_img.get_rect(center=(cx, cy))
        screen.blit(elem_img, rect)
    elif ttype == 'rocket':
        if 'ROCKET_TOWER_IMG' in globals() and ROCKET_TOWER_IMG:
            rect = ROCKET_TOWER_IMG.get_rect(center=(cx, cy))
            screen.blit(ROCKET_TOWER_IMG, rect)
        else:
            pygame.draw.circle(screen, (220,80,60), (cx, cy), CELL//2 - 6)
    else:
        # arrow：先嘗試用等級圖示，否則退回程式繪圖
        img = TOWER_IMGS.get(level)
        if img:
            rect = img.get_rect(center=(cx, cy))
            screen.blit(img, rect)
        else:
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

    # 顯示等級標籤在塔下方
    label_text = f"Lv{level}"
    label_surface = SMALL.render(label_text, True, (255, 255, 210))
    text_w, text_h = label_surface.get_width(), label_surface.get_height()
    text_x = cx - text_w // 2
    min_x = x + 2
    max_x = x + CELL - text_w - 2
    text_x = min(max(text_x, min_x), max_x)
    text_y = y + CELL - text_h - 3
    if text_y < y + 2:
        text_y = y + 2
    bg_rect = pygame.Rect(text_x - 4, text_y - 2, text_w + 8, text_h + 4)
    bg_surface = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
    bg_surface.fill((15, 19, 32, 160))
    screen.blit(bg_surface, bg_rect.topleft)
    screen.blit(label_surface, (text_x, text_y))

def draw_monster_icon(m):
    mtype = m.get('type', 'slime')
    x,y = grid_to_px(int(m['r']), int(m['c']))
    cx, cy = x + CELL//2, y + CELL//2
    color = CREEP.get(mtype, {}).get('color', (200, 200, 200))
    img = MONSTER_SURFS.get(mtype)
    if img:
        rect = img.get_rect(center=(cx, cy))
        screen.blit(img, rect)
    elif mtype == "runner":
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
        # health bar above monster
    try:
        hp = max(0, int(m.get('hp', 1)))
        mxhp = int(m.get('max_hp', hp)) if m.get('max_hp') else hp
        ratio = 0.0 if mxhp <= 0 else max(0.0, min(1.0, hp / float(mxhp)))

        bar_w = int(CELL * 0.8)
        bar_h = 5
        bx = (x + CELL//2) - bar_w // 2
        by = y - 6  # 在格子上方一點

        # 背景
        pygame.draw.rect(screen, (50, 50, 60), (bx, by, bar_w, bar_h))
        # 前景
        fill_w = int(bar_w * ratio)
        if fill_w > 0:
            pygame.draw.rect(screen, (180, 60, 60), (bx, by, fill_w, bar_h))
        # 邊框
        pygame.draw.rect(screen, (20, 20, 28), (bx, by, bar_w, bar_h), 1)
    except Exception:
        pass


def draw_bullets():
    for b in bullets:
        style = b.get('style')
        trail_color = (180, 190, 200)
        if style == 'rocket':
            trail_color = (255, 150, 90)
        element = b.get('element')
        if element == 'wind':
            trail_color = (170, 240, 255)
        elif element == 'ice':
            trail_color = (210, 240, 255)
        if element == 'thunder':
            trail_color = (120, 200, 255)
        if len(b['trail']) >= 2:
            pygame.draw.lines(screen, trail_color, False, b['trail'], 2)
        if style == 'rocket' and FIREBALL_IMG:
            angle = -math.degrees(math.atan2(b['vy'], b['vx'])) - 90
            img = pygame.transform.rotozoom(FIREBALL_IMG, angle, 1.0)
            rect = img.get_rect(center=(int(b['x']), int(b['y'])))
            screen.blit(img, rect)
        elif element == 'wind' and WIND_PROJECTILE_IMG:
            angle = -math.degrees(math.atan2(b['vy'], b['vx'])) - 90
            img = pygame.transform.rotozoom(WIND_PROJECTILE_IMG, angle, 1.0)
            rect = img.get_rect(center=(int(b['x']), int(b['y'])))
            screen.blit(img, rect)
        elif element == 'ice' and ICE_PROJECTILE_IMG:
            angle = -math.degrees(math.atan2(b['vy'], b['vx'])) - 90
            img = pygame.transform.rotozoom(ICE_PROJECTILE_IMG, angle, 1.0)
            rect = img.get_rect(center=(int(b['x']), int(b['y'])))
            screen.blit(img, rect)
        elif element == 'thunder' and LIGHTNING_BOLT_IMG:
            angle = -math.degrees(math.atan2(b['vy'], b['vx'])) - 90
            img = pygame.transform.rotate(LIGHTNING_BOLT_IMG, angle)
            rect = img.get_rect(center=(int(b['x']), int(b['y'])))
            screen.blit(img, rect)
        else:
            pygame.draw.circle(screen, WHITE, (int(b['x']), int(b['y'])), 3)

def draw_lightning_effects():
    if not lightning_effects:
        return
    alive = []
    base_img = LIGHTNING_ARC_IMG
    for bolt in lightning_effects:
        x1, y1 = bolt['start']
        x2, y2 = bolt['end']
        ttl = bolt['ttl']
        ttl_max = bolt.get('ttl_max', ttl if ttl > 0 else 1)
        life_ratio = ttl / float(ttl_max) if ttl_max else 0.0
        alpha = max(0, min(255, int(255 * life_ratio)))
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length < 4:
            bolt['ttl'] = 0
        else:
            if base_img:
                scale = length / float(base_img.get_height())
                if scale > 0:
                    angle = -math.degrees(math.atan2(dy, dx)) - 90
                    img = pygame.transform.rotozoom(base_img, angle, scale)
                    img.set_alpha(alpha)
                    rect = img.get_rect(center=(int((x1 + x2) / 2), int((y1 + y2) / 2)))
                    screen.blit(img, rect)
            else:
                color = (
                    int(160 + 80 * life_ratio),
                    int(200 + 40 * life_ratio),
                    255
                )
                width = max(1, int(3 * life_ratio))
                pygame.draw.line(screen, color, (x1, y1), (x2, y2), width)
        bolt['ttl'] -= 1
        if bolt['ttl'] > 0:
            alive.append(bolt)
    lightning_effects[:] = alive

def draw_hits():
    alive = []
    for h in hits:
        ttl_max = h.get('ttl_max', 12)
        try:
            ttl_max = float(ttl_max)
        except Exception:
            ttl_max = 12.0
        ttl_max = max(1.0, ttl_max)
        life_ratio = max(0.0, min(1.0, h['ttl'] / ttl_max))
        alpha = max(0, min(255, int(255 * life_ratio)))
        effect = h.get('effect')
        if effect == 'burn' and BURN_IMG:
            scale = 0.8 + (1.0 - life_ratio) * 0.5
            img = pygame.transform.rotozoom(BURN_IMG, 0, scale)
            img.set_alpha(alpha)
            offset_y = int((1.0 - life_ratio) * 10)
            rect = img.get_rect(center=(h['x'], h['y'] - offset_y))
            screen.blit(img, rect)
            if BLAST_IMG:
                blast_scale = 0.9 + (1.0 - life_ratio) * 0.2
                blast_size = int(HIT_IMG_SIZE * blast_scale)
                blast = pygame.transform.smoothscale(BLAST_IMG, (blast_size, blast_size)).copy()
                blast.set_alpha(int(alpha * 0.7))
                rect_blast = blast.get_rect(center=(h['x'], h['y']))
                screen.blit(blast, rect_blast)
        elif effect == 'freeze' and ICE_HIT_IMG:
            scale = 0.85 + (1.0 - life_ratio) * 0.3
            img = pygame.transform.rotozoom(ICE_HIT_IMG, 0, scale)
            img.set_alpha(alpha)
            offset_y = int((1.0 - life_ratio) * 6)
            rect = img.get_rect(center=(h['x'], h['y'] - offset_y))
            screen.blit(img, rect)
            aura_size = int(HIT_IMG_SIZE * (0.8 + (1.0 - life_ratio) * 0.3))
            aura_size = max(8, aura_size)
            aura = pygame.Surface((aura_size, aura_size), pygame.SRCALPHA)
            pygame.draw.circle(aura, (190, 230, 255, int(alpha * 0.5)), (aura_size//2, aura_size//2), aura_size//2)
            aura_rect = aura.get_rect(center=(h['x'], h['y']))
            screen.blit(aura, aura_rect)
        elif BLAST_IMG:
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

def repair_castle_with_wood(mult=1):
    """使用木材修復主堡血量。"""
    global wood_stock
    if WOOD_REPAIR_COST <= 0 or WOOD_REPAIR_HP <= 0:
        add_notice("伐木場修復參數未設定，無法修復", (255,120,120))
        return
    missing = CASTLE['max_hp'] - CASTLE['hp']
    if missing <= 0:
        add_notice("主堡血量已滿", (160,235,170))
        return
    try:
        mult = int(mult)
    except (TypeError, ValueError):
        mult = 1
    mult = max(1, min(mult, WOOD_REPAIR_LIMIT_PER_CLICK))
    max_by_missing = max(1, math.ceil(missing / float(WOOD_REPAIR_HP)))
    chunks = min(mult, max_by_missing)
    max_by_wood = wood_stock // WOOD_REPAIR_COST
    if max_by_wood <= 0:
        add_notice(f"木材不足：修復需要 {WOOD_REPAIR_COST} 木材", (255,120,120))
        return
    chunks = min(chunks, max_by_wood)
    if chunks <= 0:
        add_notice(f"木材不足：修復需要 {WOOD_REPAIR_COST} 木材", (255,120,120))
        return
    cost = chunks * WOOD_REPAIR_COST
    heal = chunks * WOOD_REPAIR_HP
    heal = min(heal, missing)
    spent_chunks = math.ceil(heal / float(WOOD_REPAIR_HP))
    cost = spent_chunks * WOOD_REPAIR_COST
    wood_stock -= cost
    if talent_state:
        bonus_ratio = talent_state.get('economy', {}).get('lumber_heal_bonus_ratio', 0.0)
        if bonus_ratio:
            heal = int(round(heal * (1.0 + bonus_ratio)))
            heal = min(heal, missing)
    CASTLE['hp'] = min(CASTLE['hp'] + heal, CASTLE['max_hp'])
    add_notice(f"使用木材修復 +{heal} HP（消耗 {cost} 木材）", (170, 220, 255))
    sfx(SFX_LEVELUP)
# 每一波擊殺金幣提升：比上一波多 1%
# 例：第 1 波=1.01x，第 10 波≈1.1046x
def reward_for(kind):
    base = CREEP.get(kind, {}).get('reward', 1)
    growth = getattr(CFG, 'CREEP_REWARD_GROWTH', 0.02)
    try:
        growth = float(growth)
    except Exception:
        growth = 0.02
    mult = (1.0 + growth) ** max(0, int(wave))
    reward = max(1, int(round(base * mult)))
    if talent_state.get('double_loot_this_wave'):
        reward *= 2
    return reward

def creep_attack_value(creep):
    """回傳怪物攻擊力（優先使用實體值，其次讀取設定表）。"""
    atk = creep.get('attack')
    try:
        atk = int(atk)
    except (TypeError, ValueError):
        atk = None
    if atk is None:
        base = CREEP.get(creep.get('type', ''), {}).get('attack')
        try:
            atk = int(base)
        except (TypeError, ValueError):
            atk = 1
    growth = getattr(CFG, 'CREEP_ATTACK_GROWTH', 0.02)
    try:
        growth = float(growth)
    except Exception:
        growth = 0.02
    wave_idx = max(0, int(wave))
    scaled = atk * ((1.0 + growth) ** wave_idx)
    return max(0, int(round(scaled)))

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

def tower_fire(t, stat=None):
    global gold
    ttype = t.get('type', 'arrow')
    if stat is None:
        stat = compute_tower_stats(t)
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
    element = t.get('element')
    if not element:
        if ttype in ('thunder', 'lightning'):
            element = 'thunder'
        elif ttype in ('fire', 'water', 'land', 'wind', 'ice', 'poison'):
            element = ttype
    bullet = {
        'x': sx, 'y': sy, 'vx': vx, 'vy': vy,
        'dmg': stat['atk'] * (1.5 if ttype == 'rocket' else 1),
        'target_id': target['id'],
        'ttl': 120, 'trail': [(sx, sy)],
        'aoe': (ttype == 'rocket'),
        'element': element,
        'tlevel': t.get('level', 0),
        'style': ttype
    }
    bullets.append(bullet)
    if element == 'thunder':
        _spawn_lightning_arc(sx, sy, tx, ty, ttl=10)

def spawn_logic():
    """
    依 get_wave_creeps(wave) 建立本波出怪佇列，並按 SPAWN_INTERVAL 出怪。
    - 每 10 波：只會有 1 隻 boss（在 get_wave_creeps 已處理）
    - 其他波：總數量介於 10~20，種類隨機（在 get_wave_creeps 已處理）
    - 血量每波 +1%，速度每波 +3%
    """
    global spawn_counter, wave_incoming, creeps, ids
    global next_spawns, current_spawns, wave_spawn_queue, _spawn_rot

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

        # 決定本波出怪口（可能為多個）：優先使用預告；否則依規則抽取
        if next_spawns is not None:
            current_spawns = list(next_spawns)
        elif current_spawns is None:
            current_spawns = choose_wave_spawns()
        next_spawns = None  # 用掉預告
        _spawn_rot = 0

    # 到點出怪
    if spawn_counter % SPAWN_INTERVAL == 0 and wave_spawn_queue:
        kind = wave_spawn_queue.pop(0)

        # 從設定讀取基礎屬性（缺就用舊 CREEP 值當備援）
        cfg = CREEP.get(kind, {}) if isinstance(CREEP, dict) else {}
        try:
            base_hp = int(cfg.get('hp', 10))
        except (TypeError, ValueError):
            base_hp = 10
        try:
            base_speed = float(cfg.get('speed', 0.02))
        except (TypeError, ValueError):
            base_speed = 0.02
        try:
            reward = int(cfg.get('reward', 1))
        except (TypeError, ValueError):
            reward = 1
        try:
            attack = int(cfg.get('attack', 1))
        except (TypeError, ValueError):
            attack = 1

        if current_spawns:
            sr, sc = current_spawns[_spawn_rot % len(current_spawns)]
            _spawn_rot += 1
        else:
            sr, sc = (SPAWNS[0] if SPAWNS else (ROWS-1, COLS//2))
        route  = PATHS.get((sr, sc)) or [(sr, sc), (CASTLE_ROW, CASTLE_COL)]

        # 成長：血量每波 +1%，速度每波 +3%
        hp_scaled  = max(1, int(round(base_hp * (1.01 ** max(0, int(wave))))))
        spd_scaled = base_speed * (1.0 + 0.03 * max(0, int(wave)))

        immune_cfg = cfg.get('immune_effects') or cfg.get('effect_immunities') or cfg.get('immune')
        immune_set = set()
        if immune_cfg:
            if isinstance(immune_cfg, str):
                immune_cfg = [immune_cfg]
            for name in immune_cfg:
                norm = _normalize_effect_name(name)
                if norm:
                    immune_set.add(norm)

        creep_obj = {
            'id': ids['creep'],
            'type': kind,
            'r': float(sr), 'c': float(sc),
            'wp': 1, 'route': route,
            'hp': hp_scaled, 'max_hp': hp_scaled, 'alive': True,
            'speed': spd_scaled, 'reward': reward,
            'attack': attack,
            'effects': {},
            'rewarded': False
        }
        if immune_set:
            creep_obj['immune_effects'] = immune_set

        creeps.append(creep_obj)
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
                        _talent_on_creep_kill(m)
                        eff[key] = None
                        break
                if e['ttl'] <= 0:
                    eff[key] = None
        # 移除過期 None
        for k in list(eff.keys()):
            if not eff[k]:
                eff.pop(k, None)
        # 冰凍：完全停滯
        frozen = eff.get('freeze')
        if frozen:
            frozen['ttl'] -= 1
            if frozen['ttl'] <= 0:
                eff.pop('freeze', None)
            else:
                alive.append(m)
                continue
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
                dmg = creep_attack_value(m)
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
                dmg = creep_attack_value(m)
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
        stat = compute_tower_stats(t)
        cd_need = max(1, int(30 / stat['rof']))
        t['cool'] = t.get('cool',0) + 1
        if t['cool'] >= cd_need:
            tower_fire(t, stat)
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
            if math.hypot(b['x'] - tx, b['y'] - ty) < 10:
                dmg = b['dmg']
                target['hp'] -= dmg
                element = b.get('element')
                hit_entry = {'x': tx, 'y': ty, 'ttl': 12, 'ttl_max': 12, 'dmg': dmg}
                if b.get('style') == 'rocket':
                    hit_entry['effect'] = 'burn'
                elif element == 'ice':
                    hit_entry['effect'] = 'freeze'
                hits.append(hit_entry)
                sfx(SFX_HIT)
                ecfg = None
                if element in ('water', 'land', 'wind', 'fire', 'thunder', 'ice', 'poison'):
                    ecfg = _get_elem_cfg(element, b.get('tlevel', 0))
                    if ecfg:
                        etype = ecfg.get('type')
                        allowed = _creep_can_receive_effect(target, etype)
                        if etype == 'knockback':
                            if allowed:
                                _do_knockback(target, ecfg.get('grids', 1))
                        elif etype == 'poison_cloud':
                            if allowed:
                                _spawn_poison_cloud(tx, ty, ecfg, dmg)
                        else:
                            if allowed:
                                _apply_status_on_hit(target, ecfg, dmg)
                        if etype == 'chain':
                            _perform_chain_lightning(target, ecfg, b)
                if b.get('aoe'):
                    ax, ay = tx, ty
                    radius = 60
                    for m in list(creeps):
                        if (not m['alive']) or m['id'] == target['id']:
                            continue
                        mx, my = center_px(m['r'], int(m['c']))
                        if math.hypot(mx - ax, my - ay) <= radius:
                            splash_dmg = max(1, int(round(dmg * 0.6)))
                            m['hp'] -= splash_dmg
                            splash_entry = {'x': mx, 'y': my, 'ttl': 8, 'ttl_max': 8, 'dmg': splash_dmg}
                            if b.get('style') == 'rocket':
                                splash_entry['effect'] = 'burn'
                            hits.append(splash_entry)
                            ecfg_fire = _get_elem_cfg('fire', b.get('tlevel', 0))
                            if ecfg_fire and _creep_can_receive_effect(m, ecfg_fire.get('type')):
                                _apply_status_on_hit(m, ecfg_fire, dmg)
                            if m['hp'] <= 0:
                                m['alive'] = False
                                corpses.append({'x': mx, 'y': my, 'ttl': 24})
                                reward_amt = reward_for(m['type'])
                                gains.append({'x': mx, 'y': my - 6, 'ttl': GAIN_TTL, 'amt': reward_amt})
                                gold += reward_amt
                                m['rewarded'] = True
                                sfx(SFX_DEATH); sfx(SFX_COIN)
                                _talent_on_creep_kill(m)
                if target['hp'] <= 0:
                    target['alive'] = False
                    corpses.append({'x': tx, 'y': ty, 'ttl': 24})
                    reward_amt = reward_for(target['type'])
                    gains.append({'x': tx, 'y': ty - 6, 'ttl': GAIN_TTL, 'amt': reward_amt})
                    gold += reward_amt
                    target['rewarded'] = True
                    sfx(SFX_DEATH); sfx(SFX_COIN)
                    _talent_on_creep_kill(target)
                continue
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
    draw_poison_clouds()
    for t in towers: draw_tower_icon(t)
    draw_upgrades()
    for m in creeps: draw_monster_icon(m)
    draw_bullets(); draw_lightning_effects(); draw_hits(); draw_corpses(); draw_gains(); draw_selection()

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
            if t['type'] == 'arrow' and t['level'] == ARROW_EVOLVE_LEVEL:
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
            max_lv = get_max_tower_level(t.get('type','arrow'))
            if t.get('level', 0) >= max_lv:
                add_notice("此塔已達最高等級", (255,180,120))
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
    global wave, wave_incoming, spawn_counter, current_spawns, next_spawns, _spawn_rot
    if wave_incoming: return
    wave += 1
    wave_incoming = True
    spawn_counter = 0
    # 使用預告的出口群，若沒有則依規則抽取
    if next_spawns:
        current_spawns = list(next_spawns)
        next_spawns = None
    elif current_spawns is None:
        current_spawns = choose_wave_spawns()
    _spawn_rot = 0

def reset_game():
    global running, tick, gold, life, wave, wave_incoming, spawn_counter
    global towers, creeps, bullets, hits, corpses, gains, upgrades, lumberyards, lumberyard_blocked, poison_clouds
    global wood_stock, _wood_timer_acc, fusion_active, fusion_selection
    running=False; tick=0; gold=100; life=20; wave=0; wave_incoming=False; spawn_counter=0
    towers=[]; creeps=[]; bullets=[]; hits=[]; corpses=[]; gains=[]; upgrades=[]; lightning_effects=[]
    towers=[]; creeps=[]; bullets=[]; hits=[]; corpses=[]; gains=[]; upgrades=[]; lightning_effects=[]
    init_talent_state()
    for r, c in list(lumberyard_blocked):
        if 0 <= r < ROWS and 0 <= c < COLS and MAP[r][c] == 3:
            MAP[r][c] = 0
    lumberyard_blocked.clear()
    lumberyards.clear()
    wood_stock = 0
    _wood_timer_acc = 0.0
    cancel_fusion_selection()
    poison_clouds.clear()
    globals()['current_spawns'] = None
    globals()['next_spawns'] = None
    globals()['_spawn_rot'] = 0
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
    global hand, gold, selected_card, lumberyards
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
                max_lv = get_max_tower_level(t.get('type','arrow'))
                if t.get('level', 0) >= max_lv:
                    add_notice("此塔已達最高等級", (255,180,120))
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
            if t.get('element'):
                if t['element'] == card:
                    add_notice("此塔已擁有相同元素", (255,180,120))
                else:
                    add_notice("此塔已有其他元素，無法覆蓋", (255,180,120))
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
                "thunder": "thunder",
                "ice": "ice",
                "poison": "poison",
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

    # 伐木場卡：將區塊標記為不可建造
    if card == "lumberyard":
        if gold < CARD_COST_DRAW:
            add_notice(f"金幣不足：建造伐木場需要 ${CARD_COST_DRAW}", (255,120,120))
            return
        if not in_bounds(r, c):
            add_notice("超出地圖範圍", (255,120,120))
            return
        if any(t['r'] == r and t['c'] == c for t in towers):
            add_notice("此處已有防禦塔，無法建造伐木場", (255,120,120))
            return
        tile = MAP[r][c]
        if tile == 1:
            add_notice("此處是道路，無法建立伐木場", (255,120,120))
            return
        if tile == 2:
            add_notice("此處已有障礙物", (255,120,120))
            return
        if tile == 3 and (r, c) not in lumberyards:
            add_notice("此處不可建造伐木場", (255,120,120))
            return
        if tile == 3 and (r, c) in lumberyards:
            add_notice("此格已建有伐木場", (255,180,120))
            return
        gold -= CARD_COST_DRAW
        hand.pop(card_index)
        selected_card = None
        if tile != 3:
            MAP[r][c] = 3
            lumberyard_blocked.add((r, c))
        lumberyards.add((r, c))
        add_notice("伐木場建造完成，此處不可再建塔", (170,220,255))
        return

    add_notice("沒有選到已建塔的格子可升級", (255,120,120))
#-----------

# =========================
# 遊戲狀態切換輔助
def start_game():
    global game_state
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass
    reset_game()           # 重置資源與佈局
    game_state = GAME_PLAY # 進入遊戲（預設暫停狀態，等玩家按 Space/N）


def go_menu():
    global game_state, running
    running = False
    game_state = GAME_MENU
    # ensure BGM resumes on returning to main menu
    try:
        if (not IS_WEB) and os.path.exists(BGM_PATH):
            if not pygame.mixer.music.get_busy():
                pygame.mixer.music.play(-1)
    except Exception:
        pass


def handle_keys(ev):
    global game_state, running, speed, sel, selected_map_idx
    if talent_ui_active:
        if ev.key in (pygame.K_1, pygame.K_KP1):
            accept_talent_choice(0)
        elif ev.key in (pygame.K_2, pygame.K_KP2):
            accept_talent_choice(1)
        elif ev.key in (pygame.K_3, pygame.K_KP3):
            accept_talent_choice(2)
        elif ev.key == pygame.K_ESCAPE:
            close_talent_selection()
        return
    if fusion_active:
        if ev.key == pygame.K_ESCAPE:
            cancel_fusion_selection()
        return
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
    elif ev.key == pygame.K_f:
        mods = pygame.key.get_mods()
        mult = WOOD_REPAIR_LIMIT_PER_CLICK if (mods & pygame.KMOD_SHIFT) else 1
        repair_castle_with_wood(mult)

def handle_click(pos):
    global sel, game_state, selected_card, hand, gold, effects
    mx, my = pos

    if talent_ui_active:
        for rect, idx in talent_ui_rects:
            if rect.collidepoint(mx, my):
                sfx(SFX_CLICK)
                accept_talent_choice(idx)
                return
        if talent_panel_rect and not talent_panel_rect.collidepoint(mx, my):
            sfx(SFX_CLICK)
            close_talent_selection()
        return

    if fusion_active:
        handle_fusion_click(pos)
        return

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
        go_menu()
        return

    # --- 遊戲中：去抖以防止誤觸，但允許「選牌後馬上點地圖」 ---
    global _last_click_ts
    now = pygame.time.get_ticks()
    if now - _last_click_ts < CLICK_DEBOUNCE_MS:
        return
    _last_click_ts = now

    if WOOD_REPAIR_BTN_RECT and WOOD_REPAIR_BTN_RECT.collidepoint(mx, my):
        sfx(SFX_CLICK)
        mods = pygame.key.get_mods()
        mult = WOOD_REPAIR_LIMIT_PER_CLICK if (mods & pygame.KMOD_SHIFT) else 1
        repair_castle_with_wood(mult)
        return
    if FUSION_BTN_RECT and FUSION_BTN_RECT.collidepoint(mx, my):
        start_fusion_selection()
        return

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
                    if talent_state:
                        bonus = talent_state.get('economy', {}).get('coin_card_bonus', 0)
                        amt += bonus
                        amt = max(0, amt)
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
    if talent_ui_active:
        close_talent_selection()
        return
    if fusion_active:
        cancel_fusion_selection()
        return
    mx, my = pos
    # 只處理在遊戲中
    if game_state == GAME_HELP:
        go_menu()
        return
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

    # 生成不可建造區域（GREY）：隨機挑選部分 0 格標記為 3
    # 避開：道路(1)、主堡(2)、最上/最下列，以免擋住關鍵區域
    zero_cells = [(r, c) for r in range(rows) for c in range(cols)
                  if m[r][c] == 0 and r not in (0, rows-1)]
    random.shuffle(zero_cells)
    # 目標覆蓋率：依地圖大小取 10% 左右
    target = max(1, int(len(zero_cells) * 0.12))
    placed = 0
    for r, c in zero_cells:
        # 保留城堡周圍 1 格與道路鄰近 1 格，以利建塔
        if abs(r - CASTLE_ROW) + abs(c - CASTLE_COL) <= 1:
            continue
        near_road = False
        for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
            rr, cc = r+dr, c+dc
            if 0 <= rr < rows and 0 <= cc < cols and m[rr][cc] == 1:
                near_road = True; break
        if near_road:
            continue
        m[r][c] = 3
        placed += 1
        if placed >= target:
            break

    MAP = m
    return True

def main():
    global tick, life, running, next_spawns, game_state
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
                spawn_logic(); move_creeps(); towers_step(); bullets_step(); poison_clouds_step()
        # 無論是否暫停：當不再出怪且場上沒有怪時，才抽下一波預告出口（支援多出口）
        if not wave_incoming and not creeps:
            if talent_runtime.get('last_cleared_wave', 0) < wave:
                talent_on_wave_cleared()
                talent_runtime['last_cleared_wave'] = wave
            maybe_offer_talent()
        if not wave_incoming and next_spawns is None and not creeps and SPAWNS:
            next_spawns = choose_wave_spawns()

        if BG_IMG:
            screen.blit(BG_IMG, (0,0))
        else:
            screen.fill(BG)
        draw_panel(); draw_world(); draw_hand_bar()
        draw_effects()
        if fusion_active:
            draw_fusion_overlay()
        if talent_ui_active:
            draw_talent_overlay()
        if life<=0:
            s = pygame.Surface((W,H), pygame.SRCALPHA); s.fill((0,0,0,160)); screen.blit(s,(0,0))
            txt = BIG.render("Game Over - 按 R 重來", True, TEXT); rect = txt.get_rect(center=(W//2, H//2)); screen.blit(txt, rect)
        pygame.display.flip()
        dt = clock.tick(60)
        if running and life>0:
            update_lumberyards(dt)

if __name__ == "__main__":
    main()
