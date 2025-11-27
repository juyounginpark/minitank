import pygame
import math
import random
import socket
import pickle
import time

WIDTH, HEIGHT = 800, 600
HOST = '3.36.32.202'
PORT = 5555

# 색상
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (100, 100, 100)
DARK_GRAY = (50, 50, 50)
BARREL_COLOR = (80, 80, 80)
OBSTACLE_COLOR = (150, 160, 170)
YELLOW = (255, 255, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 100, 255)
GOLD = (255, 215, 0)
HEAL_COLOR = (255, 0, 0)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Tank Battle - Red Heal Item")
clock = pygame.time.Clock()

try:
    FONT_MAIN = pygame.font.SysFont("malgungothic", 24)
    FONT_BIG = pygame.font.SysFont("malgungothic", 48, bold=True)
    FONT_S = pygame.font.SysFont("malgungothic", 14, bold=True)
except:
    FONT_MAIN = pygame.font.SysFont("arial", 24)
    FONT_BIG = pygame.font.SysFont("arial", 48, bold=True)
    FONT_S = pygame.font.SysFont("arial", 14, bold=True)

class Network:
    def __init__(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addr = (HOST, PORT)
        self.p_id = self.connect()

    def connect(self):
        try:
            self.client.connect(self.addr)
            return pickle.loads(self.client.recv(2048))
        except: return None

    def send(self, data):
        try:
            self.client.send(pickle.dumps(data))
            return pickle.loads(self.client.recv(8192))
        except: return None

def draw_tombstone(surface, x, y, name):
    pygame.draw.rect(surface, GRAY, (x - 15, y - 20, 30, 40))
    pygame.draw.circle(surface, GRAY, (x, y - 20), 15)
    pygame.draw.line(surface, DARK_GRAY, (x, y - 10), (x, y + 10), 3)
    pygame.draw.line(surface, DARK_GRAY, (x - 8, y - 5), (x + 8, y - 5), 3)
    txt = FONT_S.render("R.I.P", True, BLACK)
    surface.blit(txt, (x - txt.get_width()//2, y + 5))
    name_txt = FONT_S.render(name, True, BLACK)
    surface.blit(name_txt, (x - name_txt.get_width()//2, y + 25))

def draw_tank_model(surface, x, y, angle, turret_angle, color, lv, name, hp, max_hp, is_dead):
    if is_dead:
        draw_tombstone(surface, x, y, name)
        return

    lv_int = int(lv)
    base_size = 40
    scale = 1 + (lv_int * 0.1)
    size = base_size * min(scale, 3.0)
    
    body_surf = pygame.Surface((size, size), pygame.SRCALPHA)
    rw, rh = size, size * 0.75
    pygame.draw.rect(body_surf, color, (0, (size-rh)/2, rw, rh))
    
    lr = size * 0.12
    pygame.draw.circle(body_surf, YELLOW, (size - lr, (size-rh)/2 + 5), lr)
    pygame.draw.circle(body_surf, YELLOW, (size - lr, (size+rh)/2 - 5), lr)

    rotated_body = pygame.transform.rotate(body_surf, angle)
    rect = rotated_body.get_rect(center=(x, y))
    surface.blit(rotated_body, rect.topleft)

    turret_surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(turret_surf, BARREL_COLOR, (size/2, size*0.4, size*0.8, size*0.2))
    darker = (max(0, color[0]-40), max(0, color[1]-40), max(0, color[2]-40))
    pygame.draw.circle(turret_surf, darker, (size/2, size/2), size*0.25)
    
    rotated_turret = pygame.transform.rotate(turret_surf, turret_angle)
    t_rect = rotated_turret.get_rect(center=(x, y))
    surface.blit(rotated_turret, t_rect.topleft)

    info_txt = FONT_S.render(f"LV.{lv_int} {name}", True, BLACK)
    surface.blit(info_txt, (x - info_txt.get_width()//2, y + size/2 + 5))

    bar_w = 50
    bar_h = 6
    if max_hp > 0: ratio = max(0, hp / max_hp)
    else: ratio = 0
    pygame.draw.rect(surface, RED, (x - bar_w//2, y - size/2 - 15, bar_w, bar_h))
    pygame.draw.rect(surface, GREEN, (x - bar_w//2, y - size/2 - 15, bar_w * ratio, bar_h))

class Tank:
    def __init__(self, p_id, name, start_pos):
        self.id = p_id
        self.name = name
        self.x, self.y = start_pos
        self.body_angle = 90
        self.turret_angle = 90
        self.speed = 3
        
        self.lv = 1.0
        self.max_hp = 10
        self.hp = 10
        self.point = 0
        
        self.color = (random.randint(100, 200), random.randint(100, 200), random.randint(100, 200))
        self.is_dead = False
        self.bullets = []
        self.tracks = []
        self.track_timer = 0
        self.net_actions = {} 
        self.respawn_req = False

    def reset(self, start_pos):
        self.x, self.y = start_pos
        self.is_dead = False
        self.lv = 1.0
        self.point = 0
        self.max_hp = 10
        self.hp = 10
        self.bullets = []
        self.respawn_req = True

    def get_radius(self):
        scale = 1 + (int(self.lv) * 0.1)
        return (40 * min(scale, 3.0)) / 2

    def fire(self):
        if self.is_dead: return
        lv_int = int(self.lv)
        lifetime = 15 + (lv_int * 5)
        radius = 5 + (lv_int * 1.0)
        
        bullet_id = (self.id, time.time(), random.random())
        bullet_data = {'id': bullet_id, 'p_id': self.id, 'x': self.x, 'y': self.y, 'angle': self.turret_angle, 'life': lifetime, 'radius': radius, 'color': self.color}
        self.bullets.append(bullet_data)
        
        # 서버 전송을 위해 net_actions에 추가
        if 'new_bullets' not in self.net_actions:
            self.net_actions['new_bullets'] = []
        self.net_actions['new_bullets'].append(bullet_data)

    def move(self, keys, obstacles, other_players, items):
        if self.is_dead: return 

        dx = 0; dy = 0
        if keys[pygame.K_a]: self.body_angle += 3
        if keys[pygame.K_d]: self.body_angle -= 3
        if keys[pygame.K_j]: self.turret_angle += 3
        if keys[pygame.K_k]: self.turret_angle -= 3

        rad = math.radians(self.body_angle)
        if keys[pygame.K_w]: dx += math.cos(rad) * self.speed; dy -= math.sin(rad) * self.speed
        if keys[pygame.K_s]: dx -= math.cos(rad) * self.speed; dy += math.sin(rad) * self.speed
            
        self.x += dx; self.y += dy
        my_r = self.get_radius()

        for obs in obstacles:
            ox, oy = obs['x'], obs['y']
            dist = math.hypot(self.x - ox, self.y - oy)
            min_dist = my_r + obs['r']
            if dist < min_dist:
                if dist == 0: dist = 0.01
                overlap = min_dist - dist
                self.x += ((self.x - ox) / dist) * overlap
                self.y += ((self.y - oy) / dist) * overlap

        for pid, p in other_players.items():
            if pid == self.id or p['dead']: continue
            px, py = p['x'], p['y']
            other_r = (40 * min(1 + int(p['lv'])*0.1, 3.0))/2
            dist = math.hypot(self.x - px, self.y - py)
            min_dist = my_r + other_r
            if dist < min_dist:
                if dist == 0: dist = 0.01
                overlap = min_dist - dist
                self.x += ((self.x - px) / dist) * overlap * 0.5
                self.y += ((self.y - py) / dist) * overlap * 0.5

        # 아이템 획득
        for item in items:
            ix, iy = item['x'], item['y']
            dist = math.hypot(self.x - ix, self.y - iy)
            if dist < my_r + item['r']:
                self.net_actions['eat_item'] = item['id']

        self.x = max(0, min(WIDTH, self.x))
        self.y = max(0, min(HEIGHT, self.y))

        if (dx != 0 or dy != 0) and self.track_timer > 15:
            self.tracks.append([self.x, self.y, self.body_angle, 100])
            self.track_timer = 0
        else:
            self.track_timer += 1

    def update_bullets(self, obstacles, other_players):
        if self.is_dead: return
        self.net_actions = {} 
        
        for b in self.bullets[:]:
            rad = math.radians(b['angle'])
            b['x'] += math.cos(rad) * 10
            b['y'] -= math.sin(rad) * 10
            b['life'] -= 1
            
            if not (0<=b['x']<=WIDTH and 0<=b['y']<=HEIGHT) or b['life'] <= 0:
                self.bullets.remove(b)
                continue
            
            hit = False
            for obs in obstacles:
                if math.hypot(b['x']-obs['x'], b['y']-obs['y']) < b['radius'] + obs['r']:
                    self.net_actions['hit_obs'] = obs['id']
                    self.point += 1
                    if self.point % 10 == 0:
                        self.lv += 1.0
                        self.max_hp = 10 + (int(self.lv) * 5)
                        self.hp = self.max_hp 
                    hit = True; break
            
            if not hit:
                for pid, p in other_players.items():
                    if pid == self.id or p['dead']: continue
                    or_r = (40 * min(1 + int(p['lv'])*0.1, 3.0))/2
                    if math.hypot(b['x']-p['x'], b['y']-p['y']) < b['radius'] + or_r:
                        dmg = 2 + int(self.lv * 0.5)
                        self.net_actions['hit_player'] = pid
                        self.net_actions['damage'] = dmg
                        hit = True; break
            
            if hit: self.bullets.remove(b)

def get_random_spawn(obstacles):
    while True:
        x, y = random.randint(50, WIDTH-50), random.randint(50, HEIGHT-50)
        safe = True
        for obs in obstacles:
            if math.hypot(x-obs['x'], y-obs['y']) < 50 + obs['r']: safe = False; break
        if safe: return (x, y)

def start_screen():
    pygame.key.start_text_input()
    input_box = pygame.Rect(WIDTH//2 - 100, HEIGHT//2 - 25, 200, 50)
    user_text = ''; edit_text = ''; done = False
    
    while not done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return None
            if event.type == pygame.TEXTINPUT: user_text += event.text; edit_text = ''
            elif event.type == pygame.TEXTEDITING: edit_text = event.text
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if not user_text and not edit_text: user_text = "Player"
                    else: user_text += edit_text
                    done = True
                elif event.key == pygame.K_BACKSPACE:
                    if edit_text: edit_text = edit_text[:-1]
                    elif user_text: user_text = user_text[:-1]
        screen.fill((30, 30, 30))
        title = FONT_MAIN.render("TANK BATTLE", True, WHITE)
        guide = FONT_MAIN.render("이름 입력 후 Enter", True, (200, 200, 200))
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 150))
        screen.blit(guide, (WIDTH//2 - guide.get_width()//2, 230))
        txt = FONT_MAIN.render(user_text + edit_text, True, BLUE)
        input_box.w = max(200, txt.get_width()+20)
        input_box.x = WIDTH//2 - input_box.w//2
        pygame.draw.rect(screen, BLUE, input_box, 2)
        screen.blit(txt, (input_box.x+10, input_box.y+10))
        pygame.display.flip()
        clock.tick(60)
    pygame.key.stop_text_input()
    return user_text

def draw_leaderboard(surface, players, my_id):
    rank_list = sorted(players.items(), key=lambda x: x[1]['point'], reverse=True)
    count = len(rank_list)
    font_size = max(14, 24 - (count // 2)) 
    try: DYN_FONT = pygame.font.SysFont("malgungothic", font_size, bold=True)
    except: DYN_FONT = pygame.font.SysFont("arial", font_size, bold=True)

    bg_h = 30 + count * (font_size + 4)
    bg = pygame.Surface((200, bg_h), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 100))
    surface.blit(bg, (10, 10))
    surface.blit(FONT_S.render("- Ranking -", True, GOLD), (20, 15))
    
    start_y = 35
    for i, (pid, p) in enumerate(rank_list):
        color = GOLD if pid == my_id else WHITE
        if p['dead']: color = GRAY
        status = "(DEAD)" if p['dead'] else f"(Lv.{int(p['lv'])})"
        txt_surf = DYN_FONT.render(f"{i+1}. {p['name']} {status}", True, color)
        surface.blit(txt_surf, (20, start_y))
        start_y += font_size + 4

def main():
    player_name = start_screen()
    if player_name is None: return

    n = Network()
    if n.p_id is None: print("Connection Failed"); return

    init = n.send({'me': {'x':0,'y':0,'ba':0,'ta':0,'c':(0,0,0),'lv':1.0,'point':0,'max_hp':10,'name':'','is_dead':False}})
    if not init: return
    
    my_tank = Tank(n.p_id, player_name, get_random_spawn(init['obstacles']))
    explosions = []
    remote_bullets = []
    received_bullet_ids = set()

    run = True
    while run:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: run = False
            if event.type == pygame.KEYDOWN:
                if not my_tank.is_dead:
                    if event.key == pygame.K_SPACE or event.key == pygame.K_l:
                        my_tank.fire()
                else:
                    if event.key == pygame.K_r:
                        my_tank.reset(get_random_spawn(init['obstacles']))

        data = {
            'me': {
                'x': my_tank.x, 'y': my_tank.y, 
                'ba': my_tank.body_angle, 'ta': my_tank.turret_angle,
                'c': my_tank.color, 'lv': my_tank.lv, 'point': my_tank.point,
                'max_hp': my_tank.max_hp, 'name': my_tank.name,
                'is_dead': my_tank.is_dead,
                'respawn_req': my_tank.respawn_req 
            }
        }
        data.update(my_tank.net_actions)
        my_tank.respawn_req = False

        state = n.send(data)
        if not state: break

        s_players = state['players']
        obstacles = state['obstacles']
        items = state.get('items', [])
        s_exps = state['explosions']
        kill_logs = state['kill_logs']
        init['obstacles'] = obstacles

        s_bullets = state.get('bullets', [])
        for b in s_bullets:
            if b.get('p_id') != my_tank.id:
                bullet_id = b.get('id')
                if bullet_id and bullet_id not in received_bullet_ids:
                    remote_bullets.append(b)
                    received_bullet_ids.add(bullet_id)

        if my_tank.id in s_players:
            server_me = s_players[my_tank.id]
            my_tank.hp = server_me['hp']
            if server_me['lv'] > my_tank.lv:
                my_tank.lv = server_me['lv']
                my_tank.max_hp = 10 + (int(my_tank.lv) * 5)
            if server_me['dead']:
                my_tank.is_dead = True
                my_tank.hp = 0

        keys = pygame.key.get_pressed()
        my_tank.move(keys, obstacles, s_players, items)
        my_tank.update_bullets(obstacles, s_players)

        for b in remote_bullets[:]:
            rad = math.radians(b['angle'])
            b['x'] += math.cos(rad) * 10
            b['y'] -= math.sin(rad) * 10
            b['life'] -= 1
            if b['life'] <= 0:
                remote_bullets.remove(b)
                if b.get('id') in received_bullet_ids:
                    received_bullet_ids.remove(b.get('id'))

        for e in s_exps:
            color = (255,100,0)
            if e['type'] == 'hit': color = (200,200,200)
            elif e['type'] == 'heal': color = (0,255,0)
            explosions.append({'x':e['x'], 'y':e['y'], 'r':1, 'max_r':e['r'], 'a':255, 'c':color})

        # --- Draw ---
        screen.fill(WHITE)
        
        for obs in obstacles:
            ratio = obs['hp'] / obs['max_hp']
            draw_r = obs['r'] * (0.5 + 0.5 * ratio)
            col = OBSTACLE_COLOR if ratio > 0.4 else (100, 100, 100)
            pygame.draw.circle(screen, col, (obs['x'], obs['y']), int(draw_r))
            pygame.draw.circle(screen, (50,50,50), (obs['x'], obs['y']), int(draw_r), 2)
            pygame.draw.rect(screen, RED, (obs['x']-15, obs['y']+draw_r+5, 30, 4))
            pygame.draw.rect(screen, GREEN, (obs['x']-15, obs['y']+draw_r+5, 30*ratio, 4))
        
        for pid, p in s_players.items():
            if pid == n.p_id: continue
            draw_tank_model(screen, p['x'], p['y'], p['ba'], p['ta'], p['c'], p['lv'], p['name'], p['hp'], p['max_hp'], p['dead'])
        
        if my_tank.is_dead:
            draw_tombstone(screen, my_tank.x, my_tank.y, my_tank.name)
        else:
            for t in my_tank.tracks[:]:
                t[3] -= 1; 
                if t[3]<=0: my_tank.tracks.remove(t); continue
                a = int(255*(t[3]/100))
                s = pygame.Surface((10,30), pygame.SRCALPHA)
                pygame.draw.rect(s,(0,0,0,a*0.3),(0,0,3,6)); pygame.draw.rect(s,(0,0,0,a*0.3),(0,24,3,6))
                r = pygame.transform.rotate(s, t[2]).get_rect(center=(t[0],t[1]))
                screen.blit(pygame.transform.rotate(s, t[2]), r.topleft)
            
            draw_tank_model(screen, my_tank.x, my_tank.y, my_tank.body_angle, my_tank.turret_angle, 
                           my_tank.color, my_tank.lv, my_tank.name, my_tank.hp, my_tank.max_hp, False)
            
            for b in my_tank.bullets:
                pygame.draw.circle(screen, b['color'], (int(b['x']), int(b['y'])), int(b['radius']))
            
            for b in remote_bullets:
                pygame.draw.circle(screen, b['color'], (int(b['x']), int(b['y'])), int(b['radius']))

        for e in explosions[:]:
            e['r'] += 2; e['a'] -= 5
            if e['a'] <= 0: explosions.remove(e); continue
            s = pygame.Surface((e['r']*2,e['r']*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*e['c'], e['a']), (e['r'],e['r']), int(e['r']))
            screen.blit(s, (e['x']-e['r'], e['y']-e['r']))

        draw_leaderboard(screen, s_players, n.p_id)

        for i, log in enumerate(kill_logs):
            txt = FONT_MAIN.render(log['msg'], True, RED)
            screen.blit(txt, (WIDTH//2 - txt.get_width()//2, 50 + i*30))

        if my_tank.is_dead:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0,0))
            msg1 = FONT_BIG.render("GAME OVER", True, RED)
            msg2 = FONT_MAIN.render("R키를 눌러 다시 시작", True, WHITE)
            screen.blit(msg1, (WIDTH//2 - msg1.get_width()//2, HEIGHT//2 - 50))
            screen.blit(msg2, (WIDTH//2 - msg2.get_width()//2, HEIGHT//2 + 20))

        pygame.display.flip()
        clock.tick(60)
    pygame.quit()

if __name__ == "__main__":
    main()