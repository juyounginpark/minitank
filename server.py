import socket
import threading
import pickle
import random
import math
import time

HOST = '0.0.0.0'
PORT = 5555
WIDTH, HEIGHT = 800, 600

# 게임 데이터
players = {}
obstacles = []
explosion_events = [] 
kill_logs = []
obs_counter = 0
item_counter = 0
bullet_events = []

def spawn_obstacle():
    global obs_counter
    for _ in range(50):
        radius = random.randint(25, 50)
        x = random.randint(50 + radius, WIDTH - 50 - radius)
        y = random.randint(50 + radius, HEIGHT - 50 - radius)
        
        collision = False
        for obs in obstacles:
            if math.hypot(x - obs['x'], y - obs['y']) < radius + obs['r'] + 10:
                collision = True; break
        
        if not collision:
            obs_id = obs_counter
            obs_counter += 1
            hp = int(radius / 5) + 5 
            return {'id': obs_id, 'x': x, 'y': y, 'r': radius, 'hp': hp, 'max_hp': hp}
    return None

# 초기 장애물 생성
while len(obstacles) < 12:
    new_obs = spawn_obstacle()
    if new_obs: obstacles.append(new_obs)

def handle_client(conn, p_id):
    global players, obstacles, explosion_events, kill_logs
    
    conn.send(pickle.dumps(p_id))
    
    players[p_id] = {
        'x': -1000, 'y': -1000, 
        'name': 'Guest', 'hp': 10, 'max_hp': 10, 'lv': 1.0, 
        'point': 0, 'dead': False 
    }

    while True:
        try:
            recv_data = pickle.loads(conn.recv(4096))
            if not recv_data: break
            
            current_time = time.time()
            
            # 1. 상태 동기화
            if 'me' in recv_data:
                me = recv_data['me']
                
                if me.get('respawn_req', False):
                    players[p_id]['hp'] = 10
                    players[p_id]['max_hp'] = 10
                    players[p_id]['lv'] = 1.0
                    players[p_id]['point'] = 0
                    players[p_id]['dead'] = False
                
                players[p_id]['x'] = me['x']
                players[p_id]['y'] = me['y']
                players[p_id]['ba'] = me['ba']
                players[p_id]['ta'] = me['ta']
                players[p_id]['c'] = me['c']
                
                if not me.get('respawn_req', False):
                    if me['lv'] > players[p_id]['lv']:
                         players[p_id]['hp'] = me['max_hp'] # 레벨업 회복
                         players[p_id]['lv'] = me['lv']
                    players[p_id]['point'] = me['point']
                    players[p_id]['max_hp'] = me['max_hp']
                
                players[p_id]['name'] = me['name']
                if me['is_dead']: players[p_id]['dead'] = True

            # 3. 장애물 피격
            if 'hit_obs' in recv_data:
                target_id = recv_data['hit_obs']
                dmg = recv_data.get('damage', 1)
                for i, obs in enumerate(obstacles):
                    if obs['id'] == target_id:
                        obs['hp'] -= dmg
                        explosion_events.append({'x': obs['x'], 'y': obs['y'], 'r': 10, 'type': 'hit'})
                        
                        if obs['hp'] <= 0:
                            # 폭발
                            explosion_events.append({'x': obs['x'], 'y': obs['y'], 'r': obs['r'], 'type': 'obs'})
                            

                            # 폭발 데미지 (근접)
                            ox, oy = obs['x'], obs['y']
                            for pid, p in players.items():
                                if p['dead']: continue
                                dist = math.hypot(p['x'] - ox, p['y'] - oy)
                                if dist < obs['r'] + 45: 
                                    p['hp'] -= 5
                                    explosion_events.append({'x': p['x'], 'y': p['y'], 'r': 20, 'type': 'hit'})
                                    if p['hp'] <= 0:
                                        p['hp'] = 0; p['dead'] = True
                                        kill_logs.append({'msg': f"{p['name']}님이 폭발에 휘말렸습니다.", 'time': current_time + 3})
                                        explosion_events.append({'x': p['x'], 'y': p['y'], 'r': 40, 'type': 'player'})

                            obstacles.pop(i)
                            new_obs = spawn_obstacle()
                            if new_obs: obstacles.append(new_obs)
                        break
            
            # 4. 플레이어 피격
            if 'hit_player' in recv_data:
                target_pid = recv_data['hit_player']
                dmg = recv_data['damage']
                attacker_name = players[p_id]['name']
                
                if target_pid in players and not players[target_pid]['dead']:
                    players[target_pid]['hp'] -= dmg
                    explosion_events.append({'x': players[target_pid]['x'], 'y': players[target_pid]['y'], 'r': 15, 'type': 'hit'})
                    
                    if players[target_pid]['hp'] <= 0:
                        players[target_pid]['hp'] = 0; players[target_pid]['dead'] = True
                        victim_name = players[target_pid]['name']
                        reward = players[target_pid]['lv'] * 0.5
                        players[p_id]['lv'] += reward
                        
                        msg = f"{attacker_name}님이 {victim_name}님을 처치했습니다."
                        kill_logs.append({'msg': msg, 'time': current_time + 3})
                        explosion_events.append({'x': players[target_pid]['x'], 'y': players[target_pid]['y'], 'r': 40, 'type': 'player'})

            if 'new_bullets' in recv_data:
                for b in recv_data['new_bullets']:
                    b['p_id'] = p_id
                bullet_events.extend(recv_data['new_bullets'])

            # 오래된 로그 삭제
            kill_logs = [log for log in kill_logs if log['time'] > current_time]
            
            reply = {
                'players': players,
                'obstacles': obstacles,
                'explosions': explosion_events,
                'kill_logs': kill_logs,
                'bullets': bullet_events
            }
            conn.send(pickle.dumps(reply))
            if explosion_events: explosion_events.clear()
            if bullet_events: bullet_events.clear()

        except Exception as e:
            break
            
    if p_id in players: del players[p_id]
    conn.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try: server.bind((HOST, PORT))
    except: pass
    server.listen()
    print("Server Running...")
    
    cid = 0
    while True:
        conn, _ = server.accept()
        threading.Thread(target=handle_client, args=(conn, cid)).start()
        cid += 1

if __name__ == "__main__":
    main()