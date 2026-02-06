import math
import random
import pygame

# Colorful Arcade (Kids Mode) - Visual only
# No game logic here: just drawing + particles.

ARCADE_COLORS = [
    (255, 86, 161),   # pink
    (73, 207, 255),   # cyan
    (124, 255, 170),  # mint
    (255, 231, 84),   # yellow
    (185, 122, 255),  # purple
    (255, 153, 88),   # orange
]

def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)

class ArcadeFX:
    def __init__(self, w:int, h:int):
        self.w, self.h = w, h
        self.t = 0.0
        self.particles = []   # (x,y,vx,vy,life,size,color,kind)
        self.trail = [[], []] # per player: list[(x,y,life)]
        self.pulse = [0.0, 0.0]
        self.flash = 0.0

    def reset(self):
        """Clear all visual FX state (particles/trails/pulses)."""
        self.t = 0.0
        self.particles = []
        self.trail = [[], []]
        self.pulse = [0.0, 0.0]
        self.flash = 0.0

    def update(self, dt:float):
        dt = float(dt)
        self.t += dt
        # decay pulse/flash
        for i in (0,1):
            self.pulse[i] = max(0.0, self.pulse[i]-dt*2.5)
        self.flash = max(0.0, self.flash-dt*2.0)

        # update particles
        newp=[]
        for x,y,vx,vy,life,size,col,kind in self.particles:
            life -= dt
            if life <= 0: 
                continue
            x += vx*dt
            y += vy*dt
            vy += 900*dt  # gravity
            vx *= (0.995**(dt*60))
            size *= (0.998**(dt*60))
            newp.append((x,y,vx,vy,life,size,col,kind))
        self.particles = newp

        # update trails
        for pid in (0,1):
            self.trail[pid] = [(x,y,l-dt) for (x,y,l) in self.trail[pid] if (l-dt) > 0]

    def add_trail(self, pid:int, pos):
        x,y = pos
        self.trail[pid].append((float(x), float(y), 0.22))
        # keep small
        if len(self.trail[pid]) > 18:
            self.trail[pid] = self.trail[pid][-18:]

    def on_hover(self, pid:int):
        self.pulse[pid] = min(1.0, self.pulse[pid] + 0.25)

    def on_click(self, pid:int, pos):
        self.pulse[pid] = 1.0
        self._burst(pos, n=18, speed=420, life=0.55, spread=1.2, kind="spark")

    def on_success(self, pos):
        self.flash = 1.0
        self._burst(pos, n=90, speed=520, life=0.85, spread=2.6, kind="confetti")

    def _burst(self, pos, n=30, speed=400, life=0.7, spread=2.0, kind="spark"):
        x0,y0 = pos
        for _ in range(int(n)):
            a = random.random()*math.tau
            s = speed*(0.45 + random.random()*0.55)
            vx = math.cos(a)*s*spread*0.55
            vy = math.sin(a)*s*spread*0.55 - random.random()*260
            col = random.choice(ARCADE_COLORS)
            size = random.uniform(3.0, 7.0) if kind=="confetti" else random.uniform(2.0, 5.0)
            self.particles.append((float(x0), float(y0), vx, vy, life*(0.7+random.random()*0.6), size, col, kind))

    def draw_background_overlay(self, surf:pygame.Surface):
        # dark vignette
        w,h = self.w, self.h
        ov = pygame.Surface((w,h), pygame.SRCALPHA)

        # moving diagonal stripes
        stripe_w = 42
        offset = int((self.t*80) % stripe_w)
        for x in range(-w, w*2, stripe_w):
            rx = x - offset
            pygame.draw.polygon(ov, (255,255,255,16), [(rx,0),(rx+stripe_w,0),(rx+w, h),(rx+w-stripe_w,h)])
        # dots grid
        step = 48
        t = self.t
        for yy in range(24, h, step):
            for xx in range(24, w, step):
                a = 18 + int(10*math.sin((xx*0.02 + yy*0.015 + t*1.6)))
                ov.fill((255,255,255,_clamp(a,8,28)), (xx, yy, 3, 3))

        # vignette
        pygame.draw.rect(ov, (0,0,0,0), ov.get_rect())
        # four corner fades (cheap vignette)
        for i in range(12):
            alpha = int(10 + i*8)
            pad = i*10
            pygame.draw.rect(ov, (0,0,0,alpha), pygame.Rect(pad,pad,w-pad*2,h-pad*2), width=8, border_radius=36)

        # flash on success
        if self.flash > 0:
            a = int(90*self.flash)
            ov.fill((255,255,255,a), special_flags=pygame.BLEND_RGBA_ADD)

        surf.blit(ov, (0,0))

    def draw_particles(self, surf:pygame.Surface):
        if not self.particles:
            return
        ps = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for x,y,vx,vy,life,size,col,kind in self.particles:
            a = int(_clamp(life*220, 0, 220))
            if kind == "confetti":
                r = pygame.Rect(int(x), int(y), int(size*1.8), int(size))
                pygame.draw.rect(ps, (*col, a), r, border_radius=3)
            else:
                pygame.draw.circle(ps, (*col, a), (int(x), int(y)), max(1,int(size)))
        surf.blit(ps, (0,0))

    def draw_cursor(self, surf:pygame.Surface, pid:int, pos, base_color):
        x,y = pos
        self.add_trail(pid, pos)
        cs = pygame.Surface((self.w, self.h), pygame.SRCALPHA)

        # trail
        for tx,ty,life in self.trail[pid]:
            a = int(120*life/0.22)
            r = 10 + int(10*(1-life/0.22))
            pygame.draw.circle(cs, (*base_color, a), (int(tx), int(ty)), r)

        # core glow
        pulse = self.pulse[pid]
        glow_r = 26 + int(10*pulse)
        core_r = 10 + int(4*pulse)
        pygame.draw.circle(cs, (*base_color, 80), (int(x), int(y)), glow_r)
        pygame.draw.circle(cs, (*base_color, 160), (int(x), int(y)), glow_r-8)
        pygame.draw.circle(cs, (255,255,255,220), (int(x), int(y)), core_r)
        pygame.draw.circle(cs, (*base_color, 230), (int(x), int(y)), core_r-3)

        # orbit ring
        ang = self.t*3.4 + pid*1.7
        ox = x + math.cos(ang)*18
        oy = y + math.sin(ang)*18
        pygame.draw.circle(cs, (255,255,255,170), (int(ox), int(oy)), 4)
        pygame.draw.circle(cs, (*random.choice(ARCADE_COLORS), 190), (int(ox), int(oy)), 3)

        surf.blit(cs, (0,0))

    def draw_word_banner(self, surf:pygame.Surface, word:str, typed:str, x:int, y:int, font_big:pygame.font.Font):
        if not word:
            return
        padx, pady = 18, 14
        # banner size
        text_w = 0
        letters=[]
        for i,ch in enumerate(word):
            col = (255,255,255)
            if i < len(typed):
                # correct prefix letters: accent glow
                col = (124,255,170) if word.startswith(typed[:i+1]) else (255,153,88)
            letters.append((ch,col))
        # render letters individually
        rs=[]
        for ch,col in letters:
            rsurf = font_big.render(ch, True, col)
            rs.append(rsurf)
            text_w += rsurf.get_width()
        text_h = max(r.get_height() for r in rs)

        bw = text_w + padx*2
        bh = text_h + pady*2
        banner = pygame.Surface((bw,bh), pygame.SRCALPHA)

        # colorful gradient-ish stripes
        for i in range(0, bw, 22):
            c = ARCADE_COLORS[(i//22) % len(ARCADE_COLORS)]
            banner.fill((*c, 90), (i,0,22,bh))
        pygame.draw.rect(banner, (255,255,255,210), banner.get_rect(), width=4, border_radius=22)
        pygame.draw.rect(banner, (0,0,0,80), banner.get_rect(), width=8, border_radius=22)

        # slight bounce
        bob = int(3*math.sin(self.t*5.0))
        surf.blit(banner, (x, y+bob))

        # draw letters with shadow
        cx = x + padx
        cy = y + pady + bob
        for rsurf,(ch,col) in zip(rs, letters):
            # shadow
            sh = font_big.render(ch, True, (0,0,0))
            surf.blit(sh, (cx+2, cy+3))
            surf.blit(rsurf, (cx, cy))
            cx += rsurf.get_width()
