# ==== 視窗 / 地圖 ====
import random

W = 960
H = 640
CELL = 40
COLS = 15
ROWS = 9
# 不填會自動置中；要固定就直接填
# LEFT = 80
# TOP  = 60

# ==== 地圖檔 ====
MAP_USE_FILE  = True
MAP_FILE_PATH = "assets/map/map1.txt"   # 0=地, 1=路, 2=牆, S=出怪, C=主堡

# ==== 主堡設定 ====
CASTLE = {
    'hp': 50,
    'max_hp': 50,
    'level': 1,
    'upgrade_cost': 20,
    'hp_increase': 20,
}

# ==== 經濟 / 價格 ====
BUILD_COST = 10
PRICES = {
    'build': {
        'arrow': BUILD_COST,
        # 'rocket': 12,
        # 'thunder': 12,
    },
    'upgrade': {
        'arrow':  [10, 15, 20],
        'rocket': [40, 50],
        'thunder':[40, 50],
    },
    'evolve': {
    'rocket': 60,
    'thunder': 60,
  }
}
#卡片機率
CARD_RATES = [
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

# ===== 塔數值（可獨立調平衡）====# game_config.py
TOWER_TYPES = {
    'arrow': {
        0: {'atk': 1, 'range': 2, 'rof': 1.0},
        1: {'atk': 2, 'range': 2, 'rof': 1.2},
        2: {'atk': 3, 'range': 3, 'rof': 1.6},
        3: {'atk': 4, 'range': 3, 'rof': 2.0},
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

# ==== 元素塔特效 ====
ELEMENT_EFFECTS = {
    'fire': {
        'type': 'burn',
        'description': '造成爆炸傷害並使附近怪物灼傷',
        'duration': 1.0,      # 持續 1 秒
        'scale_per_lv': 0.01  # 每級增加 1% 秒數
    },
    'water': {
        'type': 'slow',
        'description': '減緩敵人移動速度',
        'duration': 1.0,      # 持續 1 秒
        'scale_per_lv': 0.01  # 每級增加 1% 秒數
    },
    'land': {
        'type': 'bleed',
        'description': '造成流血持續傷害',
        'duration': 0.5,      # 持續 0.5 秒
        'scale_per_lv': 0.015 # 每級增加 1.5% 秒數
    },
    'wind': {
        'type': 'knockback',
        'description': '擊退敵人一格',
        'base_knockback': 1,  # 初始擊退格數
        'scale_per_lv': 1     # 每級增加 1 格擊退距離
    }
}
TOWER_ATK = {
    'arrow':  [2, 3, 4, 5],   # Lv0~Lv3
    'rocket': [4, 6, 8, 10],
    'thunder':[3, 4, 5, 7],
}
TOWER_ATK_MULT = {
    'arrow': 1.2,    # 全等級 +20%
    'rocket': 0.9,   # 全等級 -10%
}
# ==== 怪物數值（可獨立調平衡）====
CREEP = {
    'slime': {'hp': 6,  'speed': .020, 'reward': 1, 'color': (120, 255, 120)},
    'runner':{'hp': 5,  'speed': .035, 'reward': 1, 'color': (34,179,230)},
    'brute': {'hp': 12, 'speed': .017, 'reward': 2, 'color': (239,106,106)},
    'boss':  {'hp': 40, 'speed': .012, 'reward': 6, 'color': (139,92,246)},
}

# ==== Boss 波次 ====
BOSS_WAVES = {w for w in range(10, 999, 10)}
BOSS_SPAWN_INDEX = 8

# ==== UI / 資產：圖片路徑與大小 ====
# 背景與 Logo
BG_IMG_PATH   = "assets/pic/bg.jpg"
LOGO_IMG_PATH = "assets/pic/logo.png"
LOGO_MAX_W    = 420

# 主選單右上狀態圖示
STATUS_ICON_SIZE   = 24
STATUS_ICON_MARGIN = 12
PLAY_IMG_PATH  = "assets/pic/play.png"
PAUSE_IMG_PATH = "assets/pic/pause.png"

# 預告箭頭
ARROW_IMG_PATH = "assets/pic/up-arrow.png"
ARROW_IMG_SIZE = 28

# 主堡 / 牆壁
CASTLE_IMG_PATH = "assets/pic/halloween_castle.png"
WALL_IMG_PATH   = "assets/pic/wall.png"
CASTLE_IMG_SIZE = 48
WALL_IMG_SIZE   = 40

# 塔圖片
TOWER_USE_IMAGES = True
TOWER_IMG_SIZE   = 36
TOWER_IMG_PATHS = {
    0: "assets/pic/tower_lv1.png",
    1: "assets/pic/tower_lv2.png",
    2: "assets/pic/tower_lv3.png",
    3: "assets/pic/tower_lv3.png",
}
ROCKET_TOWER_IMG_PATH  = "assets/pic/firetower.png"
WATER_TOWER_IMG_PATH = "assets/pic/watertower.png"
LAND_TOWER_IMG_PATH  = "assets/pic/landtower.png"
WIND_TOWER_IMG_PATH  = "assets/pic/windtower.png"
#金幣卡
MONEY1_IMG_PATH = "assets/pic/money1.png"
MONEY2_IMG_PATH = "assets/pic/money2.png"
MONEY3_IMG_PATH = "assets/pic/money3.png"

# 怪物圖片----
SLIME_USE_IMAGE  = True
SLIME_IMG_PATH   = "assets/pic/slime.png"
SLIME_IMG_SIZE   = 32
RUNNER_USE_IMAGE = True
RUNNER_IMG_PATH  = "assets/pic/runner.png"
RUNNER_IMG_SIZE  = 32
BRUTE_USE_IMAGE  = True
BRUTE_IMG_PATH   = "assets/pic/brute.png"
BRUTE_IMG_SIZE   = 36
BAT_USE_IMAGE    = True
BAT_IMG_PATH     = "assets/pic/bat.png"
BAT_IMG_SIZE     = 32
GIANT_USE_IMAGE  = True
GIANT_IMG_PATH   = "assets/pic/giant.png"
GIANT_IMG_SIZE   = 32
SANTELMO_USE_IMAGE = True
SANTELMO_IMG_PATH = "assets/pic/santelmo.png"
SANTELMO_IMG_SIZE = 32
PUMPKIN_USE_IMAGE = True
PUMPKIN_IMG_PATH = "assets/pic/pumpkin.png"
PUMPKIN_IMG_SIZE = 32

#BOSS
BOSS_USE_IMAGE   = True
BOSS_IMG_PATH    = "assets/pic/boss.png"
BOSS_IMG_SIZE    = 44

# 擊中 / 死亡 / 掉落金幣
HIT_USE_IMAGE = True
HIT_IMG_PATH  = "assets/pic/blast.png"
HIT_IMG_SIZE  = 32
DEATH_USE_IMAGE = True
DEATH_IMG_PATH  = "assets/pic/dead.png"
DEATH_IMG_SIZE  = 40
GAIN_USE_IMAGE  = True
GAIN_IMG_PATH   = "assets/pic/game-coin.png"
GAIN_IMG_SIZE   = 20
GAIN_TTL        = 30
GAIN_RISE       = 0.6
GAIN_TEXT_COLOR = (255, 234, 140)

# 升級特效
LEVELUP_USE_IMAGE = True
LEVELUP_IMG_PATH  = "assets/pic/level-up.png"
LEVELUP_IMG_SIZE  = 40
LEVELUP_TTL       = 24
LEVELUP_RISE      = 0.5

# ==== 音效 / 音樂 ====
SFX_DIR = "assets/sfx"
BGM_PATH = "assets/sfx/bgm.mp3"
SFX_VOL = 0.6
BGM_VOL = 0.35

# ==== 通知（可調位置與對齊）====
NOTICE_X = 16
# 例如要靠近面板下方可改：NOTICE_Y = TOP + 34
# 或固定到畫面底部：NOTICE_Y = H - 120
NOTICE_Y = 500
NOTICE_LINE_GAP = 22
NOTICE_ALIGN_DEFAULT = 'left'  # 'left' | 'center' | 'right'


# === 怪物設定 ===
CREEP_CONFIG = {
    "slime": {
        "name": "史萊姆",
        "hp": 5,
        "speed": 0.01,
        "reward": 1,
        "attack": 1,
        "color": (120, 255, 120),
        "image": SLIME_IMG_PATH
    },
    "santelmo": {
        "name": "鬼火",
        "hp": 6,
        "speed": 0.01,
        "reward": 2,
        "attack": 2,
        "color": (255, 34, 63),
        "image": SANTELMO_IMG_PATH
    },
    "pumpkin": {
        "name": "南瓜怪",
        "hp": 7,
        "speed": 0.02,
        "reward": 2,
        "attack": 2,
        "color": (255, 137, 34),
        "image": PUMPKIN_IMG_PATH
    },
    "runner": {
        "name": "鬼魂",
        "hp": 5,
        "speed": 0.02,
        "reward": 2,
        "attack": 2,
        "color": (180, 130, 90),
        "image": RUNNER_IMG_PATH
    },
    "bat": {
        "name": "蝙蝠",
        "hp": 5,
        "speed": 0.02,
        "reward": 1,
        "attack": 1,
        "color": (120, 120, 220),
        "image": BAT_IMG_PATH
    },
    "giant": {
        "name": "巨人",
        "hp": 30,
        "speed": 0.05,
        "reward": 10,
        "attack": 5,
        "color": (200, 80, 80),
        "image":GIANT_IMG_PATH
    },
    "boss": {
        "name": "魔王",
        "hp": 150,
        "speed": 0.06,
        "reward": 30,
        "attack": 20,
        "color": (255, 60, 60)
    }
}

# 波次配置（每10波出現 Boss）
"""def get_wave_creeps(wave_num: int):
    creeps = []
    if wave_num % 10 == 0:
        creeps.append({"type": "boss", "count": 1})
    else:
        base = ["slime", "runner", "bat","giant"]
        for _ in range(3 + wave_num // 2):
            ctype = random.choice(base)
            creeps.append({"type": ctype, "count": 1})
    return creeps"""

import random

def get_wave_creeps(wave: int):
    """
    隨機生成該波怪物配置。
    - 每 10 波出現一隻 boss。
    - 其他波：隨機產生 10~20 隻非 boss 怪物。
    """
    if wave > 0 and wave % 10 == 0:
        # 每 10 波 → 只出現 1 隻 Boss
        return [{'type': 'boss', 'count': 1}]

    # 可用的非 boss 怪物種類（從 CREEP_CONFIG 取）
    try:
        all_types = list(CREEP_CONFIG.keys())
    except NameError:
        all_types = ['slime','santelmo','pumpkin', 'runner', 'bat', 'giant', 'boss']

    non_boss = [k for k in all_types if k != 'boss']
    if not non_boss:
        non_boss = ['slime']

    # 這一波的總怪數 10~20
    total = random.randint(10, 30)
    plan = []

    # 將 total 拆分成隨機群組（2~5隻），並分配種類
    remain = total
    while remain > 0:
        chunk = random.randint(2, 5)
        if chunk > remain:
            chunk = remain
        kind = random.choice(non_boss)
        plan.append({'type': kind, 'count': chunk})
        remain -= chunk
    print(f"Wave {wave}: {plan}")

    # 35% 機率將其中一組替換為較強怪物（runner/bat/giant）
    stronger_pool = [k for k in non_boss if k in ('runner','pumpkin','santelmo', 'bat', 'giant')]
    if stronger_pool and len(plan) >= 2 and random.random() < 0.35:
        idx = random.randrange(len(plan))
        plan[idx]['type'] = random.choice(stronger_pool)

    # 確保至少包含常見種類（若有提供）
    for must_have in ('slime', 'bat'):
        if must_have in non_boss and all(p['type'] != must_have for p in plan):
            if plan:
                plan[random.randrange(len(plan))]['type'] = must_have
            else:
                plan.append({'type': must_have, 'count': max(2, total // 3)})

    return plan
