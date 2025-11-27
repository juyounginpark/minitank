import socket
import threading
import pickle
import random
import math
import time

HOST = '0.0.0.0'
PORT = 5555
WIDTH, HEIGHT = 800, 600

# 데이터 보호를 위한 Lock
data_lock = threading.Lock()

# 게임 상태 데이터
game_state = {
    'players': {},
    'obstacles': [],
    'bullets': [],
    'explosions': [],
    'kill_logs': []
}

obs_counter = 0
BULLET_SPEED = 500  # 초당 픽셀 기본 속도

def spawn_obstacle():
    global obs_counter
    for _ in range(50):
        # 장애물 크기 다양화 (레벨 보상과 연동)
        r = random.randint(20, 50)
        x = random.randint(50 + r, WIDTH - 50 - r)
        y = random.randint(50 + r, HEIGHT - 50 - r)
        
        collision = False
        for obs in game_state['obstacles']:
            if math.hypot(x - obs['x'], y - obs['y']) < r + obs['r'] + 10:
                collision = True; break
        
        if not collision:
            obs_id = obs_counter
            obs_counter += 1
            # 체력은 크기에 비례
            hp = int(r / 3) + 5
            # 파괴 시 줄 레벨 (크기에 따라 1~3)
            # 20~29: 1Lv, 30~39: 2Lv, 40~50: 3Lv
            reward_lv = min(3, max(1, int((r - 10) / 10)))
            
            return {'id': obs_id, 'x': x, 'y': y, 'r': r, 'hp': hp, 'max_hp': hp, 'reward_lv': reward_lv}
    return None

# 초기 장애물 생성
for _ in range(15):
    o = spawn_obstacle()
    if o: game_state['obstacles'].append(o)

def update_player_stats(p):
    """레벨에 따른 스탯 재계산"""
    # 레벨이 오를수록 커짐 (최대 3배)
    # 체력: 기본 10 + 레벨당 5
    p['max_hp'] = 10 + (int(p['lv']) * 5)
    # 현재 체력이 늘어난 통보다 작으면 비율 조정이 아니라 그냥 둠(힐팩 개념이 아니므로)
    # 하지만 레벨업 순간에는 약간의 회복 보너스를 줄 수도 있음 (여기선 생략)

def game_logic_thread():
    """서버 내부 물리 연산 스레드"""
    global game_state
    prev_time = time.time()

    while True:
        now = time.time()
        dt = now - prev_time
        prev_time = now

        with data_lock:
            # 1. 총알 이동
            surviving_bullets = []
            for b in game_state['bullets']:
                rad = math.radians(b['angle'])
                b['x'] += math.cos(rad) * BULLET_SPEED * dt
                b['y'] -= math.sin(rad) * BULLET_SPEED * dt
                
                # 수명(사거리) 체크
                b['life'] -= dt
                if 0 <= b['x'] <= WIDTH and 0 <= b['y'] <= HEIGHT and b['life'] > 0:
                    surviving_bullets.append(b)
            
            game_state['bullets'] = surviving_bullets

            # 2. 충돌 처리
            bullets_to_remove = []
            
            for b in game_state['bullets']:
                hit = False
                attacker = game_state['players'].get(b['p_id'])
                
                # 장애물 충돌
                for i, obs in enumerate(game_state['obstacles']):
                    if math.hypot(b['x'] - obs['x'], b['y'] - obs['y']) < b['radius'] + obs['r']:
                        # 데미지 계산 (레벨 비례)
                        dmg = 1
                        if attacker: dmg += int(attacker['lv'] * 0.2)
                        
                        obs['hp'] -= dmg
                        game_state['explosions'].append({'x': b['x'], 'y': b['y'], 'r': 10, 'type': 'hit', 'time': now})
                        hit = True
                        
                        if obs['hp'] <= 0:
                            # 장애물 파괴 이벤트
                            game_state['explosions'].append({'x': obs['x'], 'y': obs['y'], 'r': obs['r'], 'type': 'obs', 'time': now})
                            
                            # 보상: 장애물 크기만큼 LV 추가 (최대 3)
                            if attacker:
                                gain = obs['reward_lv']
                                attacker['lv'] += gain
                                update_player_stats(attacker)
                                attacker['hp'] = min(attacker['hp'] + 5, attacker['max_hp']) # 소량 회복

                            game_state['obstacles'].pop(i)
                            new_obs = spawn_obstacle()
                            if new_obs: game_state['obstacles'].append(new_obs)
                        break
                
                if hit:
                    bullets_to_remove.append(b)
                    continue

                # 플레이어 충돌
                for pid, p in game_state['players'].items():
                    if p['dead'] or pid == b['p_id']: continue
                    
                    # 피격 판정 범위 (레벨 비례 크기 고려)
                    scale = 1 + (p['lv'] * 0.1)
                    p_radius = (40 * min(scale, 3.0)) / 2
                    
                    if math.hypot(b['x'] - p['x'], b['y'] - p['y']) < b['radius'] + p_radius:
                        # 데미지 계산
                        dmg = 2
                        if attacker: dmg += int(attacker['lv'] * 0.5)
                        
                        p['hp'] -= dmg
                        game_state['explosions'].append({'x': b['x'], 'y': b['y'], 'r': 15, 'type': 'hit', 'time': now})
                        hit = True
                        
                        if p['hp'] <= 0:
                            p['hp'] = 0; p['dead'] = True
                            game_state['explosions'].append({'x': p['x'], 'y': p['y'], 'r': 50, 'type': 'player', 'time': now})
                            
                            # 킬 로그 및 보상
                            if attacker:
                                # 적 LV의 50%를 정수로 가져옴
                                xp_gain = int(p['lv'] * 0.5)
                                if xp_gain < 1: xp_gain = 1 # 최소 1은 보장
                                attacker['lv'] += xp_gain
                                update_player_stats(attacker)
                                # 처치 시 체력 대폭 회복
                                attacker['hp'] = min(attacker['hp'] + attacker['max_hp']*0.3, attacker['max_hp'])
                                
                                log_msg = f"{attacker['name']}(Lv.{int(attacker['lv'])}) 처치 -> {p['name']}(Lv.{int(p['lv'])})"
                                game_state['kill_logs'].append({'msg': log_msg, 'time': now + 4})
                            else:
                                game_state['kill_logs'].append({'msg': f"{p['name']} 사망", 'time': now + 4})
                        break
                
                if hit: bullets_to_remove.append(b)

            for b in bullets_to_remove:
                if b in game_state['bullets']:
                    game_state['bullets'].remove(b)

            # 정리
            game_state['explosions'] = [e for e in game_state['explosions'] if now - e['time'] < 0.5]
            game_state['kill_logs'] = [k for k in game_state['kill_logs'] if k['time'] > now]

        time.sleep(0.016)

def handle_client(conn, p_id):
    conn.send(pickle.dumps(p_id))
    
    with data_lock:
        # 초기화
        game_state['players'][p_id] = {
            'x': -1000, 'y': -1000, 'name': 'Player', 
            'hp': 10, 'max_hp': 10, 'lv': 1.0, 
            'dead': False, 'ba': 0, 'ta': 0, 'c': (100,100,100)
        }

    while True:
        try:
            header = conn.recv(4)
            if not header: break
            size = int.from_bytes(header, 'big')
            
            recv_bytes = b''
            while len(recv_bytes) < size:
                chunk = conn.recv(min(4096, size - len(recv_bytes)))
                if not chunk: break
                recv_bytes += chunk
            
            if len(recv_bytes) < size: break
            client_data = pickle.loads(recv_bytes)

            with data_lock:
                if 'me' in client_data:
                    me = client_data['me']
                    if p_id in game_state['players']:
                        p = game_state['players'][p_id]
                        
                        # 리스폰 처리
                        if me.get('respawn_req'):
                            p['hp'] = 10; p['max_hp'] = 10; p['lv'] = 1.0; p['dead'] = False
                            p['x'] = random.randint(100, WIDTH-100)
                            p['y'] = random.randint(100, HEIGHT-100)
                        
                        if not p['dead']:
                            p['x'] = me['x']
                            p['y'] = me['y']
                            p['ba'] = me['ba']
                            p['ta'] = me['ta']
                            # 닉네임과 색상은 클라이언트가 보낸 것으로 계속 업데이트 (또는 최초 1회만 해도 됨)
                            p['name'] = me['name']
                            p['c'] = me['c']

                if 'new_bullets' in client_data and p_id in game_state['players']:
                    shooter = game_state['players'][p_id]
                    if not shooter['dead']:
                        for b in client_data['new_bullets']:
                            b['p_id'] = p_id
                            # 사거리(수명) 계산: 기본 1.5초 + 레벨당 0.1초 증가
                            b['life'] = 1.5 + (shooter['lv'] * 0.1)
                            # 총알 크기 계산: 기본 + 레벨
                            b['radius'] = 4 + (shooter['lv'] * 0.5)
                            game_state['bullets'].append(b)

                # 클라이언트에게 보낼 데이터 (전체 상태)
                reply_data = {
                    'players': game_state['players'],
                    'obstacles': game_state['obstacles'],
                    'bullets': game_state['bullets'],
                    'explosions': game_state['explosions'],
                    'kill_logs': game_state['kill_logs']
                }

            serialized = pickle.dumps(reply_data)
            conn.send(len(serialized).to_bytes(4, 'big') + serialized)

        except Exception as e:
            print(f"Client {p_id} Error: {e}")
            break

    with data_lock:
        if p_id in game_state['players']:
            del game_state['players'][p_id]
    conn.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((HOST, PORT))
    except Exception as e:
        print(f"Bind Error: {e}")
        return
    server.listen()
    print("RPG Tank Server Running...")
    
    threading.Thread(target=game_logic_thread, daemon=True).start()

    cid = 0
    while True:
        conn, addr = server.accept()
        print(f"Joined: {addr}")
        threading.Thread(target=handle_client, args=(conn, cid), daemon=True).start()
        cid += 1

if __name__ == "__main__":
    main()