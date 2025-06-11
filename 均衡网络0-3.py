import pygame
import sys
import math
import random

# 颜色定义
COLORS = {
    "RED":    (255, 0, 0),
    "ORANGE": (255, 165, 0),
    "YELLOW": (255, 255, 0),
    "GREEN":  (0, 255, 0),
    "CYAN":   (0, 255, 255),
    "BLUE":   (0, 0, 255),
    "PURPLE": (128, 0, 128),
    "BLACK":  (0, 0, 0),
    "WHITE":  (255, 255, 255),
    "GRAY":   (128, 128, 128)
}

class Camp:
    def __init__(self, name, color):
        self.name = name
        self.color = color

class Path:
    def __init__(self, start_idx, end_idx, name, camp):
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.name = name
        self.camp = camp
        self.last_shot_frame = 0  # 用帧数代替时间

class Ball:
    def __init__(self, pos, camp, value=10, radius=30):
        self.pos = list(pos)
        self.camp = camp
        self.value = value
        self.radius = radius

    def draw(self, screen, font):
        pygame.draw.circle(screen, self.camp.color, self.pos, self.radius)
        text_color = COLORS["BLACK"] if self.camp.color == COLORS["YELLOW"] else COLORS["WHITE"]
        ball_text = font.render(str(self.value), True, text_color)
        ball_text_rect = ball_text.get_rect(center=self.pos)
        screen.blit(ball_text, ball_text_rect)

class Projectile:
    def __init__(self, pos, vel, end_idx, camp):
        self.pos = list(pos)
        self.vel = list(vel)
        self.end_idx = end_idx
        self.camp = camp

    def move(self):
        self.pos[0] += self.vel[0]
        self.pos[1] += self.vel[1]

class AI:
    def __init__(self, game):
        self.game = game
        self.cooldown = 1000  # 每个AI阵营操作冷却时间（毫秒）
        self.last_action_time = {}
        now = pygame.time.get_ticks()
        # 分别设置每个AI阵营的初始冷却
        self.init_cooldown = {
            "黄": 2000,   # 黄阵营初始冷却2秒
            "紫": 2000,   # 紫阵营初始冷却2秒
            "青": 2000,   # 青阵营初始冷却4秒
            # 其它阵营可继续添加
        }
        for camp in self.game.camps:
            if camp != self.game.player_camp and camp.color != self.game.camps[2].color:
                delay = self.init_cooldown.get(camp.name, 0)
                self.last_action_time[camp] = now + delay

    def update(self):
        # 动态判断AI阵营
        ai_camps = [camp for camp in self.game.camps if camp != self.game.player_camp and camp != self.game.camps[2]]
        ai_balls = [b for b in self.game.balls if b.camp in ai_camps and b.value > 0]
        player_balls = [b for b in self.game.balls if b.camp == self.game.player_camp and b.value > 0]
        gray_balls = [b for b in self.game.balls if b.camp == self.game.camps[2] and b.value > 0]

        # 如果AI阵营球已全部消失，且灰色球数量大于玩家球，则AI切换操控灰色
        use_gray = False
        if not ai_balls and len(gray_balls) > len(player_balls):
            ai_camps = [self.game.camps[2]]
            use_gray = True

        now = pygame.time.get_ticks()
        for camp in ai_camps:
            # 只在主动切换到灰色时允许AI操控灰色
            if not use_gray and (camp == self.game.player_camp or camp.color == self.game.camps[2].color):
                continue
            last_time = self.last_action_time.get(camp, 0)
            if now - last_time < self.cooldown:
                continue
            self.last_action_time[camp] = now

            my_balls = [b for b in self.game.balls if b.camp == camp and b.value > 0]
            all_balls = [b for b in self.game.balls if b.value > 0]

            # 新增：如果己方球数字大于49，立刻把多余的发送给最近的球
            # 新：如果己方球数字大于50，优先向己方低于40且≤50的球传输，否则向数字最小的非己方球进攻
            for src_ball in my_balls:
                if src_ball.value < 5:
                    continue  # 数字小于5时不进行任何操作
                if src_ball.value > 50:
                    # 1. 找己方 value < 40 的球
                    candidates = [b for b in my_balls if b is not src_ball and b.value < 40]
                    target_ball = None
                    if candidates:
                        # 选距离最近的
                        target_ball = min(candidates, key=lambda b: math.hypot(src_ball.pos[0] - b.pos[0], src_ball.pos[1] - b.pos[1]))
                    else:
                        # 2. 没有合适己方球，找数字最小的非己方球
                        enemy_balls = [b for b in all_balls if b.camp != camp and b.value > 0]
                        if enemy_balls:
                            target_ball = min(enemy_balls, key=lambda b: b.value)
                    if target_ball:
                        src_idx = self.game.balls.index(src_ball)
                        tgt_idx = self.game.balls.index(target_ball)
                        exists = any(
                            p.start_idx == src_idx and p.end_idx == tgt_idx
                            for p in self.game.paths
                        )
                        if not exists:
                            path_name = f"溢出({src_idx+1}->{tgt_idx+1})"
                            self.game.paths.append(Path(src_idx, tgt_idx, path_name, camp))

            # 新增：己方终点球大于50时切断路径
            for path in self.game.paths[:]:
                # 只处理己方路径，且终点球为己方且大于50
                if path.camp == camp:
                    end_ball = self.game.balls[path.end_idx]
                    if end_ball.camp == camp and end_ball.value > 50:
                        try:
                            self.game.paths.remove(path)
                        except Exception:
                            pass

            my_count = len(my_balls)
            total_balls = len(all_balls)
            my_total = sum(b.value for b in my_balls)
            player_total = sum(b.value for b in player_balls)

            # 模式切换
            mode = "develop"
            if my_count >= total_balls // 2:
                mode = "develop2"
            # 2. 对抗模式：己方球被玩家攻击
            under_attack = False
            attacked_ball_idx = None
            for path in self.game.paths:
                if path.camp == self.game.player_camp and self.game.balls[path.end_idx].camp == camp:
                    under_attack = True
                    attacked_ball_idx = path.end_idx
                    break
            if under_attack:
                mode = "fight"
            # 3. 游击模式：玩家总和大于己方1.5倍
            if player_total > my_total * 1.5:
                mode = "guerilla"

            # 发展模式：全力进攻距离最近的非己方球
            if mode == "develop":
                if not my_balls:
                    continue
                # 找到距离最近的非己方球
                target = None
                min_dist = float('inf')
                for b in all_balls:
                    if b.camp != camp and b.value > 0:
                        for my_ball in my_balls:
                            dist = math.hypot(my_ball.pos[0] - b.pos[0], my_ball.pos[1] - b.pos[1])
                            if dist < min_dist:
                                min_dist = dist
                                target = b
                if not target:
                    continue
                # 只派一个己方球进攻
                attacker = min(my_balls, key=lambda mb: math.hypot(mb.pos[0] - target.pos[0], mb.pos[1] - target.pos[1]))
                exists = any(
                    p.start_idx == self.game.balls.index(attacker) and p.end_idx == self.game.balls.index(target)
                    for p in self.game.paths
                )
                if not exists:
                    path_name = f"发展({self.game.balls.index(attacker)+1}->{self.game.balls.index(target)+1})"
                    self.game.paths.append(Path(self.game.balls.index(attacker), self.game.balls.index(target), path_name, camp))
                continue

            # 发展模式2：仅当场上有数字小于5的非玩家阵营小球才攻击
            if mode == "develop2":
                if not my_balls:
                    continue
                target = None
                for b in all_balls:
                    if b.camp != camp and b.camp != self.game.player_camp and b.value < 5 and b.value > 0:
                        target = b
                        break
                if not target:
                    continue
                attacker = min(my_balls, key=lambda mb: math.hypot(mb.pos[0] - target.pos[0], mb.pos[1] - target.pos[1]))
                exists = any(
                    p.start_idx == self.game.balls.index(attacker) and p.end_idx == self.game.balls.index(target)
                    for p in self.game.paths
                )
                if not exists:
                    path_name = f"发展2({self.game.balls.index(attacker)+1}->{self.game.balls.index(target)+1})"
                    self.game.paths.append(Path(self.game.balls.index(attacker), self.game.balls.index(target), path_name, camp))
                continue

            # 对抗模式
            if mode == "fight":
                if not my_balls:
                    continue
                # 被攻击球数字低于20，其他球增援
                if attacked_ball_idx is not None:
                    attacked_ball = self.game.balls[attacked_ball_idx]
                    if attacked_ball.value < 20:
                        for src in my_balls:
                            if self.game.balls.index(src) != attacked_ball_idx:
                                exists = any(
                                    p.start_idx == self.game.balls.index(src) and p.end_idx == attacked_ball_idx
                                    for p in self.game.paths
                                )
                                if not exists:
                                    path_name = f"增援({self.game.balls.index(src)+1}->{attacked_ball_idx+1})"
                                    self.game.paths.append(Path(self.game.balls.index(src), attacked_ball_idx, path_name, camp))
                                    break
                # 场上有数字小于3的非己方球，最近己方球立刻攻击
                target = None
                for b in all_balls:
                    if b.camp != camp and b.value < 3 and b.value > 0:
                        target = b
                        break
                if not target:
                    continue
                attacker = min(my_balls, key=lambda mb: math.hypot(mb.pos[0] - target.pos[0], mb.pos[1] - target.pos[1]))
                exists = any(
                    p.start_idx == self.game.balls.index(attacker) and p.end_idx == self.game.balls.index(target)
                    for p in self.game.paths
                )
                if not exists:
                    path_name = f"对抗({self.game.balls.index(attacker)+1}->{self.game.balls.index(target)+1})"
                    self.game.paths.append(Path(self.game.balls.index(attacker), self.game.balls.index(target), path_name, camp))
                continue

            # 游击模式
            if mode == "guerilla":
                if not my_balls:
                    continue
                # 场上有数字小于3的非己方球，最近己方球立刻攻击
                target = None
                for b in all_balls:
                    if b.camp != camp and b.value < 3 and b.value > 0:
                        target = b
                        break
                if not target:
                    continue
                attacker = min(my_balls, key=lambda mb: math.hypot(mb.pos[0] - target.pos[0], mb.pos[1] - target.pos[1]))
                exists = any(
                    p.start_idx == self.game.balls.index(attacker) and p.end_idx == self.game.balls.index(target)
                    for p in self.game.paths
                )
                if not exists:
                    path_name = f"游击({self.game.balls.index(attacker)+1}->{self.game.balls.index(target)+1})"
                    self.game.paths.append(Path(self.game.balls.index(attacker), self.game.balls.index(target), path_name, camp))
                # 被攻击球不再增援，被攻击球立刻分散到己方其它未被攻击的球
                attacked_balls = set()
                for path in self.game.paths:
                    if path.camp != camp and self.game.balls[path.end_idx].camp == camp:
                        attacked_balls.add(path.end_idx)
                for idx in attacked_balls:
                    src_ball = self.game.balls[idx]
                    # 分散到未被攻击的己方球
                    for dst in my_balls:
                        dst_idx = self.game.balls.index(dst)
                        if dst_idx not in attacked_balls and dst_idx != idx:
                            exists = any(
                                p.start_idx == idx and p.end_idx == dst_idx
                                for p in self.game.paths
                            )
                            if not exists:
                                path_name = f"分散({idx+1}->{dst_idx+1})"
                                self.game.paths.append(Path(idx, dst_idx, path_name, camp))
                                break
                continue

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((1200, 600))
        pygame.display.set_caption("游戏界面")
        self.font = pygame.font.Font("C:/Windows/Fonts/simhei.ttf", 24)
        self.running = True
        self.frame_count = 0
        self.clock = pygame.time.Clock()
        self.state = "login"
        self.input_active = True
        self.account = ""
        self.admin_list = ["wsc"]
        self.is_admin = False
        self.input_rect = pygame.Rect(500, 250, 200, 40)
        self.confirm_button_rect = pygame.Rect(720, 250, 80, 40)
        self.mouse_left_down = False
        self.drawing_line = False
        self.start_ball = None
        self.end_ball = None
        self.path_count = 1
        self.cooldown_frames = 50 #基础发射间隔
        self.shoot_speed_factor = 0.05  # 调整发射速度调节系数，数字越大，间隔缩短越快
        self.projectiles = []
        self.paths = []
        self.init_buttons()
        self.init_camps_and_balls()
        now_tick = pygame.time.get_ticks()
        self.last_add10_time = [now_tick] * len(self.balls)
        self.add10_prob = [0.0163] * len(self.balls)
        self.last_add10_check = [now_tick] * len(self.balls)
        self.player_camp = self.camps[0]  # 蓝色为玩家阵营
        self.ai = AI(self)  # 独立AI模块
        self.level = 0
        self.cmd_active = False
        self.cmd_text = ""
        self.ai_enabled = True
        self.grow_max = 100  # 增长上限
        self.start_balls_set = set()
    

    def handle_command(self, cmd):
        if cmd.strip().lower() == "/no ai":
            self.ai_enabled = False
            print("AI已禁用")

    def can_control_ball(self, ball):
        """判断当前玩家是否能操作该球"""
        if self.is_admin:
            return True
        return ball.camp == self.player_camp

    def draw_login(self):
        self.screen.fill(COLORS["WHITE"])
        title = self.font.render("请输入账号：", True, COLORS["BLACK"])
        self.screen.blit(title, (400, 200))
        # 输入框高亮
        box_color = COLORS["ORANGE"] if self.input_active else COLORS["GRAY"]
        pygame.draw.rect(self.screen, box_color, self.input_rect, 2)
        acc_text = self.font.render(self.account, True, COLORS["BLACK"])
        self.screen.blit(acc_text, (self.input_rect.x + 10, self.input_rect.y + 5))
        # 光标闪烁
        if self.input_active:
            cursor_x = self.input_rect.x + 10 + acc_text.get_width() + 2
            cursor_y = self.input_rect.y + 8
            if (pygame.time.get_ticks() // 500) % 2 == 0:
                pygame.draw.line(self.screen, COLORS["BLACK"], (cursor_x, cursor_y), (cursor_x, cursor_y + 24), 2)
        # 确定按钮
        pygame.draw.rect(self.screen, COLORS["RED"], self.confirm_button_rect)
        confirm_text = self.font.render("确定", True, COLORS["BLACK"])
        self.screen.blit(confirm_text, confirm_text.get_rect(center=self.confirm_button_rect.center))
        pygame.display.flip()

    def init_buttons(self):
        self.start_button_rect = pygame.Rect(550, 120, 100, 50)
        self.exit_button_rect = pygame.Rect(550, 200, 100, 50)
        self.back_button_rect = pygame.Rect(1100, 10, 80, 30)
        self.reset_button_rect = pygame.Rect(550, 280, 100, 40)

    def init_camps_and_balls(self):
        self.camps = [
            Camp("蓝", COLORS["BLUE"]),
            Camp("黄", COLORS["YELLOW"]),
            Camp("灰", COLORS["GRAY"]),
            Camp("紫", COLORS["PURPLE"]),
            Camp("青", COLORS["CYAN"]),
            Camp("绿", COLORS["GREEN"]),
            Camp("橙", COLORS["ORANGE"]),
            Camp("红", COLORS["RED"]),
            # 可在此添加更多阵营
        ]
        positions = [
            (100, 100), (200, 100), (100, 200), (200, 200),           # 蓝球
            (1100, 500), (1000, 500), (1100, 400), (1000, 400)        # 黄球
        ]
        self.balls = []
        for i, pos in enumerate(positions):
            camp = self.camps[0] if i < 4 else self.camps[1]
            self.balls.append(Ball(pos, camp))
        
        # 随机添加不少于9个灰球
        gray_camp = self.camps[2]
        for _ in range(9):
            while True:
                x = random.randint(60, 1140)
                y = random.randint(60, 540)
                # 保证新球不与已有球重叠
                if all(math.hypot(x - b.pos[0], y - b.pos[1]) > 2 * b.radius for b in self.balls):
                    break
            self.balls.append(Ball((x, y), gray_camp, value=5))  # 这里将value设为5

    def reset(self):
        for i, ball in enumerate(self.balls):
            # 前4个为蓝，5-8为黄，其余为灰
            if i < 4:
                ball.camp = self.camps[0]
                ball.value = 10
            elif i < 8:
                ball.camp = self.camps[1]
                ball.value = int(3 + self.level//5)  # AI阵营初始数字受level影响
            else:
                ball.camp = self.camps[2]
                ball.value = 5
        self.paths.clear()
        self.projectiles.clear()
        self.path_count = 1

    def run(self):
        while self.running:
            try:
                self.clock.tick(60)
                self.handle_events()
                if self.state == "login":
                    self.input_active = True
                    self.draw_login()
                elif self.state == "menu":
                    self.draw_menu()
                elif self.state == "game":
                    self.update_game_logic()
                    self.draw_game()
            except Exception as e:
                print("发生异常：", e)
                import traceback
                traceback.print_exc()
                pygame.quit()
                sys.exit()

    def handle_global_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                pygame.quit()
                sys.exit()
            yield event

    def handle_events(self):
        for event in self.handle_global_events():
            if self.state == "login":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.input_rect.collidepoint(event.pos):
                        self.input_active = True
                    else:
                        self.input_active = False
                    if self.confirm_button_rect.collidepoint(event.pos):
                        self.check_login()
                if event.type == pygame.KEYDOWN and self.input_active:
                    if event.key == pygame.K_RETURN:
                        self.check_login()
                    elif event.key == pygame.K_BACKSPACE:
                        self.account = self.account[:-1]
                    elif len(self.account) < 16 and event.unicode.isprintable():
                        self.account += event.unicode 
            elif self.state == "menu":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.start_button_rect.collidepoint(event.pos):
                        self.state = "game"
                    elif self.exit_button_rect.collidepoint(event.pos):
                        self.reset()
                    elif self.reset_button_rect.collidepoint(event.pos):
                        self.account = ""
                        self.state = "login"
                        self.input_active = True
            elif self.state == "game":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.mouse_left_down = True
                        self.handle_mouse_down(event.pos)
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.mouse_left_down = False
                        self.handle_mouse_up(event.pos)
                elif event.type == pygame.MOUSEMOTION:
                    if self.mouse_left_down:
                        self.handle_mouse_motion(event.pos)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.state = "menu"  # 按ESC返回主菜单
                    
                    elif self.is_admin:
                        if not self.cmd_active and event.unicode == "/":
                            self.cmd_active = True
                            self.cmd_text = "/"
                        elif self.cmd_active:
                            if event.key == pygame.K_RETURN:
                                self.handle_command(self.cmd_text)
                                self.cmd_active = False
                                self.cmd_text = ""
                            elif event.key == pygame.K_BACKSPACE:
                                self.cmd_text = self.cmd_text[:-1]
                            elif len(self.cmd_text) < 32 and event.unicode.isprintable():
                                self.cmd_text += event.unicode
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.state = "menu"  # 按ESC返回主菜单

    def can_control_path(self, path):
        if self.is_admin:
            return True
        return path.camp == self.player_camp

    def check_login(self):
        self.is_admin = (self.account in self.admin_list)
        self.state = "menu"

    def handle_mouse_down(self, pos):
        self.start_balls_set = set()
        self.start_ball = None
        for i, ball in enumerate(self.balls):
            if math.hypot(pos[0] - ball.pos[0], pos[1] - ball.pos[1]) <= ball.radius:
                if not self.can_control_ball(ball):
                    continue
                self.start_ball = i
                self.start_balls_set.add(i)
                self.drawing_line = True
                break


    def handle_mouse_up(self, pos):
        if self.drawing_line:
            end_ball = None
            end_idx = None
            for i, ball in enumerate(self.balls):
                if math.hypot(pos[0] - ball.pos[0], pos[1] - ball.pos[1]) <= ball.radius:
                    end_ball = ball
                    end_idx = i
                    break
            if end_ball is not None:
                for start_idx in self.start_balls_set:
                    if start_idx != end_idx:
                        exists = any(p.start_idx == start_idx and p.end_idx == end_idx for p in self.paths)
                        if not exists:
                            path_name = f"路径{self.path_count}({start_idx+1}->{end_idx+1})"
                            self.paths.append(Path(start_idx, end_idx, path_name, self.balls[start_idx].camp))
                            self.path_count += 1
            self.start_ball = None
            self.end_ball = None
            self.drawing_line = False
            self.start_balls_set = set()

    def handle_mouse_motion(self, pos):
        if self.drawing_line:
            for i, ball in enumerate(self.balls):
                if math.hypot(pos[0] - ball.pos[0], pos[1] - ball.pos[1]) <= ball.radius:
                    if not self.can_control_ball(ball):
                        continue
                    self.start_balls_set.add(i)
                    break
            return
        
        
        # ...原有路径删除逻辑...
        for path in self.paths[:]:
            start_pos = self.balls[path.start_idx].pos
            end_pos = self.balls[path.end_idx].pos
            x0, y0 = pos
            x1, y1 = start_pos
            x2, y2 = end_pos
            if x1 == x2 and y1 == y2:
                continue
            num = abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1)
            den = math.hypot(y2 - y1, x2 - x1)
            dist = num / den if den != 0 else float('inf')
            if dist < 8:
                dot1 = (x0 - x1) * (x2 - x1) + (y0 - y1) * (y2 - y1)
                dot2 = (x0 - x2) * (x1 - x2) + (y0 - y2) * (y1 - y2)
                if dot1 >= 0 and dot2 >= 0:
                    if self.can_control_path(path):
                        if path in self.paths:
                            try:
                                self.paths.remove(path)
                            except Exception:
                                pass
                    return

    def update_game_logic(self):
        if self.ai_enabled:
            self.ai.update()
        # 小球移动
        for projectile in self.projectiles[:]:
            projectile.move()
            end_pos = self.balls[projectile.end_idx].pos
            distance = math.hypot(projectile.pos[0] - end_pos[0], projectile.pos[1] - end_pos[1])
            if distance <= self.balls[projectile.end_idx].radius:
                target_ball = self.balls[projectile.end_idx]
                # 球归属变更或加减值
                if target_ball.value == 0:
                    target_ball.camp = projectile.camp
                    target_ball.value = 1
                else:
                    if projectile.camp == target_ball.camp:
                        target_ball.value += 1
                    else:
                        target_ball.value -= 1
                self.projectiles.remove(projectile)

        # 清除起点球为0的路径
        new_paths = []
        for p in self.paths:
            start_ball = self.balls[p.start_idx]
            if start_ball.value > 0 and start_ball.camp == p.camp:
                new_paths.append(p)
        self.paths = new_paths

        # 发射小球（按帧数判断）
        for path in self.paths:
            s_ball = self.balls[path.start_idx]
            e_ball = self.balls[path.end_idx]
            # 动态发射间隔，数字越大间隔越短，最小为2帧
            dynamic_cooldown = max(2, int(self.cooldown_frames / (1 + s_ball.value * self.shoot_speed_factor)))  # self.shoot_speed_factor为调节系数
            if s_ball.value > 0 and self.frame_count - path.last_shot_frame >= dynamic_cooldown:
                angle = math.atan2(e_ball.pos[1] - s_ball.pos[1], e_ball.pos[0] - s_ball.pos[0])
                ball_speed = 1  # 不变
                velocity = [math.cos(angle) * ball_speed, math.sin(angle) * ball_speed]
                self.projectiles.append(
                    Projectile(s_ball.pos[:], velocity, path.end_idx, s_ball.camp)
                )
                s_ball.value -= 1
                path.last_shot_frame = self.frame_count

        # 检查不同阵营小球相遇抵消
        self.frame_count += 1
        if  self.frame_count % 10 == 0:
            i = 0
            while i < len(self.projectiles):
                found = False
                for j in range(i + 1, len(self.projectiles)):
                    p1 = self.projectiles[i]
                    p2 = self.projectiles[j]
                    if p1.camp != p2.camp:
                        dist = math.hypot(p1.pos[0] - p2.pos[0], p1.pos[1] - p2.pos[1])
                        if dist < 10:
                            # 两两互消，只消除这一对
                            del self.projectiles[j]
                            del self.projectiles[i]
                            found = True
                            break
                if not found:
                    i += 1

        # 概率机制（全部用tick计时，单位毫秒）
        now_tick = pygame.time.get_ticks()
        if not hasattr(self, "last_ai_add_time"):
            self.last_ai_add_time = now_tick
        if now_tick - self.last_ai_add_time >= 1000:
            for i, ball in enumerate(self.balls):
                # 只对AI阵营（黄球）增长
                if ball.camp == self.camps[1] and ball.value > 0:
                    ball.value += (self.level//10)
                self.last_ai_add_time = now_tick
                if ball.value >= self.grow_max:
                    continue
                if ball.value > self.grow_max//2:
                    r = random.random()
                    if r < 0.3:
                        ball.value += 1
                    continue
                if now_tick - self.last_add10_time[i] >= 10000:
                    seconds_over = int((now_tick - self.last_add10_time[i] - 10000) / 1000)
                    self.add10_prob[i] = min(0.0063 + 0.005 * seconds_over, 1.0)
                else:
                    self.add10_prob[i] = 0.0063
                r = random.random()
                if r < 0.5:
                    ball.value += 1
                elif r < 0.5 + self.add10_prob[i]:
                    ball.value += 10
                    self.last_add10_time[i] = now_tick
                    self.add10_prob[i] = 0.0063

        alive_balls = [ball for ball in self.balls if ball.value > 0]
        if alive_balls:
            camps_left = set(ball.camp for ball in alive_balls)
            player_balls = [ball for ball in alive_balls if ball.camp == self.player_camp]
            if len(player_balls) == 0:
                self.draw_game()
                end_text = self.font.render("游戏失败", True, COLORS["RED"])
                rect = end_text.get_rect(center=(600, 300))
                self.screen.blit(end_text, rect)
                pygame.display.flip()
                pygame.time.delay(4000)
                self.state = "menu"
                self.reset()
            elif len(player_balls) == len(alive_balls):
                self.draw_game()
                # 弹窗
                popup_rect = pygame.Rect(400, 200, 400, 200)
                pygame.draw.rect(self.screen, COLORS["WHITE"], popup_rect)
                pygame.draw.rect(self.screen, COLORS["BLACK"], popup_rect, 3)
                left_rect = pygame.Rect(420, 270, 160, 80)
                right_rect = pygame.Rect(620, 270, 160, 80)
                pygame.draw.rect(self.screen, COLORS["RED"], left_rect)
                pygame.draw.rect(self.screen, COLORS["GREEN"], right_rect)
                left_text = self.font.render("返回目录", True, COLORS["BLACK"])
                right_text = self.font.render("下一关", True, COLORS["BLACK"])
                self.screen.blit(left_text, left_text.get_rect(center=left_rect.center))
                self.screen.blit(right_text, right_text.get_rect(center=right_rect.center))
                pygame.display.flip()
                # 等待点击
                waiting = True
                while waiting:
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            pygame.quit()
                            sys.exit()
                        elif event.type == pygame.MOUSEBUTTONDOWN:
                            if left_rect.collidepoint(event.pos):
                                self.state = "menu"
                                self.reset()
                                waiting = False
                                break
                            elif right_rect.collidepoint(event.pos):
                                self.level += 1
                                self.randomize_balls()
                                self.state = "game"
                                waiting = False
                                break

    def randomize_balls(self):
        radius = 30
        margin = 10  # 球之间最小间距，可调
        edge = 100   # 边缘留白
        width, height = 1200, 600
        positions = []
        # 蓝球（左半区，越靠左概率越高）
        for _ in range(4):
            while True:
                # 非均匀分布，靠左概率高
                x = int(edge + radius + (width // 2 - edge - radius) * (random.random() ** 2))
                y = random.randint(edge + radius, height - edge - radius)
                if all(math.hypot(x - px, y - py) > 2 * radius + margin for px, py in positions):
                    positions.append((x, y))
                    break
        # 黄球（右半区，越靠右概率越高）
        for _ in range(4):
            while True:
                # 非均匀分布，靠右概率高
                rx = random.random()
                x = int(width // 2 + (width // 2 - edge - radius) * (1 - rx ** 2) + edge + radius)
                y = random.randint(edge + radius, height - edge - radius)
                if all(math.hypot(x - px, y - py) > 2 * radius + margin for px, py in positions):
                    positions.append((x, y))
                    break
        # 灰球（全场均匀）
        gray_count = len(self.balls) - 8
        for _ in range(gray_count):
            while True:
                x = random.randint(edge + radius, width - edge - radius)
                y = random.randint(edge + radius, height - edge - radius)
                if all(math.hypot(x - px, y - py) > 2 * radius + margin for px, py in positions):
                    positions.append((x, y))
                    break
        # 重新分配位置和阵营
        for i, ball in enumerate(self.balls):
            ball.pos = list(positions[i])
            if i < 4:
                ball.camp = self.camps[0]
                ball.value = 10
            elif i < 8:
                ball.camp = self.camps[1]
                ball.value = int(10 + self.level)
            else:
                ball.camp = self.camps[2]
                ball.value = 5
        self.paths.clear()
        self.projectiles.clear()
        self.path_count = 1

    def draw_menu(self):
        self.screen.fill(COLORS["WHITE"])
        fps = int(self.clock.get_fps())
        fps_text = self.font.render(f"FPS: {fps}", True, COLORS["BLACK"])
        self.screen.blit(fps_text, (10, 10))
        # 顶部显示当前关卡
        level_text = self.font.render(f"第{self.level}关", True, COLORS["BLACK"])
        self.screen.blit(level_text, (570, 120))  # 居中显示

        # 按钮整体下移
        y_offset = 60  # 下移像素
        self.start_button_rect.y = 120 + y_offset
        self.exit_button_rect.y = 200 + y_offset
        self.reset_button_rect.y = 280 + y_offset

        pygame.draw.rect(self.screen, COLORS["RED"], self.start_button_rect)
        start_text = self.font.render("开始游戏", True, COLORS["BLACK"])
        self.screen.blit(start_text, start_text.get_rect(center=self.start_button_rect.center))
        pygame.draw.rect(self.screen, COLORS["RED"], self.exit_button_rect)
        exit_text = self.font.render("重置", True, COLORS["BLACK"])
        self.screen.blit(exit_text, exit_text.get_rect(center=self.exit_button_rect.center))
        pygame.draw.rect(self.screen, COLORS["RED"], self.reset_button_rect)
        relogin_text = self.font.render("重新登录", True, COLORS["BLACK"])
        self.screen.blit(relogin_text, relogin_text.get_rect(center=self.reset_button_rect.center))
        pygame.display.flip()



    def draw_game(self):
        self.screen.fill(COLORS["WHITE"])
        fps = int(self.clock.get_fps())
        fps_text = self.font.render(f"FPS: {fps}", True, COLORS["BLACK"])
        self.screen.blit(fps_text, (10, 10))
        # 右上角显示关卡
        level_text = self.font.render(f"关卡：{self.level}", True, COLORS["BLACK"])
        self.screen.blit(level_text, (1050, 10))
    
        for path in self.paths:
            start_pos = self.balls[path.start_idx].pos
            end_pos = self.balls[path.end_idx].pos
            pygame.draw.line(self.screen, path.camp.color, start_pos, end_pos, 8)
            pygame.draw.line(self.screen, COLORS["GRAY"], start_pos, end_pos, 6)
        for proj in self.projectiles:
            pygame.draw.circle(self.screen, proj.camp.color, (int(proj.pos[0]), int(proj.pos[1])), 5)
        for ball in self.balls:
            ball.draw(self.screen, self.font)
        # 多对一连线的指示线
        if self.drawing_line and self.start_balls_set:
            mouse_pos = pygame.mouse.get_pos()
            for idx in self.start_balls_set:
                pygame.draw.line(self.screen, COLORS["BLACK"], self.balls[idx].pos, mouse_pos, 2)
        if self.cmd_active:
            pygame.draw.rect(self.screen, COLORS["WHITE"], (300, 550, 600, 40))
            pygame.draw.rect(self.screen, COLORS["BLACK"], (300, 550, 600, 40), 2)
            cmd_text_render = self.font.render(self.cmd_text, True, COLORS["BLACK"])
            self.screen.blit(cmd_text_render, (310, 555))

        
        
        
        pygame.display.flip()


if __name__ == "__main__":
    Game().run()