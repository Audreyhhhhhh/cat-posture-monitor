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

# 修复SSL
ssl._create_default_https_context = ssl._create_unverified_context

# ===================== 配置区 =====================
CHECK_INTERVAL = 10  # 5分钟
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/8b8ecff3-df3f-495e-8220-06d8e3b3eb5f"
DATA_FILE = "posture_data.json"
# ==================================================

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

# 加载数据
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

# ------------------- 工具函数 -------------------
def calculate_angle(a, b, c):
    ang = math.degrees(math.atan2(c.y - b.y, c.x - b.x) - math.atan2(a.y - b.y, a.x - b.x))
    return abs(ang)

def is_head_forward(landmarks, w):
    ear = landmarks[mp_pose.PoseLandmark.LEFT_EAR]
    shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
    return (ear.x - shoulder.x) * w > 50

def is_hunchback(landmarks):
    ear = landmarks[mp_pose.PoseLandmark.LEFT_EAR]
    shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
    hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP]
    return calculate_angle(ear, shoulder, hip) < 150

def is_cross_legs(landmarks):
    lk = landmarks[mp_pose.PoseLandmark.LEFT_KNEE]
    rk = landmarks[mp_pose.PoseLandmark.RIGHT_KNEE]
    la = landmarks[mp_pose.PoseLandmark.LEFT_ANKLE]
    ra = landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE]
    return abs(lk.x - rk.x) < 0.2 and abs(la.x - ra.x) > 0.25

# ------------------- 语音 & 飞书 -------------------
def speak(text):
    subprocess.run(["say", text])

def warning_voice():
    speak("喵！坐姿错误！请坐直！")

def send_feishu(msg):
    try:
        data = json.dumps({"msg_type": "text", "content": {"text": msg}}).encode()
        req = urllib.request.Request(FEISHU_WEBHOOK, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req)
        print("✅ 飞书推送成功")
    except:
        print("❌ 飞书推送失败")

def save_data(day):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

# ------------------- 【猫咪主题超级美化网页】 -------------------
class WebHandler(BaseHTTPRequestHandler):
    def send_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        self.send_headers()
        path = self.path
        target_date = today

        if "?date=" in path:
            target_date = path.split("?date=")[1]

        data = all_data.get(target_date, all_data[today])
        days = sorted(all_data.keys(), reverse=True)

        html = f'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>🐱 猫咪坐姿守护助手</title>
<style>
* {{
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}}

body {{
  background: #fdf6f0;
  color: #555;
  min-height: 100vh;
  padding: 30px 20px;
  display: flex;
  justify-content: center;
}}

.container {{
  max-width: 780px;
  width: 100%;
}}

/* 标题区域 */
.header {{
  text-align: center;
  margin-bottom: 32px;
}}

.header h1 {{
  font-size: 28px;
  color: #e0a96d;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}}

.header p {{
  color: #999;
  font-size: 15px;
}}

/* 日期选择 */
.date-box {{
  text-align: center;
  margin-bottom: 24px;
}}

select {{
  padding: 10px 16px;
  border-radius: 20px;
  border: none;
  background: #fff;
  color: #666;
  font-size: 14px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  outline: none;
}}

/* 统计卡片 */
.stats {{
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 30px;
}}

.card {{
  background: #ffffff;
  border-radius: 20px;
  padding: 22px;
  text-align: center;
  box-shadow: 0 8px 20px rgba(0,0,0,0.05);
  transition: transform 0.2s ease;
}}

.card:hover {{
  transform: translateY(-4px);
}}

.card .icon {{
  font-size: 22px;
  margin-bottom: 8px;
}}

.card .label {{
  font-size: 14px;
  color: #888;
  margin-bottom: 6px;
}}

.card .num {{
  font-size: 28px;
  font-weight: bold;
  color: #e0a96d;
}}

/* 介绍区域 */
.intro {{
  background: #ffffff;
  border-radius: 20px;
  padding: 26px;
  box-shadow: 0 8px 20px rgba(0,0,0,0.05);
  line-height: 1.7;
}}

.intro h3 {{
  color: #e0a96d;
  margin-bottom: 14px;
  font-size: 18px;
  display: flex;
  align-items: center;
  gap: 8px;
}}

.intro p {{
  color: #777;
  font-size: 15px;
  margin-bottom: 10px;
}}

.tags {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}}

.tags span {{
  background: #f9e9d7;
  color: #d4985a;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 13px;
}}

.footer {{
  text-align: center;
  margin-top: 40px;
  color: #ccc;
  font-size: 13px;
}}
</style>
</head>

<body>
<div class="container">

  <div class="header">
    <h1>🐱 猫咪坐姿守护助手</h1>
    <p>猫咪监督你坐直～每天健康一点点</p>
  </div>

  <div class="date-box">
    <form method="get">
      <select name="date" onchange="this.form.submit()">
        {''.join([f'<option value="{d}" {"selected" if d == target_date else ""}>{d}</option>' for d in days])}
      </select>
    </form>
  </div>

  <div class="stats">
    <div class="card">
      <div class="icon">📅</div>
      <div class="label">今日检测</div>
      <div class="num">{data["total_checks"]}</div>
    </div>
    <div class="card">
      <div class="icon">🙀</div>
      <div class="label">头前伸</div>
      <div class="num">{data["head_forward"]}</div>
    </div>
    <div class="card">
      <div class="icon">😿</div>
      <div class="label">驼背</div>
      <div class="num">{data["hunchback"]}</div>
    </div>
    <div class="card">
      <div class="icon">🐾</div>
      <div class="label">二郎腿</div>
      <div class="num">{data["cross_legs"]}</div>
    </div>
  </div>

  <div class="intro">
    <h3>🐱 关于猫咪坐姿助手</h3>
    <p>这是一个由 AI 驱动的坐姿监测工具，每 5 分钟自动检测一次姿势。</p>
    <p>一旦检测到：驼背、头前伸、翘二郎腿，会立刻语音提醒，并自动记录数据。</p>
    <p>让可爱的猫咪陪你养成健康坐姿～</p>

    <div class="tags">
      <span>AI 姿态识别</span>
      <span>猫咪监督</span>
      <span>语音提醒</span>
      <span>飞书推送</span>
      <span>数据统计</span>
    </div>
  </div>

  <div class="footer">
    🐾 Made with love & cats
  </div>

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
    print("🌐 访问页面：http://localhost:8765")
    print("🎤 语音提醒已开启")
    cap = cv2.VideoCapture(0)
    last_check = time.time()

    with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
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
                        save_data(today)
                    last_check = time.time()

                if is_head_forward(lm, w):
                    cv2.putText(frame, "HEAD FORWARD", (50,50),0,1,(0,0,255),2)
                if is_hunchback(lm):
                    cv2.putText(frame, "HUNCHBACK", (50,100),0,1,(0,0,255),2)
                if is_cross_legs(lm):
                    cv2.putText(frame, "CROSS LEGS", (50,150),0,1,(0,0,255),2)
                mp_drawing.draw_landmarks(frame, res.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            cv2.imshow("AI坐姿监测", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()