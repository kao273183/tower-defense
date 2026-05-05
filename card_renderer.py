# -*- coding:utf-8 -*-
"""
程式化卡片繪製：給定卡名 / 顯示名 / 費用 / icon 圖層，生成統一風格的卡面 Surface。

不引用 main.py，所有依賴透過參數傳入，避免循環匯入。
"""
import os
import pygame


# 元素 → (亮色, 暗色, 重點色)
ELEMENT_COLORS = {
    "fire":     ((255, 120,  60), (140,  30,  10), (255, 200,  80)),
    "water":    (( 90, 170, 255), ( 20,  50, 130), (180, 230, 255)),
    "wind":     ((180, 240, 200), ( 40, 110,  80), (220, 255, 230)),
    "land":     ((190, 150,  90), ( 90,  60,  30), (240, 220, 160)),
    "thunder":  ((255, 230,  90), (140,  90,  30), (255, 255, 200)),
    "ice":      ((200, 235, 255), ( 60, 130, 200), (240, 250, 255)),
    "poison":   ((150, 220,  80), ( 50, 100,  30), (210, 255, 150)),
    "basic":    ((200, 205, 215), ( 70,  75,  85), (240, 240, 245)),
    "upgrade":  ((255, 210,  90), (160, 110,  10), (255, 240, 180)),
    "1money":   ((255, 220, 110), (160, 110,  20), (255, 245, 200)),
    "2money":   ((255, 215, 100), (155, 105,  15), (255, 240, 190)),
    "3money":   ((255, 210,  90), (150, 100,  10), (255, 235, 180)),
    "lumberyard":((180, 140,  80), ( 80,  55,  25), (220, 190, 130)),
    "skill_frost_field":   ((170, 210, 255), ( 60,  90, 180), (220, 235, 255)),
    "skill_thunder_burst": ((230, 180, 255), (100,  60, 180), (250, 220, 255)),
}

DEFAULT_COLORS = ((180, 180, 190), ( 70,  70,  80), (220, 220, 225))


# 元素稀有度（影響右下星數）
RARITY = {
    "basic":   1,
    "fire": 2, "water": 2, "wind": 2, "land": 2,
    "ice": 2, "poison": 2, "thunder": 3,
    "upgrade": 2,
    "1money": 1, "2money": 2, "3money": 3,
    "lumberyard": 2,
    "skill_frost_field": 3,
    "skill_thunder_burst": 3,
}


# 沒有 icon 圖時的字符後備
GLYPH_FALLBACK = {
    "fire": "火", "water": "水", "wind": "風", "land": "土",
    "thunder": "雷", "ice": "冰", "poison": "毒",
    "basic": "塔", "upgrade": "↑",
    "1money": "$", "2money": "$$", "3money": "$$$",
    "lumberyard": "木",
    "skill_frost_field": "❆",
    "skill_thunder_burst": "⚡",
}


# 卡名 → 推薦 icon 圖路徑（優先使用塔本體圖而非卡片圖，避免「卡上有卡」）
DEFAULT_ICON_PATHS = {
    "fire":      "assets/pic/firetower.png",
    "water":     "assets/pic/watertower.png",
    "wind":      "assets/pic/windtower.png",
    "land":      "assets/pic/landtower.png",
    "thunder":   "assets/pic/thundertower.png",
    "ice":       "assets/pic/icetower.png",
    "poison":    "assets/pic/poisontower.png",
    "basic":     "assets/pic/tower_lv1.png",
    "upgrade":   "assets/pic/up-arrow.png",
    "1money":    "assets/pic/game-coin.png",
    "2money":    "assets/pic/game-coin.png",
    "3money":    "assets/pic/game-coin.png",
    "lumberyard":"assets/pic/lumberyard.png",
    "skill_frost_field":   "assets/pic/IcePick.png",
    "skill_thunder_burst": "assets/pic/lightning.png",
}


_icon_cache = {}


def _load_icon(name):
    """載入並快取 icon 圖。回傳 Surface 或 None。"""
    if name in _icon_cache:
        return _icon_cache[name]
    path = DEFAULT_ICON_PATHS.get(name)
    surf = None
    if path and os.path.exists(path):
        try:
            surf = pygame.image.load(path).convert_alpha()
        except Exception:
            surf = None
    _icon_cache[name] = surf
    return surf


def _draw_vgradient(surf, top_color, bottom_color, rect=None):
    """在 surf 上畫垂直漸層（不影響 alpha）。"""
    rect = rect or surf.get_rect()
    h = rect.height
    if h <= 0:
        return
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        pygame.draw.line(surf, (r, g, b), (rect.x, rect.y + y), (rect.right - 1, rect.y + y))


def _rounded_mask(size, radius):
    """產生圓角遮罩（白色不透明 + 透明背景）。"""
    w, h = size
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, w, h), border_radius=radius)
    return mask


def render_card(name, display_name, cost, size, fonts,
                icon_surface=None, rarity=None, money_amount=None):
    """
    參數：
      name           : 卡片內部名稱（用於配色 / icon 對照）
      display_name   : 顯示文字（中文）
      cost           : 費用（int 或 None；0 / None 不顯示）
      size           : (w, h) 卡片尺寸
      fonts          : dict，包含 'name' / 'small' / 'glyph' 三個 pygame.font.Font
      icon_surface   : 自訂 icon 圖，None 則使用預設對照路徑
      rarity         : 1~3 星，None 則查 RARITY 表
      money_amount   : 金錢卡左下角要顯示的金額數字（覆蓋 cost 顯示）
    """
    w, h = size
    bright, dark, accent = ELEMENT_COLORS.get(name, DEFAULT_COLORS)
    if rarity is None:
        rarity = RARITY.get(name, 1)
    radius = max(6, min(12, w // 8))

    # === 1. 背景漸層（先畫到 full rect，再用圓角 mask 裁切） ===
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    _draw_vgradient(surf, bright, dark)
    # 圓角裁切：把外圈 alpha 變 0
    mask = _rounded_mask((w, h), radius)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    # === 2. 內框 ===
    inner_rect = pygame.Rect(3, 3, w - 6, h - 6)
    pygame.draw.rect(surf, (0, 0, 0, 90), inner_rect, 1, border_radius=radius - 2)

    # === 3. 標題列 ===
    title_h = max(18, int(h * 0.18))
    title_rect = pygame.Rect(4, 4, w - 8, title_h)
    title_bg = pygame.Surface(title_rect.size, pygame.SRCALPHA)
    title_bg.fill((0, 0, 0, 130))
    surf.blit(title_bg, title_rect.topleft)

    f_name = fonts.get('name')
    if f_name:
        title_img = f_name.render(display_name, True, accent)
        # 太長就縮
        if title_img.get_width() > title_rect.width - 4:
            scale = (title_rect.width - 4) / title_img.get_width()
            new_w = int(title_img.get_width() * scale)
            new_h = int(title_img.get_height() * scale)
            title_img = pygame.transform.smoothscale(title_img, (new_w, new_h))
        surf.blit(title_img, (
            title_rect.centerx - title_img.get_width() // 2,
            title_rect.centery - title_img.get_height() // 2,
        ))

    # === 4. 中央 icon 區 ===
    bottom_h = max(16, int(h * 0.16))
    icon_rect = pygame.Rect(6, title_rect.bottom + 2,
                            w - 12, h - title_rect.bottom - 2 - bottom_h - 4)
    if icon_rect.height > 0:
        # 內凹深色面板
        panel = pygame.Surface(icon_rect.size, pygame.SRCALPHA)
        panel.fill((0, 0, 0, 70))
        surf.blit(panel, icon_rect.topleft)
        pygame.draw.rect(surf, (255, 255, 255, 30), icon_rect, 1, border_radius=4)

        # icon 圖：傳入 > 預設路徑 > 字符後備
        icon = icon_surface if icon_surface is not None else _load_icon(name)
        if icon is not None:
            iw, ih = icon.get_size()
            scale = min(icon_rect.width / iw, icon_rect.height / ih) * 0.85
            new_size = (max(1, int(iw * scale)), max(1, int(ih * scale)))
            scaled = pygame.transform.smoothscale(icon, new_size)
            surf.blit(scaled, scaled.get_rect(center=icon_rect.center))
        else:
            # 字符後備
            f_glyph = fonts.get('glyph') or f_name
            if f_glyph:
                glyph = GLYPH_FALLBACK.get(name, '?')
                gimg = f_glyph.render(glyph, True, accent)
                # 太大就縮
                if gimg.get_width() > icon_rect.width - 4 or gimg.get_height() > icon_rect.height - 4:
                    s = min((icon_rect.width - 4) / gimg.get_width(),
                            (icon_rect.height - 4) / gimg.get_height())
                    gimg = pygame.transform.smoothscale(
                        gimg, (max(1, int(gimg.get_width() * s)),
                               max(1, int(gimg.get_height() * s))))
                surf.blit(gimg, gimg.get_rect(center=icon_rect.center))

    # === 5. 底部資訊列 ===
    info_rect = pygame.Rect(4, h - 4 - bottom_h, w - 8, bottom_h)
    info_bg = pygame.Surface(info_rect.size, pygame.SRCALPHA)
    info_bg.fill((0, 0, 0, 130))
    surf.blit(info_bg, info_rect.topleft)

    f_small = fonts.get('small') or f_name
    # 左：費用 / 金錢
    label = None
    if money_amount is not None:
        label = f"+${money_amount}"
        label_color = (255, 230, 100)
    elif cost:
        label = f"${cost}"
        label_color = (255, 230, 100)
    if label and f_small:
        timg = f_small.render(label, True, label_color)
        surf.blit(timg, (info_rect.x + 4,
                        info_rect.centery - timg.get_height() // 2))
    # 右：稀有度星
    if f_small and rarity > 0:
        stars = '★' * rarity + '☆' * max(0, 3 - rarity)
        simg = f_small.render(stars, True, accent)
        surf.blit(simg, (info_rect.right - simg.get_width() - 4,
                         info_rect.centery - simg.get_height() // 2))

    # === 6. 外框 ===
    pygame.draw.rect(surf, (15, 15, 25), (0, 0, w, h), 2, border_radius=radius)

    return surf


def render_card_back(size, fonts):
    """抽卡堆背面（同風格）。"""
    w, h = size
    bright = (60, 90, 160)
    dark = (20, 30, 70)
    accent = (200, 220, 255)
    radius = max(6, min(12, w // 8))

    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    _draw_vgradient(surf, bright, dark)
    mask = _rounded_mask((w, h), radius)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    # 中央菱形紋飾
    cx, cy = w // 2, h // 2
    s = min(w, h) // 3
    pygame.draw.polygon(surf, accent + (180,),
                        [(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)], 2)
    pygame.draw.polygon(surf, accent + (120,),
                        [(cx, cy - s // 2), (cx + s // 2, cy), (cx, cy + s // 2), (cx - s // 2, cy)], 1)

    f_name = fonts.get('name')
    if f_name:
        timg = f_name.render('抽 卡', True, accent)
        surf.blit(timg, (cx - timg.get_width() // 2, h - timg.get_height() - 6))

    pygame.draw.rect(surf, (15, 15, 25), (0, 0, w, h), 2, border_radius=radius)
    return surf


def make_fonts(font_path, size_w, size_h):
    """便利：依卡片尺寸給出合理的字級。"""
    if font_path:
        name_size = max(12, min(18, size_h // 7))
        small_size = max(10, min(14, size_h // 9))
        glyph_size = max(28, min(64, size_h // 2))
        return {
            'name':  pygame.font.Font(font_path, name_size),
            'small': pygame.font.Font(font_path, small_size),
            'glyph': pygame.font.Font(font_path, glyph_size),
        }
    else:
        return {
            'name':  pygame.font.SysFont('arial', max(12, size_h // 7), True),
            'small': pygame.font.SysFont('arial', max(10, size_h // 9)),
            'glyph': pygame.font.SysFont('arial', max(28, size_h // 2), True),
        }
