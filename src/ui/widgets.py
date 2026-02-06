import pygame
from .theme import CARD2, BORDER, TEXT, ACCENT

def draw_label(surf, text, font, color, pos):
    surf.blit(font.render(text, True, color), pos)

class Button:
    def __init__(self, rect, label, font, on_click, primary=False):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.font = font
        self.on_click = on_click
        self.primary = primary
        self.hover = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.on_click()

    def draw(self, surf):
        color = ACCENT if self.primary else CARD2
        if self.hover:
            color = (min(255, color[0]+12), min(255, color[1]+12), min(255, color[2]+12))
        pygame.draw.rect(surf, color, self.rect, border_radius=14)
        pygame.draw.rect(surf, BORDER, self.rect, width=2, border_radius=14)
        txt = self.font.render(self.label, True, TEXT)
        surf.blit(txt, txt.get_rect(center=self.rect.center))

def draw_vertical_gradient(surf, rect, top_color, bottom_color):
    x, y, w, h = rect
    for i in range(h):
        t = i / max(1, h-1)
        r = int(top_color[0] * (1-t) + bottom_color[0] * t)
        g = int(top_color[1] * (1-t) + bottom_color[1] * t)
        b = int(top_color[2] * (1-t) + bottom_color[2] * t)
        pygame.draw.line(surf, (r,g,b), (x, y+i), (x+w, y+i))

def draw_shadow_card(surf, rect, radius=18, shadow_offset=(0,6), shadow_alpha=90):
    # simple shadow by drawing a semi-transparent rect
    shadow = pygame.Surface((rect.width + 20, rect.height + 20), pygame.SRCALPHA)
    srect = pygame.Rect(10, 10, rect.width, rect.height)
    pygame.draw.rect(shadow, (0,0,0,shadow_alpha), srect, border_radius=radius)
    surf.blit(shadow, (rect.x + shadow_offset[0]-10, rect.y + shadow_offset[1]-10))
