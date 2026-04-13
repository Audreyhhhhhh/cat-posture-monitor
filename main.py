import cv2
import mediapipe as mp
import math
import time
import json
import os
import datetime
import threading
import subprocess
import urllib.request
import ssl
from http.server import HTTPServer, BaseHTTPRequestHandler

# ===================== 【公开版】配置区 =====================
CHECK_INTERVAL = 300  # 5分钟
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/你的飞书机器人Webhook"
DATA_FILE = "posture_data.json"
# =============================================================

# 忽略SSL证书问题
ssl._create_default_https_context = ssl._create_unverified_context

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

# 加载历史数据
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        all_data = json.load(f)
else:
    all_data = {}

today = datetime.date.today().isoformat()
if today not in all_data:
    all_data[today] = {
        "total_checks": 0,
        "head_forward": 0,
        "hunchback": 0,
        "cross_legs": 0,
        "date": today
    }

# ------------------- 角度计算工具 -------------------
def calculate_angle(a, b, c):
    radians = math.atan2(c.y - b.y, c.x - b.x) - math.atan2(a.y - b.y, a.x - b.x)
    angle = abs(math.degrees(radians))
    return angle

# ------------------- 【精准版】姿态识别 -------------------
def is_head_forward(landmarks, w):
    ear = landmarks[mp_pose.PoseLandmark.LEFT_EAR]
    shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
    offset = (ear.x - shoulder.x) * w
    return offset > 40

def is_hunchback(landmarks):
    ear = landmarks[mp_pose.PoseLandmark.LEFT_EAR]
    shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
    hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP]
    angle = calculate_angle(ear, shoulder, hip)
    return angle < 155

def is_cross_legs(landmarks):
    l_knee = landmarks[mp_pose.PoseLandmark.LEFT_KNEE]
    r_knee = landmarks[mp_pose.PoseLandmark.RIGHT_KNEE]
    l_ankle = landmarks[mp_pose.PoseLandmark.LEFT_ANKLE]
    r_ankle = landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE]
    knee_dist = abs(l_knee.x - r_knee.x)
    ankle_dist = abs(l_ankle.x - r_ankle.x)
    return knee_dist < 0.22 and ankle_dist > 0.28

# ------------------- 语音提醒 -------------------
def speak(text):
    subprocess.run(["say", text])

def warning_voice():
    speak("警告！坐姿不正确，请坐直！")

# ------------------- 飞书推送 -------------------
def send_feishu(msg):
    try:
        payload = {
            "msg_type": "text",
            "content": {
                "text": msg
            }
        }
        req = urllib.request.Request(
            FEISHU_WEBHOOK,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req)
        print("✅ 飞书推送成功")
    except Exception as e:
        print("❌ 飞书推送失败，请检查Webhook")

# ------------------- 数据保存 -------------------
def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

# ------------------- 🐱 猫咪主题网页 -------------------
class WebHandler(BaseHTTPRequestHandler):
    def send_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        self.send_headers()
        target_date = today
        if "?date=" in self.path:
            target_date = self.path.split("?date=")[1]

        data = all_data.get(target_date, all_data[today])
        days = sorted(all_data.keys(), reverse=True)

        html = f'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🐱 猫咪坐姿守护助手</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif}}
body{{background:#fdf6f0;color:#555;min-height:100vh;padding:30px 20px;display:flex;justify-content:center}}
.container{{max-width:780px;width:100%}}
.header{{text-align:center;margin-bottom:30px}}
.header h1{{font-size:28px;color:#e0a96d;margin-bottom:8px}}
.header p{{color:#999}}
.date{{text-align:center;margin-bottom:24px}}
select{{padding:10px 16px;border-radius:20px;border:none;background:#fff;outline:none;box-shadow:0 2px 8px rgba(0,0,0,0.05)}}
.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-bottom:30px}}
.card{{background:#fff;border-radius:20px;padding:24px;text-align:center;box-shadow:0 8px 20px rgba(0,0,0,0.05)}}
.card .icon{{font-size:24px;margin-bottom:8px}}
.card .label{{color:#888;font-size:14px;margin-bottom:6px}}
.card .num{{font-size:28px;font-weight:bold;color:#e0a96d}}
.intro{{background:#fff;border-radius:20px;padding:26px;line-height:1.7;box-shadow:0 8px 20px rgba(0,0,0,0.05)}}
.intro h3{{color:#e0a96d;margin-bottom:14px}}
.intro p{{color:#777;margin-bottom:10px}}
.tags{{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}}
.tags span{{background:#f9e9d7;color:#d4985a;padding:4px 12px;border-radius:12px;font-size:13px}}
.footer{{text-align:center;margin-top:40px;color:#ccc}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>🐱 猫咪坐姿守护助手</h1>
<p>AI 姿态识别 · 实时监测坐姿 · 猫咪监督更健康</p>
</div>

<div class="date">
<form method="get">
<select name="date" onchange="this.form.submit()">
{''.join([f'<option value="{d}" {"selected" if d==target_date else ""}>{d}</option>' for d in days])}
</select>
</form>
</div>

<div class="grid">
<div class="card"><div class="icon">📅</div><div class="label">检测次数</div><div class="num">{data['total_checks']}</div></div>
<div class="card"><div class="icon">🙀</div><div class="label">头前伸</div><div class="num">{data['head_forward']}</div></div>
<div class="card"><div class="icon">😿</div><div class="label">驼背</div><div class="num">{data['hunchback']}</div></div>
<div class="card"><div class="icon">🐾</div><div class="label">二郎腿</div><div class="num">{data['cross_legs']}</div></div>
</div>

<div class="intro">
<h3>📌 项目介绍</h3>
<p>基于 MediaPipe 姿态关键点检测 AI，实时识别驼背、头前伸、二郎腿等不良姿势。</p>
<p>支持定时检测、语音提醒、飞书消息推送、数据统计与历史记录。</p>
<p>猫咪主题界面，简单治愈，帮助你养成健康坐姿。</p>
<div class="tags">
<span>AI姿态识别</span>
<span>坐姿监测</span>
<span>Python</span>
<span>OpenCV</span>
<span>MediaPipe</span>
<span>飞书推送</span>
</div>
</div>

<div class="footer">🐾 Made with Vibe Coding & AI</div>
</div>
</body>
</html>
        '''
        self.wfile.write(html.encode())

def start_web():
    try:
        server = HTTPServer(("0.0.0.0", 8765), WebHandler)
        server.serve_forever()
    except:
        pass

# ------------------- 主程序 -------------------
def main():
    threading.Thread(target=start_web, daemon=True).start()
    print("🌐 网页端: http://localhost:8765")
    print("🎤 语音提醒已启动")
    print("✅ AI坐姿识别已运行")

    cap = cv2.VideoCapture(0)
    last_check = time.time()

    with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = pose.process(rgb)

            if res.pose_landmarks:
                lm = res.pose_landmarks.landmark
                current = all_data[today]
                bad = False
                msg = "⚠️坐姿警告："

                if time.time() - last_check > CHECK_INTERVAL:
                    current["total_checks"] += 1

                    if is_head_forward(lm, w):
                        current["head_forward"] += 1
                        msg += "头前伸 "
                        bad = True
                    if is_hunchback(lm):
                        current["hunchback"] += 1
                        msg += "驼背 "
                        bad = True
                    if is_cross_legs(lm):
                        current["cross_legs"] += 1
                        msg += "二郎腿 "
                        bad = True

                    if bad:
                        print(msg)
                        warning_voice()
                        send_feishu(msg)
                        save_data()

                    last_check = time.time()

                # 实时提示
                if is_head_forward(lm, w):
                    cv2.putText(frame, "HEAD FORWARD", (50,50), 0, 1, (0,0,255), 2)
                if is_hunchback(lm):
                    cv2.putText(frame, "HUNCHBACK", (50,100), 0, 1, (0,0,255), 2)
                if is_cross_legs(lm):
                    cv2.putText(frame, "CROSS LEGS", (50,150), 0, 1, (0,0,255), 2)

                mp_drawing.draw_landmarks(frame, res.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            cv2.imshow("AI 猫咪坐姿监测", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()