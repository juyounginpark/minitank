import pygame
import math
import random
import socket
import pickle

WIDTH, HEIGHT = 800, 600
HOST = '52.79.106.125' # 실제 서버 IP로 변경 필요
PORT = 5555

# 색상
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (100, 100, 100)
RED = (255, 60, 60)
GREEN = (60, 255, 60)
GOLD = (255, 215, 0)
TRANS_BLACK = (0, 0, 0, 150)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("MINI TANKS")
clock = pygame.time.Clock()

# 한글 폰트 설정
try:
    # 윈도우 기본 한글 폰트
    FONT_MAIN = pygame.font.SysFont("malgungothic", 20, bold=True)
    FONT_BIG = pygame.font.SysFont("malgungothic", 40, bold=True)
    FONT_S = pygame.font.SysFont("malgungothic", 12, bold=True)
    FONT_NAME = pygame.font.SysFont("malgungothic", 14, bold=True)
except:
    # 폰트 없을 시 기본값
    FONT_MAIN = pygame.font.SysFont("arial", 20, bold=True)
    FONT_BIG = pygame.font.SysFont("arial", 40, bold=True)
    FONT_S = pygame.font.SysFont("arial", 12, bold=True)
    FONT_NAME = pygame.font.SysFont("arial", 14, bold=True)

class Network:
    def __init__(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.p_id = None
        self.connected = False

    def connect(self):
        try:
            self.client.connect((HOST, PORT))
            self.p_id = pickle.loads(self.client.recv(2048))
            self.connected = True
            return True
        except: 
            return False

    def send(self, data):
        try:
            pickled = pickle.dumps(data)
            self.client.send(len(pickled).to_bytes(4, 'big') + pickled)
            
            header = self.client.recv(4)
            if not header: return None
            size = int.from_bytes(header, 'big')
            
            recv_data = b''
            while len(recv_data) < size:
                chunk = self.client.recv(min(4096, size - len(recv_data)))
                if not chunk: return None
                recv_data += chunk
            return pickle.loads(recv_data)
        except: return None

# 닉네임 입력 화면
def input_nickname():
    user_text = ""
    composition_text = ""
    input_active = True
    
    pygame.key.set_repeat(500, 50)
    try:
        pygame.key.start_text_input()
    except: pass

    while input_active:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            
            elif event.type == pygame.TEXTINPUT:
                if len(user_text) + len(event.text) <= 8:
                    user_text += event.text
                composition_text = ""
            
            elif event.type == pygame.TEXTEDITING:
                composition_text = event.text

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    final_name = user_text + composition_text
                    if len(final_name) > 0:
                        try: pygame.key.stop_text_input()
                        except: pass
                        return final_name
                elif event.key == pygame.K_BACKSPACE:
                    if len(user_text) > 0 and not composition_text:
                        user_text = user_text[:-1]

        screen.fill((30, 30, 30))
        title = FONT_BIG.render("MINI TANKS", True, GOLD)
        guide = FONT_MAIN.render("닉네임을 입력하세요 (Enter)", True, WHITE)
        
        input_box = pygame.Rect(WIDTH//2 - 100, HEIGHT//2, 200, 40)
        pygame.draw.rect(screen, WHITE, input_box, 2)
        
        display_text = user_text + composition_text
        name_surf = FONT_MAIN.render(display_text, True, GOLD)
        screen.blit(name_surf, (input_box.x + 10, input_box.y + 8))
        
        if pygame.time.get_ticks() % 1000 < 500:
            cursor_x = input_box.x + 10 + name_surf.get_width()
            pygame.draw.line(screen, GOLD, (cursor_x, input_box.y + 8), (cursor_x, input_box.y + 32), 2)
        
        screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//2 - 100))
        screen.blit(guide, (WIDTH//2 - guide.get_width()//2, HEIGHT//2 - 50))
        
        pygame.display.flip()
        clock.tick(60)
    return user_text

# [추가] 안전한 스폰 위치 계산 (겹침 방지)
def get_safe_spawn(obstacles, players, my_id):
    # 최대 100번 시도하여 안전한 위치 탐색
    for _ in range(100):
        x = random.randint(50, WIDTH - 50)
        y = random.randint(50, HEIGHT - 50)
        safe = True
        
        # 1. 장애물과 겹치는지 확인
        for obs in obstacles:
            # 장애물 반지름 + 탱크 안전거리(약 30) + 여유분
            if math.hypot(x - obs['x'], y - obs['y']) < obs['r'] + 40:
                safe = False; break
        
        if not safe: continue

        # 2. 다른 플레이어와 겹치는지 확인
        for pid, p in players.items():
            if pid == my_id or p['dead']: continue
            # 상대 탱크 반지름 고려 (넉넉하게 60 거리 유지)
            if math.hypot(x - p['x'], y - p['y']) < 60:
                safe = False; break
        
        if safe: return x, y
        
    # 자리가 정 없으면 그냥 랜덤 반환
    return random.randint(50, WIDTH - 50), random.randint(50, HEIGHT - 50)

def draw_tombstone(surf, x, y, name):
    pygame.draw.circle(surf, GRAY, (x, y-10), 15)
    pygame.draw.rect(surf, GRAY, (x-15, y-10, 30, 30))
    pygame.draw.line(surf, BLACK, (x, y-5), (x, y+10), 2)
    pygame.draw.line(surf, BLACK, (x-5, y), (x+5, y), 2)
    
    txt = FONT_S.render("R.I.P", True, BLACK)
    surf.blit(txt, (x-txt.get_width()//2, y+25))
    
    name_txt = FONT_S.render(name, True, WHITE)
    surf.blit(name_txt, (x-name_txt.get_width()//2, y-35))

def draw_leaderboard(surf, players):
    sorted_p = sorted(players.items(), key=lambda item: item[1]['lv'], reverse=True)
    
    count = len(sorted_p)
    font_size = max(15, 22 - (count // 2))
    
    try:
        RANK_FONT = pygame.font.SysFont("malgungothic", font_size, bold=True)
    except:
        RANK_FONT = pygame.font.SysFont("arial", font_size, bold=True)
        
    box_w = 180
    box_h = 40 + (count * (font_size + 5))
    
    bg = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    bg.fill(TRANS_BLACK)
    surf.blit(bg, (10, 10))
    
    header = FONT_MAIN.render("현재 랭킹", True, GOLD)
    surf.blit(header, (20, 15))
    
    y = 45
    for i, (pid, p) in enumerate(sorted_p):
        state = "💀" if p['dead'] else f"Lv.{int(p['lv'])}"
        text = f"{i+1}. {p['name']} ({state})"
        
        color = WHITE
        if i == 0: color = GOLD
        elif i == 1: color = (192, 192, 192)
        elif i == 2: color = (205, 127, 50)
        
        row = RANK_FONT.render(text, True, color)
        surf.blit(row, (20, y))
        y += font_size + 5

def draw_tank(surf, x, y, ba, ta, color, lv, name, hp, max_hp, is_dead):
    if is_dead:
        draw_tombstone(surf, x, y, name)
        return

    scale = 1 + (lv * 0.1)
    base_size = 40
    size = base_size * min(scale, 3.0)
    
    shadow = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(shadow, (0,0,0,50), (size/2, size/2), size/2)
    surf.blit(shadow, (x - size/2 + 5, y - size/2 + 5))

    body = pygame.Surface((size, size*0.85), pygame.SRCALPHA)
    pygame.draw.rect(body, color, (0, 0, size, size*0.85), border_radius=int(5*scale))
    
    pygame.draw.rect(body, (30,30,30), (0, 0, size, size*0.2))
    pygame.draw.rect(body, (30,30,30), (0, size*0.65, size, size*0.2))

    r_body = pygame.transform.rotate(body, ba)
    surf.blit(r_body, r_body.get_rect(center=(x, y)).topleft)

    turret = pygame.Surface((size, size), pygame.SRCALPHA)
    barrel_w = size * 0.6
    barrel_h = size * 0.25
    pygame.draw.rect(turret, (80, 80, 80), (size/2, size/2 - barrel_h/2, barrel_w, barrel_h))
    pygame.draw.circle(turret, (max(0, color[0]-40), max(0, color[1]-40), max(0, color[2]-40)), (size/2, size/2), size*0.35)
    
    r_turret = pygame.transform.rotate(turret, ta)
    surf.blit(r_turret, r_turret.get_rect(center=(x, y)).topleft)

    name_surf = FONT_NAME.render(f"Lv.{int(lv)} {name}", True, BLACK)
    for dx, dy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
        outline = FONT_NAME.render(f"Lv.{int(lv)} {name}", True, WHITE)
        surf.blit(outline, (x - name_surf.get_width()//2 + dx, y + size/2 + 5 + dy))
    surf.blit(name_surf, (x - name_surf.get_width()//2, y + size/2 + 5))
    
    if max_hp > 0:
        ratio = max(0, hp / max_hp)
        bar_w = size * 1.2
        bar_h = 6 * min(scale, 2.0)
        bar_x = x - bar_w // 2
        bar_y = y - size/2 - 15
        
        pygame.draw.rect(surf, (50,0,0), (bar_x, bar_y, bar_w, bar_h))
        pygame.draw.rect(surf, GREEN if ratio > 0.5 else RED, (bar_x, bar_y, bar_w * ratio, bar_h))

class Player:
    def __init__(self, pid, name):
        self.pid = pid
        self.name = name
        # [수정] 초기 위치를 화면 밖으로 설정하여 아직 스폰되지 않음을 표시
        self.x, self.y = -1000, -1000 
        self.ba = 0
        self.ta = 0
        self.color = (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200))
        self.respawn_req = False
        self.is_dead = False
        self.bullets_q = []
        self.speed = 4
        self.lv = 1.0
        self.has_spawned = False # 스폰 여부 플래그

    def move(self, keys, obstacles, other_players):
        # [수정] 스폰되지 않았거나 죽었으면 이동 불가
        if self.is_dead or not self.has_spawned: return
        
        dx, dy = 0, 0
        rad = math.radians(self.ba)
        if keys[pygame.K_w]: dx += math.cos(rad) * self.speed; dy -= math.sin(rad) * self.speed
        if keys[pygame.K_s]: dx -= math.cos(rad) * self.speed; dy += math.sin(rad) * self.speed
        if keys[pygame.K_a]: self.ba += 4
        if keys[pygame.K_d]: self.ba -= 4
        if keys[pygame.K_j]: self.ta += 4
        if keys[pygame.K_k]: self.ta -= 4
        
        # 이동 적용
        self.x += dx
        self.y += dy

        # 맵 경계 제한
        self.x = max(0, min(WIDTH, self.x))
        self.y = max(0, min(HEIGHT, self.y))

        # --- 충돌 처리 (밀어내기) ---
        scale = 1 + (self.lv * 0.1)
        my_radius = (40 * min(scale, 3.0)) / 2

        # 1. 장애물과 충돌
        for obs in obstacles:
            ox, oy, or_ = obs['x'], obs['y'], obs['r']
            dist = math.hypot(self.x - ox, self.y - oy)
            min_dist = my_radius + or_
            
            if dist < min_dist:
                if dist == 0: dist = 0.1
                overlap = min_dist - dist
                push_ratio = overlap / dist
                self.x += (self.x - ox) * push_ratio
                self.y += (self.y - oy) * push_ratio

        # 2. 다른 플레이어와 충돌
        for pid, p in other_players.items():
            if pid == self.pid or p['dead']: continue
            
            px, py = p['x'], p['y']
            p_scale = 1 + (p['lv'] * 0.1)
            p_radius = (40 * min(p_scale, 3.0)) / 2
            
            dist = math.hypot(self.x - px, self.y - py)
            min_dist = my_radius + p_radius
            
            if dist < min_dist:
                if dist == 0: dist = 0.1
                overlap = min_dist - dist
                push_ratio = overlap / dist
                self.x += (self.x - px) * push_ratio * 0.5
                self.y += (self.y - py) * push_ratio * 0.5
        
        self.x = max(0, min(WIDTH, self.x))
        self.y = max(0, min(HEIGHT, self.y))

    def shoot(self):
        if not self.is_dead and self.has_spawned:
            self.bullets_q.append({'x': self.x, 'y': self.y, 'angle': self.ta, 'color': self.color})

def main():
    nickname = input_nickname()
    if not nickname: return

    n = Network()
    if not n.connect():
        print("서버 연결 실패")
        return

    me = Player(n.p_id, nickname)
    
    last_obstacles = []
    last_players = {}

    run = True
    while run:
        clock.tick(60)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT: run = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE: me.shoot()
                if event.key == pygame.K_r and me.is_dead: 
                    me.respawn_req = True

        keys = pygame.key.get_pressed()
        me.move(keys, last_obstacles, last_players)

        send_data = {
            'me': {
                'x': int(me.x), 'y': int(me.y), 'ba': int(me.ba), 'ta': int(me.ta),
                'name': me.name, 'c': me.color, 'respawn_req': me.respawn_req
            },
            'new_bullets': me.bullets_q[:]
        }
        me.bullets_q.clear()
        me.respawn_req = False

        state = n.send(send_data)
        if not state: break

        last_obstacles = state['obstacles']
        last_players = state['players']

        if n.p_id in state['players']:
            my_state = state['players'][n.p_id]
            
            # [수정] 1. 최초 접속 시 안전한 위치 스폰
            if not me.has_spawned:
                me.x, me.y = get_safe_spawn(state['obstacles'], state['players'], n.p_id)
                me.has_spawned = True

            # [수정] 2. 부활 시 안전한 위치로 재조정 (서버 랜덤 위치 덮어쓰기)
            # 내가 죽어있었는데 서버 데이터는 살아있다면(방금 부활함)
            if me.is_dead and not my_state['dead']:
                me.x, me.y = get_safe_spawn(state['obstacles'], state['players'], n.p_id)
            
            me.is_dead = my_state['dead']
            me.lv = my_state['lv']

        screen.fill((240, 240, 245))

        # 1. 장애물
        for obs in state['obstacles']:
            ratio = obs['hp'] / obs['max_hp']
            shade = 150 - (obs['r'] - 20) * 2
            col = (shade, shade, shade)
            
            pygame.draw.circle(screen, col, (obs['x'], obs['y']), obs['r'])
            pygame.draw.circle(screen, BLACK, (obs['x'], obs['y']), obs['r'], 2)
            
            if ratio < 1.0:
                pygame.draw.rect(screen, RED, (obs['x']-15, obs['y']+obs['r']+5, 30, 4))
                pygame.draw.rect(screen, GREEN, (obs['x']-15, obs['y']+obs['r']+5, 30*ratio, 4))

        # 2. 플레이어
        for pid, p in state['players'].items():
            draw_tank(screen, p['x'], p['y'], p['ba'], p['ta'], p['c'], 
                      p['lv'], p['name'], p['hp'], p['max_hp'], p['dead'])

        # 3. 총알
        for b in state['bullets']:
            pygame.draw.circle(screen, b.get('color', BLACK), (int(b['x']), int(b['y'])), int(b.get('radius', 5)))

        # 4. 이펙트
        for e in state['explosions']:
            if e['type'] == 'hit':
                pygame.draw.circle(screen, (255, 100, 0), (int(e['x']), int(e['y'])), e['r'], 2)
            else:
                s = pygame.Surface((e['r']*2, e['r']*2), pygame.SRCALPHA)
                alpha = max(0, 255 - int((pygame.time.get_ticks()/1000 - e['time']) * 500))
                pygame.draw.circle(s, (255, 50, 0, 150), (e['r'], e['r']), e['r'])
                screen.blit(s, (e['x']-e['r'], e['y']-e['r']))

        # 5. UI 오버레이
        draw_leaderboard(screen, state['players'])
        
        log_y = 10
        for log in state['kill_logs']:
            txt = FONT_MAIN.render(log['msg'], True, RED)
            screen.blit(txt, (WIDTH/2 - txt.get_width()/2, log_y))
            log_y += 30

        if me.is_dead:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))
            
            msg1 = FONT_BIG.render("GAME OVER", True, RED)
            msg2 = FONT_MAIN.render("Press 'R' to Respawn", True, WHITE)
            screen.blit(msg1, (WIDTH//2 - msg1.get_width()//2, HEIGHT//2 - 40))
            screen.blit(msg2, (WIDTH//2 - msg2.get_width()//2, HEIGHT//2 + 20))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()