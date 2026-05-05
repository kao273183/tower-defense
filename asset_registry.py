# -*- coding:utf-8 -*-
"""
資源路徑單一來源（Single Source of Truth）

未來換素材包（例如下載 Kenney TD pack 後）只要編輯這個檔。
所有 main.py / card_renderer.py 內的硬編碼路徑都從這裡取值。

結構：
  IMAGES   : 所有圖片 (key -> 路徑)
  SOUNDS   : 所有音效
  FONTS    : 字型
  MAPS     : 地圖檔
  THEMES   : 主題切換（節慶用）

API：
  img(key)   等同 IMAGES.get(key, '')
  sfx(key)   等同 SOUNDS.get(key, '')
"""

import os

# Kenney TD pack：實際使用的 6 張已複製到 assets/pic/kenney/
# （原始包含 299 張，全包進 web bundle 沒必要；放短路徑也避開 pygbag
#  對含空格目錄的處理問題。授權見 assets/pic/kenney/License.txt）
_K = 'assets/pic/kenney'

# ---------------------------------------------------------------------------
# 主題：影響 castle / grey 等季節性素材切換
#   'default'   : 一般
#   'halloween' : 萬聖節
#   'christmas' : 聖誕節
# ---------------------------------------------------------------------------
THEME = 'christmas'


# ---------------------------------------------------------------------------
# 圖片
# ---------------------------------------------------------------------------
IMAGES = {
    # === 卡片（手牌列上顯示的卡面 PNG。若 USE_PROCEDURAL_CARDS=True 則改用程式繪製） ===
    'card_basic':    'assets/pic/Basic_Tower.png',
    'card_fire':     'assets/pic/fireCard.png',
    'card_wind':     'assets/pic/WindCard.png',
    'card_water':    'assets/pic/waterCard.png',
    'card_land':     'assets/pic/landCard.png',
    'card_upgrade':  'assets/pic/UpgradeCard.png',
    'card_money1':   'assets/pic/money1.png',
    'card_money2':   'assets/pic/money2.png',
    'card_money3':   'assets/pic/money3.png',
    'card_bg':       'assets/pic/BgCard.png',
    'card_lumberyard': 'assets/pic/lumberyardCard.png',
    'card_thunder':  'assets/pic/lightningCard.png',
    'card_ice':      'assets/pic/iceCard.png',
    'card_poison':   'assets/pic/poisonCard.png',
    'card_skill_frost_field':   'assets/pic/skill_frost_field.png',
    'card_skill_thunder_burst': 'assets/pic/skill_thunder_burst.png',

    # === 怪物 ===
    'monster_grunt':    'assets/pic/monster.png',
    'monster_runner':   'assets/pic/runner.png',
    'monster_brute':    'assets/pic/brute.png',
    'monster_boss':     'assets/pic/boss.png',
    'monster_slime':    'assets/pic/slime.png',
    'monster_bat':      'assets/pic/bat.png',
    'monster_giant':    'assets/pic/giant.png',
    'monster_santelmo': 'assets/pic/santelmo.png',

    # === 塔（基礎等級） ===
    'tower_lv1': 'assets/pic/tower_lv1.png',
    'tower_lv2': 'assets/pic/tower_lv2.png',
    'tower_lv3': 'assets/pic/tower_lv3.png',
    'tower_rocket': 'assets/pic/rocket_tower.png',

    # === 元素塔 ===
    'tower_fire':    'assets/pic/firetower.png',
    'tower_water':   'assets/pic/watertower.png',
    'tower_land':    'assets/pic/landtower.png',
    'tower_wind':    'assets/pic/windtower.png',
    'tower_thunder': 'assets/pic/thundertower.png',
    'tower_ice':     'assets/pic/icetower.png',
    'tower_poison':  'assets/pic/poisontower.png',
    'tower_dark':    'assets/pic/darktower.png',

    # === 建築 ===
    'lumberyard': 'assets/pic/lumberyard.png',

    # === 子彈 / 投射物 ===
    'projectile_fireball':  'assets/pic/fireball.png',
    'projectile_wind':      'assets/pic/wind.png',
    'projectile_ice':       'assets/pic/snowball.png',

    # === 命中 / 死亡 / 特效 ===
    # fx_hit / fx_burn 來自 Kenney pack（風格中性，視覺打擊感更強）
    'fx_hit':       f'{_K}/explosion.png',  # 大型橘色爆炸
    'fx_death':     'assets/pic/dead.png',
    'fx_burn':      f'{_K}/flame.png',       # 火焰
    'fx_ice_hit':   'assets/pic/IcePickhit.png',
    'fx_lightning': 'assets/pic/lightning.png',
    'fx_levelup':   'assets/pic/level-up.png',

    # === 拾取 / 經濟（Kenney 通用 sprite） ===
    'gain_coin':  f'{_K}/coin.png',     # 黃色硬幣
    'gemstone':   f'{_K}/crystal.png',  # 綠水晶簇

    # === UI ===
    'ui_arrow':  'assets/pic/up-arrow.png',
    'ui_play':   'assets/pic/play.png',
    'ui_pause':  'assets/pic/pause.png',

    # === 場景 / 主畫面 ===
    'bg_main': 'assets/pic/bg.jpg',
    'logo':    'assets/pic/logo.png',
    'wall':    f'{_K}/wall_stone.png',  # Kenney 石塊（取代原 wall.png）

    # === 主題相關（會被 THEMED 覆蓋；下面是 default 的值） ===
    'castle': 'assets/pic/castle.png',
    'grey':   f'{_K}/grass.png',  # Kenney 純綠草地（取代 activist.png 作可建造區）
}


# ---------------------------------------------------------------------------
# 主題覆蓋表（只列差異，未列出的沿用 IMAGES 預設）
# ---------------------------------------------------------------------------
THEMED = {
    'default': {},
    'halloween': {
        'castle': 'assets/pic/halloween_castle.png',
    },
    'christmas': {
        'castle': 'assets/pic/christmastown.png',
    },
}


# 保留未套主題前的 base 表，方便切換主題時還原
_BASE_IMAGES = dict(IMAGES)


def _apply_theme(name):
    """重新從 _BASE_IMAGES 套用指定主題。"""
    IMAGES.clear()
    IMAGES.update(_BASE_IMAGES)
    for k, v in THEMED.get(name, {}).items():
        IMAGES[k] = v


_apply_theme(THEME)


# ---------------------------------------------------------------------------
# 音效
# ---------------------------------------------------------------------------
SFX_DIR = 'assets/sfx'

# 全部使用 OGG 並用小寫檔名（pygbag/Web 對 WAV 不友善、檔案大；瀏覽器又區分大小寫）
# 在 desktop 跑 main.py 時若 .ogg 不存在會優雅 fallback（_load_sfx 檢查 os.path.exists）
SOUNDS = {
    'bgm':       os.path.join(SFX_DIR, 'bgmusic_merrychristmas.ogg'),
    'shoot':     os.path.join(SFX_DIR, 'shoot.ogg'),
    'hit':       os.path.join(SFX_DIR, 'hit.ogg'),
    'death':     os.path.join(SFX_DIR, 'death.ogg'),
    'coin':      os.path.join(SFX_DIR, 'coin.ogg'),
    'levelup':   os.path.join(SFX_DIR, 'levelup.ogg'),
    'click':     os.path.join(SFX_DIR, 'click.ogg'),
    'draw':      os.path.join(SFX_DIR, 'draw.ogg'),
}


# ---------------------------------------------------------------------------
# 字型
# ---------------------------------------------------------------------------
FONTS = {
    'emoji':   'assets/font/NotoColorEmoji.ttf',
    'cjk_web': 'assets/font/NotoSansCJK-Regular.otf',  # web 版用
}


# ---------------------------------------------------------------------------
# 地圖
# ---------------------------------------------------------------------------
MAPS = {
    'dir':     'assets/map',
    'default': 'assets/map/map1.txt',
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def img(key, default=''):
    """回傳圖片路徑，找不到回傳 default。"""
    return IMAGES.get(key, default)


def sfx(key, default=''):
    """回傳音效路徑，找不到回傳 default。"""
    return SOUNDS.get(key, default)


def font(key, default=''):
    return FONTS.get(key, default)


def set_theme(name):
    """執行期切換主題。"""
    global THEME
    if name not in THEMED:
        return False
    THEME = name
    _apply_theme(name)
    return True
