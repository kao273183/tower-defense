import pygame

class Tower:
    def __init__(self, pos, tower_type="basic"):
        self.pos = pos
        self.type = tower_type
        self.level = 1
        self.damage = 10
        self.cost = 10
        self.image = pygame.image.load("assets/Basic_Tower.png")

    def upgrade(self, element):
        element_map = {
            "fire": ("assets/fireCard.png", 20),
            "wind": ("assets/WindCard.png", 12),
            "water": ("assets/waterCard.png", 10),
            "land": ("assets/landCard.png", 8),
        }
        if element in element_map:
            img, dmg = element_map[element]
            self.image = pygame.image.load(img)
            self.damage = dmg
            self.type = element