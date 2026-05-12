import tkinter as tk
import sqlite3
import threading
import time
import queue
import os
import urllib.request
import serial
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from datetime import datetime
from PIL import Image, ImageTk
 
SERIAL_PORT  = "COM5"
SERIAL_BAUD  = 9600
DB_PATH      = "smart_gym.db"
CAMERA_INDEX = 0
MODEL_PATH   = "pose_landmarker_lite.task"
MODEL_URL    = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task%22
 
_RIGHT_SHOULDER = 12
_RIGHT_WRIST    = 16
 
_POSE_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,7),(0,4),(4,5),(5,6),(6,8),
    (9,10),(11,12),(11,13),(13,15),(15,17),(15,19),(17,19),
    (12,14),(14,16),(16,18),(16,20),(18,20),
    (11,23),(12,24),(23,24),(23,25),(24,26),
    (25,27),(26,28),(27,29),(28,30),(29,31),(30,32),(27,31),(28,32),
]
 
 
def download_model_if_needed():
    if not os.path.exists(MODEL_PATH):
        print("Baixando modelo de pose landmarker...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Modelo baixado com sucesso.")
 
BG_DARK   = "#0d0d0d"
BG_CARD   = "#181818"
ACCENT    = "#e8005a"
ACCENT2   = "#ff3c82"
TEXT_MAIN = "#f0f0f0"
TEXT_DIM  = "#888888"
GREEN_OK  = "#00e676"
YELLOW_W  = "#ffd600"
 
 
def init_db():
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alunos (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            nome       TEXT    NOT NULL,
            uid_rfid   TEXT    NOT NULL UNIQUE,
            exercicio  TEXT    NOT NULL,
            repeticoes INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS log_acessos (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            uid_rfid TEXT    NOT NULL,
            horario  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (aluno_id) REFERENCES alunos(id)
        )
    """)
    cursor.executemany(
        "INSERT OR IGNORE INTO alunos (nome, uid_rfid, exercicio, repeticoes) VALUES (?,?,?,?)",
        [
            ("Carlos Silva",   "00A93926", "Supino Reto",     12),
            ("Mariana Costa",  "4BA49079", "Agachamento",     15),
            ("Pedro Oliveira", "I9J0K1L2", "Desenvolvimento", 10),
            ("Ana Souza",      "M3N4O5P6", "Remada Curvada",  12),
            ("Lucas Ferreira", "Q7R8S9T0", "Leg Press",       20),
        ]
    )
    conn.commit()
    conn.close()
 
 
def buscar_aluno(uid):
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, exercicio, repeticoes FROM alunos WHERE uid_rfid = ?", (uid,))
    row = cursor.fetchone()
    conn.close()
    return {"id": row[0], "nome": row[1], "exercicio": row[2], "repeticoes": row[3]} if row else None
 
 
def registrar_log(aluno_id, uid):
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO log_acessos (aluno_id, uid_rfid, horario) VALUES (?,?,datetime('now','localtime'))",
        (aluno_id, uid)
    )
    conn.commit()
    conn.close()
 
 
def listar_alunos():
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT nome, uid_rfid FROM alunos ORDER BY nome")
    rows = cursor.fetchall()
    conn.close()
    return rows
 
 
class CameraThread(threading.Thread):
    def __init__(self, frame_queue):
        super().__init__(daemon=True)
        self.frame_queue = frame_queue
        self._running    = False
        self.rep_count   = 0
        self._pose_state = "down"
 
        options = mp_vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH)
        )
        self._landmarker = mp_vision.PoseLandmarker.create_from_options(options)
 
    def start_capture(self):
        self._running = True
        if not self.is_alive():
            self.start()
 
    def stop_capture(self):
        self._running    = False
        self.rep_count   = 0
        self._pose_state = "down"
 
    def run(self):
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
        if not cap.isOpened():
            print(f"[Camera] Erro: não foi possível abrir câmera {CAMERA_INDEX}")
            return
        while True:
            if not self._running:
                time.sleep(0.1)
                continue
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue
            try:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb.copy())
                result    = self._landmarker.detect(mp_image)
 
                if result.pose_landmarks:
                    landmarks = result.pose_landmarks[0]
                    h, w = frame_rgb.shape[:2]
                    self._draw_landmarks(frame_rgb, landmarks, h, w)
                    self._count_reps(landmarks)
            except Exception as e:
                print(f"[Camera] Erro no processamento: {e}")
 
            img = Image.fromarray(frame_rgb)
            if not self.frame_queue.empty():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
            self.frame_queue.put(img)
        cap.release()
 
    def _draw_landmarks(self, frame, landmarks, h, w):
        pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
        for a, b in _POSE_CONNECTIONS:
            if a < len(pts) and b < len(pts):
                cv2.line(frame, pts[a], pts[b], (255, 60, 130), 2)
        for x, y in pts:
            cv2.circle(frame, (x, y), 3, (232, 0, 90), -1)
 
    def _count_reps(self, landmarks):
        sy = landmarks[_RIGHT_SHOULDER].y
        wy = landmarks[_RIGHT_WRIST].y
        if wy < sy - 0.05:
            if self._pose_state == "down":
                self.rep_count  += 1
                self._pose_state = "up"
        else:
            self._pose_state = "down"
 
 
class SerialThread(threading.Thread):
    def __init__(self, uid_queue):
        super().__init__(daemon=True)
        self.uid_queue = uid_queue
 
    def run(self):
        while True:
            try:
                ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
                print(f"[Serial] Conectado em {SERIAL_PORT} @ {SERIAL_BAUD} baud")
                while True:
                    line = ser.readline().decode("utf-8", errors="ignore").strip().upper()
                    if line and line != "SMART_GYM_READY":
                        self.uid_queue.put(line)
            except serial.SerialException as e:
                print(f"[Serial] {e} — tentando novamente em 3s...")
                time.sleep(3)
 
 
class SmartGymApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Smart Gym Station")
        self.configure(bg=BG_DARK)
        self.geometry("1100x720")
        self.resizable(False, False)
 
        self.aluno_atual = None
        self.frame_queue = queue.Queue(maxsize=2)
        self.serial_queue = queue.Queue()
        self.camera_thread = CameraThread(self.frame_queue)
        self.camera_thread.start()
        SerialThread(self.serial_queue).start()
 
        self._build_ui()
        self._set_state_waiting()
        self._poll()
 
    def _build_ui(self):
        tk.Frame(self, bg=ACCENT, height=5).pack(fill="x")
 
        top = tk.Frame(self, bg=BG_DARK, pady=14)
        top.pack(fill="x", padx=24)
        tk.Label(top, text="⬡ SMART GYM", bg=BG_DARK, fg=ACCENT,
                 font=("Courier New", 18, "bold")).pack(side="left")
        self.lbl_clock = tk.Label(top, bg=BG_DARK, fg=TEXT_DIM, font=("Courier New", 12))
        self.lbl_clock.pack(side="right")
        self._tick()
 
        main = tk.Frame(self, bg=BG_DARK)
        main.pack(fill="both", expand=True, padx=24, pady=(0, 12))
 
        left = tk.Frame(main, bg=BG_CARD, width=340, padx=20, pady=20)
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)
        self._build_left(left)
 
        right = tk.Frame(main, bg=BG_CARD)
        right.pack(side="left", fill="both", expand=True)
        self._build_right(right)
 
        footer = tk.Frame(self, bg="#111", pady=10)
        footer.pack(fill="x", padx=24)
        tk.Label(footer, text="SIMULAÇÃO RFID:", bg="#111", fg=TEXT_DIM,
                 font=("Courier New", 9)).pack(side="left", padx=(0, 10))
        for nome, uid in listar_alunos():
            tk.Button(footer, text=nome.split()[0], bg="#222", fg=ACCENT2,
                      font=("Courier New", 9, "bold"), relief="flat", padx=10,
                      cursor="hand2",
                      command=lambda u=uid: self._handle_rfid(u)).pack(side="left", padx=3)
        tk.Button(footer, text="UID INVÁLIDO", bg="#222", fg=TEXT_DIM,
                  font=("Courier New", 9), relief="flat", padx=10, cursor="hand2",
                  command=lambda: self._handle_rfid("XXXXXXXX")).pack(side="left", padx=3)
 
    def _build_left(self, p):
        bf = tk.Frame(p, bg=BG_CARD)
        bf.pack(anchor="w", pady=(0, 16))
        self.badge_dot = tk.Label(bf, bg=BG_CARD, font=("Courier New", 13), text="●")
        self.badge_dot.pack(side="left", padx=(0, 5))
        self.badge_lbl = tk.Label(bf, bg=BG_CARD, font=("Courier New", 10, "bold"))
        self.badge_lbl.pack(side="left")
 
        tk.Frame(p, bg=ACCENT, height=1).pack(fill="x", pady=(0, 16))
 
        self.icon_lbl = tk.Label(p, bg=BG_CARD, font=("Courier New", 48))
        self.icon_lbl.pack()
        self.lbl_nome = tk.Label(p, bg=BG_CARD, fg=TEXT_MAIN,
                                 font=("Courier New", 16, "bold"), wraplength=280)
        self.lbl_nome.pack(pady=(10, 2))
        self.lbl_bvindas = tk.Label(p, bg=BG_CARD, fg=TEXT_DIM,
                                    font=("Courier New", 9), wraplength=280)
        self.lbl_bvindas.pack()
 
        tk.Frame(p, bg="#333", height=1).pack(fill="x", pady=16)
 
        tk.Label(p, text="EXERCÍCIO", bg=BG_CARD, fg=TEXT_DIM,
                 font=("Courier New", 8)).pack(anchor="w")
        self.lbl_ex = tk.Label(p, text="—", bg=BG_CARD, fg=TEXT_MAIN,
                               font=("Courier New", 13, "bold"))
        self.lbl_ex.pack(anchor="w", pady=(2, 12))
 
        tk.Label(p, text="META", bg=BG_CARD, fg=TEXT_DIM,
                 font=("Courier New", 8)).pack(anchor="w")
        self.lbl_meta = tk.Label(p, text="—", bg=BG_CARD, fg=ACCENT2,
                                 font=("Courier New", 20, "bold"))
        self.lbl_meta.pack(anchor="w", pady=(2, 12))
 
        tk.Label(p, text="REPETIÇÕES REALIZADAS", bg=BG_CARD, fg=TEXT_DIM,
                 font=("Courier New", 8)).pack(anchor="w")
        self.lbl_reps = tk.Label(p, text="0", bg=BG_CARD, fg=GREEN_OK,
                                 font=("Courier New", 30, "bold"))
        self.lbl_reps.pack(anchor="w", pady=(2, 16))
 
        self.btn_out = tk.Button(p, text="⏏  ENCERRAR SESSÃO", bg=ACCENT, fg="white",
                                 relief="flat", font=("Courier New", 10, "bold"),
                                 cursor="hand2", activebackground="#c0004a",
                                 command=self._logout)
        self.btn_out.pack(fill="x")
 
    def _build_right(self, p):
        ch = tk.Frame(p, bg=BG_CARD, pady=10, padx=14)
        ch.pack(fill="x")
        tk.Label(ch, text="MONITORAMENTO — MEDIAPIPE", bg=BG_CARD, fg=TEXT_DIM,
                 font=("Courier New", 9)).pack(side="left")
        self.lbl_cam = tk.Label(ch, text="● OFFLINE", bg=BG_CARD, fg=TEXT_DIM,
                                font=("Courier New", 9))
        self.lbl_cam.pack(side="right")
        self.canvas = tk.Canvas(p, bg="#111", bd=0, highlightthickness=0,
                                width=700, height=500)
        self.canvas.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self._placeholder()
 
    def _set_state_waiting(self):
        self.badge_dot.config(fg=YELLOW_W)
        self.badge_lbl.config(text="AGUARDANDO LOGIN", fg=YELLOW_W)
        self.icon_lbl.config(text="🏋️")
        self.lbl_nome.config(text="Aproxime seu\ncartão RFID", fg=TEXT_DIM)
        self.lbl_bvindas.config(text="")
        self.lbl_ex.config(text="—")
        self.lbl_meta.config(text="—")
        self.lbl_reps.config(text="0", fg=GREEN_OK)
        self.btn_out.config(state="disabled", bg="#444")
        self.lbl_cam.config(text="● OFFLINE", fg=TEXT_DIM)
        self.camera_thread.stop_capture()
        self._placeholder()
 
    def _set_state_active(self, aluno):
        self.aluno_atual = aluno
        now = datetime.now()
        self.badge_dot.config(fg=GREEN_OK)
        self.badge_lbl.config(text="TREINO ATIVO", fg=GREEN_OK)
        self.icon_lbl.config(text="✅")
        self.lbl_nome.config(text=aluno["nome"], fg=TEXT_MAIN)
        self.lbl_bvindas.config(
            text=f"Bem-vindo(a)! Sessão iniciada às {now.strftime('%H:%M:%S')}")
        self.lbl_ex.config(text=aluno["exercicio"])
        self.lbl_meta.config(text=str(aluno["repeticoes"]))
        self.lbl_reps.config(text="0", fg=GREEN_OK)
        self.btn_out.config(state="normal", bg=ACCENT)
        self.lbl_cam.config(text="● AO VIVO", fg=GREEN_OK)
        self.camera_thread.rep_count = 0
        self.camera_thread.start_capture()
 
    def _logout(self):
        self.aluno_atual = None
        self._set_state_waiting()
 
    def _handle_rfid(self, uid):
        if self.aluno_atual:
            return
        aluno = buscar_aluno(uid)
        if aluno:
            registrar_log(aluno["id"], uid)
            self._set_state_active(aluno)
        else:
            self.badge_dot.config(fg=ACCENT)
            self.badge_lbl.config(text=f"UID NÃO ENCONTRADO: {uid}", fg=ACCENT)
            self.after(3000, lambda: self._set_state_waiting() if not self.aluno_atual else None)
 
    def _poll(self):
        try:
            uid = self.serial_queue.get_nowait()
            self._handle_rfid(uid)
        except queue.Empty:
            pass
 
        if self.aluno_atual:
            try:
                img   = self.frame_queue.get_nowait()
                self._draw(img)
                count = self.camera_thread.rep_count
                self.lbl_reps.config(
                    text=str(count),
                    fg=ACCENT if count >= self.aluno_atual["repeticoes"] else GREEN_OK
                )
            except queue.Empty:
                pass
        self.after(33, self._poll)
 
    def _draw(self, img):
        cw = self.canvas.winfo_width()  or 700
        ch = self.canvas.winfo_height() or 500
        r  = img.resize((cw, ch), Image.LANCZOS)
        self._ph = ImageTk.PhotoImage(r)
        self.canvas.create_image(0, 0, anchor="nw", image=self._ph)
 
    def _placeholder(self):
        self.canvas.delete("all")
        w, h = 700, 500
        self.canvas.create_rectangle(0, 0, w, h, fill="#111", outline="")
        self.canvas.create_text(w//2, h//2 - 20, text="📷",
                                font=("Courier New", 44), fill="#333")
        self.canvas.create_text(w//2, h//2 + 34, text="Câmera ativa após identificação",
                                font=("Courier New", 11), fill="#444")
 
    def _tick(self):
        self.lbl_clock.config(text=datetime.now().strftime("%d/%m/%Y  %H:%M:%S"))
        self.after(1000, self._tick)
 
    def on_close(self):
        self.camera_thread.stop_capture()
        self.destroy()
 
 
if __name__ == "__main__":
    download_model_if_needed()
    init_db()
    app = SmartGymApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
 
