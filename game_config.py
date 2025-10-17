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
        'arrow':  [10, 15, 20, 25, 30],
        'rocket': [40, 50, 60, 70, 80],
        'thunder':[40, 50, 60, 70, 80],
    },
    'evolve': {
    'rocket': 60,
    'thunder': 60,
  }
}
#卡片機率
CARD_RATES = [
    {'type': 'basic',   'weight': 45},
    {'type': 'fire',    'weight': 5},
    {'type': 'water',   'weight': 5},
    {'type': 'land',    'weight': 5},
    {'type': 'wind',    'weight': 5},
    {'type': 'upgrade', 'weight': 5},
    {'type': 'lumberyard', 'weight': 10},#伐木場
    {'type': '1money', 'weight': 20},#金幣卡
    {'type': '2money', 'weight': 10},#金幣卡
    {'type': '3money', 'weight': 5},#金幣卡
]

# ==== 怪物成長設定 ====
CREEP_REWARD_GROWTH = 0.02  # 每波擊殺金幣增加 2%
CREEP_ATTACK_GROWTH = 0.02  # 每波攻擊力增加 2%

# ==== 元素融合設定 ====
ELEMENT_FUSIONS = {
    ('fire', 'wind'): 'thunder',
    ('wind','water'): 'ice',
    ('land', 'water'): 'poison',
}

# ===== 塔數值（可獨立調平衡）====# game_config.py
TOWER_LEVEL_RULES = {
    'arrow': {
        'max_level': 5,
        'atk_base': 1,
        'atk_growth': 1,
        'range': [2, 2, 3, 3, 4, 4],
        'rof': [1.0, 1.2, 1.5, 1.8, 2.0, 2.2],
    },
    'rocket': {
        'max_level': 5,
        'atk_base': 3,
        'atk_growth': 1,
        'range': [3, 3, 3, 4, 4, 4],
        'rof': [0.8, 1.0, 1.2, 1.4, 1.6, 1.8],
    },
    'thunder': {
        'max_level': 5,
        'atk_base': 3,
        'atk_growth': 1,
        'range': [3, 3, 4, 4, 5, 5],
        'rof': [1.2, 1.4, 1.6, 1.8, 2.0, 2.2],
    },
    'fire': {
        'max_level': 5,
        'atk_base': 4,
        'atk_growth': 2,
        'range': [3, 3, 4, 4, 4, 5],
        'rof': [1.2, 1.4, 1.6, 1.8, 2.0, 2.2],
    },
    'water': {
        'max_level': 5,
        'atk_base': 2,
        'atk_growth': 1,
        'range': [4, 4, 5, 5, 6, 6],
        'rof': [1.5, 1.7, 1.9, 2.1, 2.3, 2.5],
    },
    'land': {
        'max_level': 5,
        'atk_base': 3,
        'atk_growth': 1,
        'range': [3, 3, 4, 4, 5, 5],
        'rof': [1.0, 1.1, 1.2, 1.3, 1.4, 1.5],
    },
    'wind': {
        'max_level': 5,
        'atk_base': 1,
        'atk_growth': 1,
        'range': [3, 3, 4, 4, 4, 5],
        'rof': [2.0, 2.4, 2.8, 3.2, 3.6, 4.0],
    },
    'ice': {
        'max_level': 5,
        'atk_base': 1,
        'atk_growth': 1,
        'range': [1, 1, 1, 1, 1, 1],
        'rof': [1.5, 1.7, 1.9, 2.1, 2.3, 2.5],
    },
    'poison': {
        'max_level': 5,
        'atk_base': 2,
        'atk_growth': 1,
        'range': [2, 3, 4, 4, 4, 4],
        'rof': [1.0, 1.1, 1.2, 1.3, 1.4, 1.5],
    },
}

# 元素塔圖片設定（可自行新增元素）
ELEMENT_TOWER_IMAGES = {
    'fire':    "assets/pic/firetower.png",
    'water':   "assets/pic/watertower.png",
    'land':    "assets/pic/landtower.png",
    'wind':    "assets/pic/windtower.png",
    'thunder': "assets/pic/thundertower.png",
    'ice':     "assets/pic/icetower.png",
    'poison':  "assets/pic/poisontower.png",
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
    },
    'thunder': {
        'type': 'chain',
        'description': '連鎖閃電攻擊額外敵人',
        'base_targets': 2,
        'targets_per_lv': 1
    },
    'ice': {
        'type': 'freeze',
        'description': '短暫冰凍敵人，等級越高凍結越久',
        'duration': 0.5,
        'duration_per_lv': 0.1
    },
    'poison': {
        'type': 'poison_cloud',
        'description': '在地面形成劇毒霧氣，影響範圍逐級擴大',
        'radius': 2.0,
        'radius_per_lv': 0.5,
        'duration': 2.0,
        'tick_interval': 15,
        'dmg_ratio': 0.3
    }
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
THUNDER_TOWER_IMG_PATH = "assets/pic/thundertower.png"

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
VAMPIRE_USE_IMAGE = True
VAMPIRE_IMG_PATH = "assets/pic/vampire.png"
VAMPIRE_IMG_SIZE = 32
FRANKENSTEIN_USE_IMAGE = True
FRANKENSTEIN_IMG_PATH = "assets/pic/frankenstein.png"
FRANKENSTEIN_IMG_SIZE = 32
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
    "vampire": {
        "name": "吸血鬼",
        "hp": 10,
        "speed": 0.03,
        "reward": 3,
        "attack": 3,
        "color": (74, 68, 64),
        "image": VAMPIRE_IMG_PATH
    },
    "frankenstein": {
        "name": "科學怪人",
        "hp": 25,
        "speed": 0.04,
        "reward": 10,
        "attack": 5,
        "color": (109, 199, 112),
        "image": FRANKENSTEIN_IMG_PATH
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
        all_types = ['slime','santelmo','vampire','pumpkin', 'runner', 'bat', 'giant', 'boss']

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
