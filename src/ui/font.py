import pygame

def get_fonts():
    title = pygame.font.SysFont("Segoe UI", 48, bold=True)
    h2 = pygame.font.SysFont("Segoe UI", 28, bold=True)
    body = pygame.font.SysFont("Segoe UI", 18, bold=False)
    small = pygame.font.SysFont("Segoe UI", 14, bold=False)
    mono = pygame.font.SysFont("Consolas", 20, bold=True)
    return title, h2, body, small, mono
