# ==== 視窗 / 地圖 ====
from main import LAND


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
    'thunder': {
        0: {'atk': 3, 'range': 4, 'rof': 2.5},
        1: {'atk': 4, 'range': 5, 'rof': 3.0},
        2: {'atk': 5, 'range': 5, 'rof': 3.5},
        3: {'atk': 6, 'range': 6, 'rof': 4.0},
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
    'grunt': {'hp': 6,  'speed': .020, 'reward': 1, 'color': (244,162,75)},
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
CASTLE_IMG_PATH = "assets/pic/castle.png"
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

# 怪物圖片
GRUNT_USE_IMAGE  = True
GRUNT_IMG_PATH   = "assets/pic/monster.png"
GRUNT_IMG_SIZE   = 32
RUNNER_USE_IMAGE = True
RUNNER_IMG_PATH  = "assets/pic/runner.png"
RUNNER_IMG_SIZE  = 32
BRUTE_USE_IMAGE  = True
BRUTE_IMG_PATH   = "assets/pic/brute.png"
BRUTE_IMG_SIZE   = 36
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