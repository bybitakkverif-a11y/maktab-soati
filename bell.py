import sys
import os
import time
import json
import threading
import ctypes
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Musiqa chalish uchun pygame.mixer (juda yengil va ishonchli)
import pygame

# --- Windows Uyqu Rejimini Bloklash Funksiyasi ---
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

def prevent_sleep():
    """Tizimni dastur ishlab turganda uyquga ketishidan saqlaydi"""
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )
    except Exception as e:
        print(f"Uyqu bloklash xatosi: {e}")

def allow_sleep():
    """Dastur yopilganda normal holatga qaytaradi"""
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:
        pass

# --- Baza dars jadvali ---
DEFAULT_SCHEDULE = [
    {"time": "08:30", "event": "1-Dars Kirish", "sound": ""},
    {"time": "09:15", "event": "1-Dars Chiqish", "sound": ""},
    {"time": "09:20", "event": "2-Dars Kirish", "sound": ""},
    {"time": "10:05", "event": "2-Dars Chiqish", "sound": ""},
    {"time": "10:10", "event": "3-Dars Kirish", "sound": ""},
    {"time": "10:55", "event": "3-Dars Chiqish", "sound": ""},
    {"time": "11:00", "event": "4-Dars Kirish", "sound": ""},
    {"time": "11:45", "event": "4-Dars Chiqish (Katta tanaffus)", "sound": ""},
    {"time": "12:15", "event": "5-Dars Kirish", "sound": ""},
    {"time": "13:00", "event": "5-Dars Chiqish", "sound": ""},
    {"time": "13:05", "event": "6-Dars Kirish", "sound": ""},
    {"time": "13:50", "event": "6-Dars Chiqish", "sound": ""},
    {"time": "13:55", "event": "7-Dars Kirish", "sound": ""},
    {"time": "14:40", "event": "7-Dars Chiqish", "sound": ""},
]

CONFIG_FILE = "bell_config.json"

class SchoolBellApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Avtomatlashtirilgan Maktab Qo'ng'irog'i")
        self.root.geometry("780x560")
        self.root.minsize(650, 450)
        
        # Audio tizimini ishga tushirish
        pygame.mixer.init()
        
        # Uyqu rejimini taqiqlash
        prevent_sleep()
        
        self.schedule_data = self.load_config()
        self.played_today = set()
        self.is_running = True
        
        self.setup_ui()
        
        # Orqa fonda vaqtni tekshiruvchi thread
        self.monitor_thread = threading.Thread(target=self.time_monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        # Oyna yopilganda to'g'ri chiqish
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    # Eskisini yangi parametrlar bilan sinxronlash
                    return saved
            except Exception:
                pass
        return DEFAULT_SCHEDULE

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.schedule_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Xato", f"Sozlamalarni saqlashda xato: {e}")

    def setup_ui(self):
        # Yuqori qism: Soat va Status
        top_frame = tk.Frame(self.root, bg="#1e293b", pady=10)
        top_frame.pack(fill=tk.X)
        
        self.clock_label = tk.Label(top_frame, text="00:00:00", font=("Consolas", 26, "bold"), fg="#38bdf8", bg="#1e293b")
        self.clock_label.pack()
        
        self.status_label = tk.Label(top_frame, text="Tizim faol | Uyqu rejimi bloklangan", font=("Arial", 10), fg="#a7f3d0", bg="#1e293b")
        self.status_label.pack()
        
        self.update_clock()

        # O'rta qism: Jadval
        mid_frame = tk.Frame(self.root, padx=10, pady=10)
        mid_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("time", "event", "sound")
        self.tree = ttk.Treeview(mid_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("time", text="Vaqt")
        self.tree.heading("event", text="Hodisa / Dars")
        self.tree.heading("sound", text="Tanlangan Musiqa Fayli")
        
        self.tree.column("time", width=80, anchor=tk.CENTER)
        self.tree.column("event", width=220, anchor=tk.W)
        self.tree.column("sound", width=380, anchor=tk.W)
        
        scrollbar = ttk.Scrollbar(mid_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.refresh_tree()

        # Pastki qism: Tugmalar
        btn_frame = tk.Frame(self.root, pady=10)
        btn_frame.pack(fill=tk.X)

        btn_select_sound = tk.Button(btn_frame, text="🎵 Musiqa Tanlash (Fayl biriktirish)", 
                                     font=("Arial", 10, "bold"), bg="#0284c7", fg="white", 
                                     padx=10, pady=5, command=self.choose_sound_for_selected)
        btn_select_sound.pack(side=tk.LEFT, padx=10)

        btn_test = tk.Button(btn_frame, text="▶ Sinov (Eshitib ko'rish)", 
                             font=("Arial", 10), bg="#10b981", fg="white", 
                             padx=10, pady=5, command=self.test_selected_sound)
        btn_test.pack(side=tk.LEFT, padx=5)

        btn_stop = tk.Button(btn_frame, text="⏹ To'xtatish", 
                             font=("Arial", 10), bg="#ef4444", fg="white", 
                             padx=10, pady=5, command=self.stop_sound)
        btn_stop.pack(side=tk.LEFT, padx=5)

    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, row in enumerate(self.schedule_data):
            sound_display = os.path.basename(row["sound"]) if row["sound"] else "[Fayl belgilanmagan]"
            self.tree.insert("", tk.END, iid=str(i), values=(row["time"], row["event"], sound_display))

    def update_clock(self):
        now_str = datetime.now().strftime("%H:%M:%S")
        self.clock_label.config(text=now_str)
        self.root.after(1000, self.update_clock)

    def choose_sound_for_selected(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Ogohlantirish", "Avval jadvaldan biror qatorni tanlang!")
            return
        
        idx = int(selected_item[0])
        file_path = filedialog.askopenfilename(
            title="Qo'ng'iroq musiqasini tanlang",
            filetypes=[("Audio fayllar", "*.mp3 *.wav *.ogg")]
        )
        if file_path:
            self.schedule_data[idx]["sound"] = file_path
            self.save_config()
            self.refresh_tree()
            self.tree.selection_set(str(idx))

    def test_selected_sound(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Ogohlantirish", "Qaysi musiqani sinamoqchisiz? Qatorni tanlang.")
            return
        idx = int(selected_item[0])
        sound_path = self.schedule_data[idx]["sound"]
        if sound_path and os.path.exists(sound_path):
            self.play_audio(sound_path)
        else:
            messagebox.showwarning("Xato", "Ushbu vaqt uchun musiqa fayli tanlanmagan yoki fayl o'chirilgan!")

    def play_audio(self, path):
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
        except Exception as e:
            messagebox.showerror("Audio Xatosi", f"Musiqani chalishda xatolik: {e}")

    def stop_sound(self):
        pygame.mixer.music.stop()

    def time_monitor_loop(self):
        """Orqa fonda har soniyada vaqtni tekshirib turadi"""
        while self.is_running:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            current_seconds = now.second
            
            # Yangi kunda tarixdagi ijrolarni tozalash (00:00 da)
            if current_time == "00:00" and current_seconds < 2:
                self.played_today.clear()
            
            # Jadvaldagi vaqtlarni solishtiramiz
            for row in self.schedule_data:
                target_time = row["time"]
                
                # Agar ayni daqiqa kelgan bo'lsa va bu daqiqada hali chalinmagan bo'lsa
                if current_time == target_time and target_time not in self.played_today:
                    self.played_today.add(target_time)
                    sound = row.get("sound", "")
                    if sound and os.path.exists(sound):
                        self.play_audio(sound)
                    break
            
            time.sleep(1)

    def on_close(self):
        self.is_running = False
        allow_sleep()
        self.root.destroy()
        sys.exit()

if __name__ == "__main__":
    root = tk.Tk()
    app = SchoolBellApp(root)
    root.mainloop()