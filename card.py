import random, pygame

CARD_TYPES = {
    "fire": {"img": "assets/pic/fireCard.png", "cost": 5},
    "wind": {"img": "assets/pic/WindCard.png", "cost": 5},
    "water": {"img": "assets/pic/waterCard.png", "cost": 5},
    "land": {"img": "assets/pic/landCard.png", "cost": 5},
    "basic": {"img": "assets/pic/Basic_Tower.png", "cost": 10}
}

class CardManager:
    def __init__(self, player_gold):
        self.gold = player_gold
        self.cards = []  # 玩家擁有的卡片

    def draw_card(self):
        if self.gold < 5:
            return None, "金幣不足"
        self.gold -= 5
        kind = random.choice(list(CARD_TYPES.keys()))
        card_info = CARD_TYPES[kind]
        self.cards.append(kind)
        return card_info, f"抽到 {kind} 元素卡！"

    def use_card(self, kind):
        if kind in self.cards:
            self.cards.remove(kind)
            return True
        return False