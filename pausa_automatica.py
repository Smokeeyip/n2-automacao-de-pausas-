import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui
import threading
import time
import json
import os
import ctypes
from datetime import datetime, timedelta

try:
    import win32gui
    import win32con
except ImportError:
    win32gui = None
    win32con = None

pyautogui.PAUSE = 0.12
pyautogui.FAILSAFE = True

APP_DIR = os.path.join(os.path.expanduser("~"), "PausaAutomatica")
os.makedirs(APP_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(APP_DIR, "config.json")

DEFAULT_CONFIG = {
    "target_window": "",
    "pause_button": None,
    "unpause_button": None,
    "categories": {},
    "schedules": []
}

def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return DEFAULT_CONFIG.copy()

config = load_config()

def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def list_windows():
    result = []
    if win32gui:
        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).strip()
                if title:
                    result.append((hwnd, title))
        win32gui.EnumWindows(callback, None)
    return result

def activate_window(title):
    """Ativa a janela alvo usando Win32, inclusive quando o Windows bloqueia
    SetForegroundWindow por pertencer a outro processo."""
    if not win32gui:
        return None
    for hwnd, text in list_windows():
        if text != title:
            continue
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            else:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            try:
                fg = win32gui.GetForegroundWindow()
                cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
                target_tid = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
                fg_tid = ctypes.windll.user32.GetWindowThreadProcessId(fg, None) if fg else 0
                attached = []
                for tid in (target_tid, fg_tid):
                    if tid and tid != cur_tid:
                        if ctypes.windll.user32.AttachThreadInput(cur_tid, tid, True):
                            attached.append(tid)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                ctypes.windll.user32.BringWindowToTop(hwnd)
                for tid in attached:
                    ctypes.windll.user32.AttachThreadInput(cur_tid, tid, False)
            except Exception:
                try: win32gui.BringWindowToTop(hwnd)
                except Exception: pass
                try: win32gui.SetForegroundWindow(hwnd)
                except Exception: pass
            time.sleep(0.35)
            return hwnd
        except Exception:
            return None
    return None

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("N2")
        self.root.geometry("900x720")
        self.root.configure(bg="#151515")
        self.root.resizable(False, False)
        self.running = False
        self.capture_mode = None
        self.capture_category = None
        self.menu_wait_seconds = 1.5
        self.action_lock = threading.Lock()

        self.build_ui()
        self.refresh_windows()
        self.refresh_positions()
        self.refresh_categories()
        self.refresh_schedules()
        self.update_clock()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        BG = "#0b0d10"
        PANEL = "#14181d"
        PANEL2 = "#101419"
        BORDER = "#242a31"
        TEXT = "#f4f6f8"
        MUTED = "#8b949e"
        RED = "#e31b23"
        RED_DARK = "#a90f15"
        GREEN = "#32d583"
        self.root.configure(bg=BG)
        self.root.title("N2")
        self.root.geometry("960x780")
        self.root.resizable(False, False)

        style.configure("N2.TButton", font=("Segoe UI", 9, "bold"), padding=(13, 8), foreground=TEXT, background="#20262d", borderwidth=0)
        style.map("N2.TButton", background=[("active", "#2b323a")])
        style.configure("N2.Red.TButton", font=("Segoe UI", 9, "bold"), padding=(15, 9), foreground="white", background=RED, borderwidth=0)
        style.map("N2.Red.TButton", background=[("active", RED_DARK)])
        style.configure("N2.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 9))
        style.configure("N2.Muted.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 8))
        style.configure("N2.TLabelframe", background=PANEL, foreground=TEXT, borderwidth=1, relief="solid")
        style.configure("N2.TLabelframe.Label", background=PANEL, foreground=RED, font=("Segoe UI", 10, "bold"))
        style.configure("N2.TCombobox", fieldbackground="#0e1216", background="#20262d", foreground=TEXT, arrowcolor=TEXT)
        style.configure("N2.TEntry", fieldbackground="#0e1216", foreground=TEXT, insertcolor=TEXT)

        # Header / brand
        header = tk.Frame(self.root, bg="#11151a", height=92, highlightthickness=1, highlightbackground=BORDER)
        header.pack(fill="x")
        header.pack_propagate(False)
        brand = tk.Frame(header, bg="#11151a")
        brand.pack(side="left", padx=24, pady=15)
        tk.Label(brand, text="N2", bg="#11151a", fg="white", font=("Segoe UI", 30, "bold")).pack(side="left")
        tk.Frame(brand, bg=RED, width=4, height=38).pack(side="left", padx=13)
        tk.Label(brand, text="PAINEL DE AUTOMAÇÃO", bg="#11151a", fg=MUTED, font=("Segoe UI", 10, "bold")).pack(side="left", pady=(8,0))

        self.header_status = tk.Label(header, text="● PARADO", bg="#11151a", fg=MUTED, font=("Segoe UI", 10, "bold"))
        self.header_status.pack(side="right", padx=24)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=16)

        # Top status strip
        strip = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        strip.pack(fill="x", pady=(0, 12))
        tk.Label(strip, text="CONTROLE", bg=PANEL, fg=RED, font=("Segoe UI", 8, "bold")).pack(side="left", padx=15, pady=12)
        tk.Label(strip, text="Configure uma vez e deixe o N2 cuidar dos horários automaticamente.", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        self.clock_lbl = tk.Label(strip, text="", bg=PANEL, fg="#c7cdd4", font=("Consolas", 9, "bold"))
        self.clock_lbl.pack(side="right", padx=15)

        target = ttk.LabelFrame(body, text=" 01  •  JANELA ALVO ", padding=12, style="N2.TLabelframe")
        target.pack(fill="x", pady=6)
        self.window_combo = ttk.Combobox(target, state="readonly", width=67, style="N2.TCombobox")
        self.window_combo.grid(row=0, column=0, padx=(4,8), pady=3)
        ttk.Button(target, text="↻  Atualizar", command=self.refresh_windows, style="N2.TButton").grid(row=0,column=1,padx=4)
        ttk.Button(target, text="Salvar", command=self.save_window, style="N2.Red.TButton").grid(row=0,column=2,padx=4)
        ttk.Label(target, text="A automação usa a janela selecionada como referência dos pontos configurados.", style="N2.Muted.TLabel").grid(row=1,column=0,columnspan=3,sticky="w",padx=4,pady=(7,0))

        pos = ttk.LabelFrame(body, text=" 02  •  PONTOS DE CONTROLE ", padding=12, style="N2.TLabelframe")
        pos.pack(fill="x", pady=6)
        self.pause_lbl = tk.Label(pos, text="", anchor="w", bg=PANEL, fg=TEXT, font=("Segoe UI",9))
        self.pause_lbl.grid(row=0,column=0,sticky="w",padx=4,pady=4)
        ttk.Button(pos,text="Definir PAUSAR",command=lambda:self.start_capture("pause"),style="N2.TButton").grid(row=0,column=1,padx=8)
        self.unpause_lbl = tk.Label(pos, text="", anchor="w", bg=PANEL, fg=TEXT, font=("Segoe UI",9))
        self.unpause_lbl.grid(row=1,column=0,sticky="w",padx=4,pady=4)
        ttk.Button(pos,text="Definir DESPAUSAR",command=lambda:self.start_capture("unpause"),style="N2.TButton").grid(row=1,column=1,padx=8)
        ttk.Label(pos,text="Os pontos ficam vinculados à janela para maior estabilidade.",style="N2.Muted.TLabel").grid(row=2,column=0,columnspan=2,sticky="w",padx=4,pady=(6,0))

        cat = ttk.LabelFrame(body, text=" 03  •  CATEGORIAS ", padding=12, style="N2.TLabelframe")
        cat.pack(fill="x", pady=6)
        ttk.Label(cat,text="Nome",style="N2.TLabel").grid(row=0,column=0,padx=4)
        self.cat_name=ttk.Entry(cat,width=24,style="N2.TEntry")
        self.cat_name.grid(row=0,column=1,padx=5)
        ttk.Button(cat,text="Adicionar / atualizar",command=self.add_category,style="N2.TButton").grid(row=0,column=2,padx=5)
        ttk.Button(cat,text="Definir clique",command=self.capture_selected_category,style="N2.Red.TButton").grid(row=0,column=3,padx=5)
        ttk.Button(cat,text="Excluir",command=self.delete_category,style="N2.TButton").grid(row=0,column=4,padx=5)
        self.cat_list=tk.Listbox(cat,height=3,width=88,bg="#0d1115",fg=TEXT,selectbackground=RED,selectforeground="white",relief="flat",highlightthickness=1,highlightbackground=BORDER,font=("Segoe UI",9))
        self.cat_list.grid(row=1,column=0,columnspan=5,sticky="w",padx=4,pady=9)
        self.cat_list.bind("<<ListboxSelect>>",self.category_selected)
        ttk.Label(cat,text="Defina o clique da categoria apenas uma vez; o N2 reutiliza a posição nos próximos agendamentos.",style="N2.Muted.TLabel").grid(row=2,column=0,columnspan=5,sticky="w",padx=4)

        sched=ttk.LabelFrame(body,text=" 04  •  AGENDAMENTOS ",padding=12,style="N2.TLabelframe")
        sched.pack(fill="x",pady=6)
        ttk.Label(sched,text="Horário",style="N2.TLabel").grid(row=0,column=0,padx=4)
        self.time_entry=ttk.Entry(sched,width=8,style="N2.TEntry"); self.time_entry.insert(0,"09:00"); self.time_entry.grid(row=0,column=1,padx=5)
        ttk.Label(sched,text="Duração (min)",style="N2.TLabel").grid(row=0,column=2,padx=8)
        self.duration_entry=ttk.Entry(sched,width=8,style="N2.TEntry"); self.duration_entry.insert(0,"10"); self.duration_entry.grid(row=0,column=3,padx=5)
        ttk.Label(sched,text="Categoria",style="N2.TLabel").grid(row=0,column=4,padx=8)
        self.cat_combo=ttk.Combobox(sched,state="readonly",width=19,style="N2.TCombobox"); self.cat_combo.grid(row=0,column=5,padx=5)
        ttk.Button(sched,text="＋  Adicionar",command=self.add_schedule,style="N2.Red.TButton").grid(row=0,column=6,padx=8)
        self.schedule_list=tk.Listbox(sched,height=5,width=101,bg="#0d1115",fg=TEXT,selectbackground=RED,selectforeground="white",relief="flat",highlightthickness=1,highlightbackground=BORDER,font=("Segoe UI",9))
        self.schedule_list.grid(row=1,column=0,columnspan=7,sticky="w",pady=10)
        ttk.Button(sched,text="Excluir horário",command=self.delete_schedule,style="N2.TButton").grid(row=2,column=0,padx=4)
        self.status_lbl=tk.Label(sched,text="● PARADO",bg=PANEL,fg=RED,font=("Segoe UI",10,"bold"),anchor="w")
        self.status_lbl.grid(row=2,column=1,columnspan=6,sticky="w",padx=15)

        bottom=tk.Frame(body,bg=BG)
        bottom.pack(fill="x",pady=(10,0))
        self.start_btn=ttk.Button(bottom,text="▶  INICIAR N2",command=self.toggle_running,style="N2.Red.TButton")
        self.start_btn.pack(side="left")
        ttk.Button(bottom,text="TESTAR PAUSA",command=self.test_pause,style="N2.TButton").pack(side="left",padx=8)
        ttk.Button(bottom,text="TESTAR DESPAUSA",command=self.test_unpause,style="N2.TButton").pack(side="left")
        tk.Label(bottom,text="N2",bg=BG,fg="#3b424a",font=("Segoe UI",9,"bold")).pack(side="right")

    def update_clock(self):
        self.clock_lbl.config(text=datetime.now().strftime("%d/%m/%Y  %H:%M:%S"))
        self.root.after(500,self.update_clock)

    def refresh_windows(self):
        vals=[title for _,title in list_windows()]
        self.window_combo["values"]=vals
        saved=config.get("target_window","")
        if saved in vals: self.window_combo.set(saved)
        elif vals: self.window_combo.current(0)

    def save_window(self):
        value=self.window_combo.get().strip()
        if not value:
            messagebox.showwarning("Janela","Selecione uma janela.")
            return
        config["target_window"]=value
        save_config()
        messagebox.showinfo("Janela","Janela salva como alvo da automação.")

    def refresh_positions(self):
        self.pause_lbl.config(text=f"PAUSAR: {config.get('pause_button') or 'não definido'}")
        self.unpause_lbl.config(text=f"DESPAUSAR: {config.get('unpause_button') or 'não definido'}")

    def refresh_categories(self):
        self.cat_list.delete(0,tk.END)
        names=list(config["categories"].keys())
        for n in names: self.cat_list.insert(tk.END,n)
        self.cat_combo["values"]=names
        if names and not self.cat_combo.get(): self.cat_combo.current(0)

    def refresh_schedules(self):
        self.schedule_list.delete(0,tk.END)
        for s in sorted(config["schedules"],key=lambda x:x["time"]):
            self.schedule_list.insert(tk.END,f'{s["time"]}  |  {s["duration"]} min  |  {s["category"]}')

    def start_capture(self,mode):
        self.capture_mode=mode
        msg="PAUSAR" if mode=="pause" else "DESPAUSAR"
        messagebox.showinfo("N2 • Capturar posição",f"Quando você apertar OK, o N2 começará a captura de {msg}.\n\nColoque o cursor no local correto e aguarde a contagem.")
        threading.Thread(target=self.wait_capture,args=(mode,),daemon=True).start()

    def wait_capture(self,mode):
        try:
            if mode == "pause":
                # Guia o cursor para o ponto atualmente salvo, se existir; caso contrário, apenas inicia a contagem.
                old = config.get("pause_button")
                if old:
                    x,y=self._screen_pos(old)
                    pyautogui.moveTo(x,y,duration=.5)
                    self.root.after(0,lambda:self.status_lbl.config(text="CAPTURA PAUSAR • cursor guiado ao ponto salvo"))
                for r in range(5,0,-1):
                    self.root.after(0,lambda x=r:self.status_lbl.config(text=f"CAPTURANDO PAUSAR • {x}s")); time.sleep(1)
            else:
                for r in range(5,0,-1):
                    self.root.after(0,lambda x=r:self.status_lbl.config(text=f"CAPTURANDO DESPAUSAR • {x}s")); time.sleep(1)
            pos=pyautogui.position()
            config["pause_button" if mode=="pause" else "unpause_button"]=self._save_window_relative_pos(pos)
            save_config()
            self.root.after(0,self.refresh_positions)
            self.root.after(0,lambda:self.status_lbl.config(text=f"✓ {('PAUSAR' if mode=='pause' else 'DESPAUSAR')} SALVO • posição vinculada à janela N2"))
            self.root.after(0,lambda:messagebox.showinfo("N2 • Posição salva",f"✓ Posição de {('PAUSAR' if mode=='pause' else 'DESPAUSAR')} salva e vinculada à janela selecionada.\n\nO N2 poderá reposicionar o cursor automaticamente mesmo se a janela estiver em outro local da tela."))
        except Exception as e:
            self.root.after(0,lambda:self.status_lbl.config(text="ERRO NA CAPTURA"))
            self.root.after(0,lambda err=str(e):messagebox.showerror("N2 • Captura",err))

    def capture_selected_category(self):
        sel=self.cat_list.curselection()
        if not sel:
            messagebox.showwarning("N2 • Categoria","Selecione uma categoria."); return
        if not config.get("pause_button"):
            messagebox.showwarning("N2 • Categoria","Defina o botão PAUSAR primeiro."); return
        name=self.cat_list.get(sel[0]); self.capture_category=name
        messagebox.showinfo("N2 • Capturar categoria",f'Clique em OK. O N2 irá automaticamente para o botão PAUSAR e abrirá o menu.\n\nDepois, mova o mouse para "{name}". A posição será capturada após a contagem.')
        threading.Thread(target=self.wait_category_capture,args=(name,),daemon=True).start()

    def wait_category_capture(self,name):
        try:
            self.focus_target()
            # Movimento visível e separado do clique para deixar claro que a automação está no ponto certo.
            self.root.after(0,lambda:self.status_lbl.config(text="GUIANDO CURSOR → PAUSAR"))
            x,y=self._screen_pos(config["pause_button"])
            pyautogui.moveTo(x,y,duration=.7)
            time.sleep(.3)
            self.root.after(0,lambda:self.status_lbl.config(text="CLICANDO PAUSAR → abrindo menu"))
            pyautogui.click()
            time.sleep(self.menu_wait_seconds)
            for r in range(8,0,-1):
                self.root.after(0,lambda x=r:self.status_lbl.config(text=f'MENU ABERTO • coloque em "{name}" • {x}s'))
                time.sleep(1)
            pos=pyautogui.position()
            config["categories"][name]=self._save_window_relative_pos(pos)
            save_config(); self.root.after(0,self.refresh_categories)
            self.root.after(0,lambda:self.status_lbl.config(text=f'✓ {name.upper()} SALVO • posição vinculada à janela N2'))
            self.root.after(0,lambda:messagebox.showinfo("N2 • Categoria salva",f'✓ Categoria "{name}" configurada e vinculada à janela selecionada.\n\nO N2 moverá o cursor automaticamente até ela na execução programada.'))
        except Exception as e:
            self.root.after(0,lambda:self.status_lbl.config(text="ERRO NA CAPTURA"))
            self.root.after(0,lambda err=str(e):messagebox.showerror("N2 • Captura",err))

    def add_category(self):
        name=self.cat_name.get().strip()
        if not name:
            messagebox.showwarning("Categoria","Digite o nome.")
            return
        config["categories"].setdefault(name,None)
        save_config()
        self.cat_name.delete(0,tk.END)
        self.refresh_categories()

    def category_selected(self,_=None):
        sel=self.cat_list.curselection()
        if sel:
            self.cat_name.delete(0,tk.END)
            self.cat_name.insert(0,self.cat_list.get(sel[0]))

    def delete_category(self):
        sel=self.cat_list.curselection()
        if not sel: return
        name=self.cat_list.get(sel[0])
        if messagebox.askyesno("Excluir",f'Excluir a categoria "{name}"?'):
            config["categories"].pop(name,None)
            config["schedules"]=[s for s in config["schedules"] if s["category"]!=name]
            save_config()
            self.refresh_categories()
            self.refresh_schedules()

    def add_schedule(self):
        t=self.time_entry.get().strip()
        dur=self.duration_entry.get().strip()
        cat=self.cat_combo.get().strip()
        try:
            datetime.strptime(t,"%H:%M")
            d=int(dur)
            if d<1 or d>720: raise ValueError
        except:
            messagebox.showerror("Programação","Use HH:MM e duração entre 1 e 720 minutos.")
            return
        if not cat or not config["categories"].get(cat):
            messagebox.showerror("Programação","Selecione uma categoria já configurada.")
            return
        if not config.get("pause_button") or not config.get("unpause_button"):
            messagebox.showerror("Programação","Defina PAUSAR e DESPAUSAR primeiro.")
            return
        config["schedules"].append({"time":t,"duration":d,"category":cat})
        save_config()
        self.refresh_schedules()
        self.status_lbl.config(text=f"✓ AGENDAMENTO SALVO • {t} • {cat.upper()} • {d} min")
        self.header_status.config(text="● AGENDADO")
        # O agendamento passa a ficar ativo imediatamente. Não é necessário
        # apertar outro botão depois de cadastrar o horário.
        if not self.running:
            self.start_scheduler()
        messagebox.showinfo("N2 • Agendamento salvo",f"✓ AGENDAMENTO SALVO COM SUCESSO\n\n⏰ Horário: {t}\n📍 Categoria: {cat.upper()}\n⏱ Duração: {d} min\n\n🟢 AGENDAMENTO ATIVO\nO N2 já está aguardando o horário usando o relógio do Windows.")

    def delete_schedule(self):
        sel=self.schedule_list.curselection()
        if not sel: return
        ordered=sorted(config["schedules"],key=lambda x:x["time"])
        item=ordered[sel[0]]
        config["schedules"].remove(item)
        save_config()
        self.refresh_schedules()

    def focus_target(self):
        title=config.get("target_window","").strip()
        if not title:
            return None
        hwnd=activate_window(title)
        if not hwnd:
            raise RuntimeError("A janela escolhida não está aberta ou não pôde ser ativada.")
        return hwnd

    def _screen_pos(self, pos):
        """Converte posições salvas relativas à área cliente da janela para a tela."""
        if not pos:
            raise RuntimeError("Posição de clique inválida.")
        if isinstance(pos, dict) and pos.get("relative"):
            hwnd=self.focus_target()
            if not hwnd:
                raise RuntimeError("Não foi possível ativar a janela alvo.")
            try:
                point=win32gui.ClientToScreen(hwnd, (int(pos["x"]), int(pos["y"])))
                return int(point[0]), int(point[1])
            except Exception as e:
                raise RuntimeError(f"Não foi possível calcular a posição na janela: {e}")
        # Compatibilidade com configurações antigas: coordenada absoluta.
        return int(pos[0]), int(pos[1])

    def _save_window_relative_pos(self, screen_pos):
        title=config.get("target_window","").strip()
        if win32gui and title:
            hwnd=activate_window(title)
            if hwnd:
                try:
                    point=win32gui.ScreenToClient(hwnd, (int(screen_pos.x), int(screen_pos.y)))
                    return {"relative": True, "x": int(point[0]), "y": int(point[1])}
                except Exception:
                    pass
        return [int(screen_pos.x), int(screen_pos.y)]

    def _client_point(self, pos):
        if not pos:
            raise RuntimeError("Posição de clique inválida.")
        if isinstance(pos, dict) and pos.get("relative"):
            hwnd = self.get_target_hwnd()
            if not hwnd:
                raise RuntimeError("Não foi possível localizar a janela alvo.")
            return int(pos["x"]), int(pos["y"]), hwnd
        # Compatibilidade: coordenada antiga absoluta -> converte para cliente.
        hwnd = self.get_target_hwnd()
        if not hwnd:
            raise RuntimeError("Não foi possível localizar a janela alvo.")
        pt = win32gui.ScreenToClient(hwnd, (int(pos[0]), int(pos[1])))
        return int(pt[0]), int(pt[1]), hwnd

    def get_target_hwnd(self):
        title=config.get("target_window","").strip()
        if not title or not win32gui:
            return None
        for hwnd,text in list_windows():
            if text == title:
                return hwnd
        return None

    def _find_window_at_client_point(self, root_hwnd, cx, cy):
        """Tenta localizar o popup/menu que contém o ponto salvo.
        Isso permite clicar em menus padrão mesmo sem mexer no mouse físico."""
        try:
            screen_pt=win32gui.ClientToScreen(root_hwnd,(cx,cy))
            found=[]
            root_tid=ctypes.windll.user32.GetWindowThreadProcessId(root_hwnd,None)
            def enum_cb(hwnd,_):
                try:
                    if not win32gui.IsWindowVisible(hwnd): return
                    tid=ctypes.windll.user32.GetWindowThreadProcessId(hwnd,None)
                    if tid != root_tid: return
                    l,t,r,b=win32gui.GetWindowRect(hwnd)
                    if l <= screen_pt[0] < r and t <= screen_pt[1] < b:
                        found.append((hwnd,(r-l)*(b-t)))
                except Exception: pass
            win32gui.EnumThreadWindows(root_tid, enum_cb, None)
            if found:
                found.sort(key=lambda x:x[1])
                return found[0][0]
        except Exception:
            pass
        return root_hwnd

    def background_click(self, pos, label=None):
        """Clique sem mover o cursor e sem ativar a janela.
        Usa mensagens Win32, permitindo que o N2 continue agendando com a sessão
        bloqueada quando o aplicativo alvo aceita mensagens de mouse em background."""
        if not win32gui:
            raise RuntimeError("pywin32 não está instalado.")
        cx,cy,root_hwnd=self._client_point(pos)
        target_hwnd=self._find_window_at_client_point(root_hwnd,cx,cy)
        # Se o ponto estiver em um popup/menu, converte novamente para o cliente dele.
        if target_hwnd != root_hwnd:
            sx,sy=win32gui.ClientToScreen(root_hwnd,(cx,cy))
            cx2,cy2=win32gui.ScreenToClient(target_hwnd,(sx,sy))
        else:
            cx2,cy2=cx,cy
        lparam=(int(cy2) << 16) | (int(cx2) & 0xFFFF)
        if label:
            self.root.after(0,lambda:self.status_lbl.config(text=f"🖥️ CLIQUE EM BACKGROUND → {label}"))
        user32=ctypes.windll.user32
        # WM_MOUSEMOVE + botão esquerdo. PostMessage não exige foreground nem cursor físico.
        user32.PostMessageW(target_hwnd,0x0200,0,lparam)  # WM_MOUSEMOVE
        user32.PostMessageW(target_hwnd,0x0201,1,lparam)  # WM_LBUTTONDOWN
        time.sleep(0.05)
        user32.PostMessageW(target_hwnd,0x0202,0,lparam)  # WM_LBUTTONUP
        return True

    def click_pos(self,pos, label=None):
        if not pos:
            raise RuntimeError("Posição de clique inválida.")
        if label:
            self.root.after(0,lambda:self.status_lbl.config(text=f"🖱️ MOVENDO CURSOR → {label}"))
        # Sempre traz a janela alvo para frente imediatamente antes de calcular a posição.
        self.focus_target()
        x,y=self._screen_pos(pos)
        self.root.after(0,lambda x=x,y=y,l=label:self.status_lbl.config(text=f"🖱️ CURSOR → {l or 'POSIÇÃO'}  ({x},{y})"))
        pyautogui.moveTo(x,y,duration=1.0,_pause=False)
        time.sleep(.25)
        cur=pyautogui.position()
        if abs(cur.x-x)>3 or abs(cur.y-y)>3:
            raise RuntimeError(f"O cursor não chegou à posição de {label or 'clique'} (esperado {x},{y}; atual {cur.x},{cur.y}).")
        pyautogui.click(_pause=False)

    def execute_pause(self,category):
        """Fluxo V2:
        1) ativa a janela;
        2) clica UMA vez em PAUSAR;
        3) espera o menu abrir;
        4) clica UMA vez na opção escolhida.
        """
        if not config.get("pause_button"):
            raise RuntimeError("Botão PAUSAR não está configurado.")
        if category not in config.get("categories",{}) or not config["categories"].get(category):
            raise RuntimeError(f'Categoria "{category}" não está configurada.')
        with self.action_lock:
            self.focus_target()
            self.root.after(0,lambda:self.status_lbl.config(text=f"PAUSAR → abrindo menu: {category}"))
            self.click_pos(config["pause_button"], "PAUSAR")       # EXATAMENTE 1 clique
            time.sleep(self.menu_wait_seconds)            # aguarda o menu
            self.root.after(0,lambda:self.status_lbl.config(text=f"MENU ABERTO → {category}"))
            self.click_pos(config["categories"][category], category.upper()) # EXATAMENTE 1 clique
            self.root.after(0,lambda:self.status_lbl.config(text=f"PAUSA ATIVA: {category}"))

    def execute_unpause(self):
        """Despausa com um único clique, sem abrir menu."""
        if not config.get("unpause_button"):
            raise RuntimeError("Botão DESPAUSAR não está configurado.")
        with self.action_lock:
            self.focus_target()
            self.root.after(0,lambda:self.status_lbl.config(text="DESPAUSAR → 1 clique"))
            self.click_pos(config["unpause_button"], "DESPAUSAR")      # EXATAMENTE 1 clique
            self.root.after(0,lambda:self.status_lbl.config(text="DESPAUSADO"))

    def test_pause(self):
        cat=self.cat_combo.get()
        if not config.get("pause_button") or not config["categories"].get(cat):
            messagebox.showerror("Teste","Configure PAUSAR e a categoria primeiro.")
            return
        try: self.execute_pause(cat)
        except Exception as e: messagebox.showerror("Teste",str(e))

    def test_unpause(self):
        if not config.get("unpause_button"):
            messagebox.showerror("Teste","Defina DESPAUSAR primeiro.")
            return
        try: self.execute_unpause()
        except Exception as e: messagebox.showerror("Teste",str(e))

    def start_scheduler(self):
        if self.running:
            return
        if not config.get("schedules"):
            return
        if not config.get("target_window"):
            raise RuntimeError("Selecione e salve a janela alvo antes de agendar.")
        self.running=True
        self.start_btn.config(text="■ PARAR AUTOMAÇÃO")
        self.status_lbl.config(text="🟢 AGENDAMENTO ATIVO • sincronizado com o relógio do Windows")
        self.header_status.config(text="● ATIVO")
        threading.Thread(target=self.scheduler_loop,daemon=True).start()

    def toggle_running(self):
        if self.running:
            self.running=False
            self.start_btn.config(text="▶ INICIAR AUTOMAÇÃO")
            self.status_lbl.config(text="● PARADO")
            self.header_status.config(text="● PARADO")
        else:
            if not config["schedules"]:
                messagebox.showwarning("Automação","Adicione pelo menos um horário.")
                return
            if not config.get("target_window"):
                messagebox.showwarning("Automação","Selecione e salve a janela alvo.")
                return
            self.start_scheduler()

    def run_scheduled_job(self, schedule, target):
        """Executa um agendamento em sua própria thread.

        O agendador principal nunca fica bloqueado durante a duração da pausa.
        Assim, vários horários podem ser cadastrados e cada um será disparado
        quando chegar sua vez. O action_lock serializa as ações físicas do
        mouse para evitar dois cliques simultâneos.
        """
        category = schedule.get("category", "")
        duration = int(schedule.get("duration", 0))
        t = schedule.get("time", "")
        try:
            self.root.after(0, lambda t=t, c=category: self.status_lbl.config(
                text=f"🔔 HORÁRIO ATINGIDO! {t} → {c.upper()}"))
            self.root.after(0, lambda: self.header_status.config(text="● EXECUTANDO"))

            # Se outra execução estiver usando o mouse, esta espera sua vez.
            self.root.after(0, lambda c=category: self.status_lbl.config(
                text=f"⏳ FILA DE EXECUÇÃO • {c.upper()}"))
            with self.action_lock:
                if not self.running:
                    return

                self.root.after(0, lambda c=category: self.status_lbl.config(
                    text=f"▶ EXECUTANDO EM BACKGROUND • {c.upper()}"))
                # Fluxo obrigatório: PAUSAR -> aguardar menu -> CATEGORIA.
                self._execute_pause_no_lock(category, background=True)

                end_time = datetime.now() + timedelta(minutes=duration)
                while self.running and datetime.now() < end_time:
                    remaining_sec = max(0, int((end_time - datetime.now()).total_seconds()))
                    self.root.after(0, lambda r=remaining_sec, c=category:
                        self.status_lbl.config(
                            text=f"🟢 PAUSA ATIVA • {c.upper()} • falta {r//60:02d}:{r%60:02d}"))
                    time.sleep(0.25)

                if self.running:
                    self.root.after(0, lambda: self.status_lbl.config(
                        text="🔄 DURAÇÃO ENCERRADA • DESPAUSANDO..."))
                    self._execute_unpause_no_lock(background=True)
                    self.root.after(0, lambda t=t, c=category:
                        self.status_lbl.config(text=f"✓ AGENDAMENTO EXECUTADO • {t} • {c.upper()}"))
                    self.root.after(0, lambda: self.header_status.config(text="● AGENDADO"))
        except Exception as e:
            self.root.after(0, lambda err=str(e): messagebox.showerror(
                "N2 • Erro na automação", err))
            self.root.after(0, lambda: self.status_lbl.config(text="✕ ERRO NA AUTOMAÇÃO"))
            self.root.after(0, lambda: self.header_status.config(text="● ERRO"))

    def _execute_pause_no_lock(self, category, background=False):
        """Executa PAUSAR + categoria. O lock é controlado pelo chamador."""
        if not config.get("pause_button"):
            raise RuntimeError("Botão PAUSAR não está configurado.")
        if category not in config.get("categories", {}) or not config["categories"].get(category):
            raise RuntimeError(f'Categoria "{category}" não está configurada.')

        if background:
            self.root.after(0, lambda c=category: self.status_lbl.config(text=f"🖥️ BACKGROUND → PAUSAR • {c.upper()}"))
            self.background_click(config["pause_button"], "PAUSAR")
        else:
            self.focus_target()
            self.root.after(0, lambda c=category: self.status_lbl.config(text=f"🖱️ CURSOR → PAUSAR • {c.upper()}"))
            self.click_pos(config["pause_button"], "PAUSAR")       # 1 clique
        time.sleep(self.menu_wait_seconds)
        self.root.after(0, lambda c=category: self.status_lbl.config(text=f"📂 MENU ABERTO → {c.upper()}"))
        if background:
            self.background_click(config["categories"][category], category.upper())  # 1 clique
        else:
            self.click_pos(config["categories"][category], category.upper())  # 1 clique
        self.root.after(0, lambda c=category: self.status_lbl.config(
            text=f"🟢 PAUSA ATIVA • {c.upper()}"))

    def _execute_unpause_no_lock(self, background=False):
        """Executa DESPAUSAR. O lock é controlado pelo chamador."""
        if not config.get("unpause_button"):
            raise RuntimeError("Botão DESPAUSAR não está configurado.")
        if background:
            self.root.after(0, lambda: self.status_lbl.config(text="🖥️ BACKGROUND → DESPAUSAR"))
            self.background_click(config["unpause_button"], "DESPAUSAR")  # 1 clique
        else:
            self.focus_target()
            self.root.after(0, lambda: self.status_lbl.config(text="🖱️ CURSOR → DESPAUSAR"))
            self.click_pos(config["unpause_button"], "DESPAUSAR")  # 1 clique
        self.root.after(0, lambda: self.status_lbl.config(text="✓ DESPAUSADO"))

    def scheduler_loop(self):
        """Monitora todos os horários sem ficar preso na duração de uma pausa."""
        executed = set()
        jobs = {}

        while self.running:
            try:
                now = datetime.now()
                today = now.date()
                schedules = list(config.get("schedules", []))
                upcoming = []

                for idx, s in enumerate(schedules):
                    try:
                        hh, mm = map(int, str(s["time"]).split(":"))
                        target = datetime.combine(today, datetime.min.time()).replace(
                            hour=hh, minute=mm, second=0, microsecond=0)
                        if target < now:
                            target += timedelta(days=1)

                        # Identificador estável o suficiente para não repetir o mesmo
                        # horário no mesmo dia, mesmo enquanto outra execução está ativa.
                        key = f"{target.strftime('%Y-%m-%d')}|{idx}|{s['time']}|{s.get('category','')}|{s.get('duration',0)}"
                        remaining = (target - now).total_seconds()
                        upcoming.append((remaining, target, s, key))

                        # Dispara com tolerância, mas somente para horários que realmente
                        # acabaram de chegar. O target do dia seguinte nunca dispara agora.
                        if 0 <= remaining <= 0.60 and key not in executed:
                            executed.add(key)
                            job = threading.Thread(
                                target=self.run_scheduled_job,
                                args=(dict(s), target),
                                daemon=True,
                            )
                            jobs[key] = job
                            job.start()
                    except Exception:
                        continue

                if upcoming:
                    remaining, target, s, key = min(upcoming, key=lambda x: x[0])
                    # Quando o próximo horário é hoje e está chegando, mostra a contagem.
                    if remaining >= 0:
                        mins = max(0, int(remaining) // 60)
                        secs = max(0, int(remaining) % 60)
                        self.root.after(0, lambda sn=s, m=mins, se=secs:
                            self.status_lbl.config(
                                text=f"🟢 AGUARDANDO • {sn['time']} • {sn['category'].upper()} • falta {m:02d}:{se:02d}"))

                # Limpa jobs finalizados para não crescer indefinidamente.
                jobs = {k: v for k, v in jobs.items() if v.is_alive()}
                time.sleep(0.10)
            except Exception as e:
                self.root.after(0, lambda err=str(e): messagebox.showerror(
                    "N2 • Erro no agendador", err))
                time.sleep(1)

    def close(self):
        self.running=False
        self.root.destroy()

if __name__=="__main__":
    root=tk.Tk()
    App(root)
    root.mainloop()
