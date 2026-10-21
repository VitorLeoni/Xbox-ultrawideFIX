"""
Xbox Stretch - remove as barras pretas da transmissão do app Xbox no Windows.

Como funciona:
  1. Você escolhe a janela.
  2. Ao clicar em Iniciar, o app cria uma janela sobreposta (overlay) em tela cheia
     e pede ao DWM para desenhar nela uma janela do Xbox, recortando só a área 16:9 e esticando para preencher tudo.
  3. Pausar remove o overlay e volta ao normal.

Atalho global: Ctrl + Alt + X  (inicia / pausa)

Requisitos: Windows 10/11 e Python 3.8+.
"""
import ctypes
import threading
import tkinter as tk
from ctypes import wintypes as wt
from tkinter import ttk

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
dwm = ctypes.windll.dwmapi

class RECT(ctypes.Structure):
    _fields_ = [("left", wt.LONG), ("top", wt.LONG), ("right", wt.LONG), ("bottom", wt.LONG)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", wt.LONG), ("cy", wt.LONG)]


class DWM_THUMBNAIL_PROPERTIES(ctypes.Structure):
    _fields_ = [
        ("dwFlags", wt.DWORD),
        ("rcDestination", RECT),
        ("rcSource", RECT),
        ("opacity", ctypes.c_ubyte),
        ("fVisible", wt.BOOL),
        ("fSourceClientAreaOnly", wt.BOOL),
    ]


DWM_TNP_RECTDESTINATION = 0x1
DWM_TNP_RECTSOURCE = 0x2
DWM_TNP_OPACITY = 0x4
DWM_TNP_VISIBLE = 0x8
DWM_TNP_SOURCECLIENTAREAONLY = 0x10

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x20
WS_EX_TOOLWINDOW = 0x80
WS_EX_LAYERED = 0x80000
WS_EX_NOACTIVATE = 0x08000000
LWA_ALPHA = 0x2
GA_ROOT = 2
WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x1, 0x2, 0x4000

CONTENT_ASPECT = 16 / 9  # proporção do vídeo da transmissão


user32.GetWindowTextW.argtypes = [ctypes.c_void_p, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
user32.IsWindow.argtypes = [ctypes.c_void_p]
user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT)]
user32.GetAncestor.argtypes = [ctypes.c_void_p, wt.UINT]
user32.GetAncestor.restype = ctypes.c_void_p
user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetLayeredWindowAttributes.argtypes = [ctypes.c_void_p, wt.DWORD, ctypes.c_ubyte, wt.DWORD]
user32.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, wt.UINT, wt.UINT]

dwm.DwmRegisterThumbnail.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
dwm.DwmUnregisterThumbnail.argtypes = [ctypes.c_void_p]
dwm.DwmUpdateThumbnailProperties.argtypes = [ctypes.c_void_p, ctypes.POINTER(DWM_THUMBNAIL_PROPERTIES)]
dwm.DwmQueryThumbnailSourceSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(SIZE)]
dwm.DwmGetWindowAttribute.argtypes = [ctypes.c_void_p, wt.DWORD, ctypes.c_void_p, wt.DWORD]

EnumProc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)


kernel32 = ctypes.windll.kernel32
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype = ctypes.c_void_p
kernel32.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.DWORD)]
user32.GetClassNameW.argtypes = [ctypes.c_void_p, wt.LPWSTR, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
user32.GetForegroundWindow.restype = ctypes.c_void_p
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]


def proc_name(hwnd):
    """Nome do .exe dono da janela (vazio se não for possível ler)."""
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)  
    if not h:
        return ""
    buf = ctypes.create_unicode_buffer(520)
    n = wt.DWORD(520)
    ok = kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
    kernel32.CloseHandle(h)
    return buf.value.rsplit("\\", 1)[-1] if ok else ""


def list_windows(show_all=False):
    """Retorna [(hwnd, titulo, processo)].

    Modo normal: só janelas visíveis.
    show_all: inclui janelas sem título, ocultas pelo UWP (minimizadas / outra
    área de trabalho virtual) e mostra a classe da janela quando não há título.
    """
    found = []
    xbox_keys = ("xbox", "gamingapp", "gamebar")

    def cb(hwnd, _):
        pname = None
        is_xbox = False
        if not show_all:
            cloaked = ctypes.c_int(0)
            dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4)  
            if not user32.IsWindowVisible(hwnd) or cloaked.value:
                # janela oculta/suspensa: só entra se for de um processo do Xbox
                pname = proc_name(hwnd)
                is_xbox = any(k in pname.lower() for k in xbox_keys)
                if not is_xbox:
                    return 1
        n = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            title = buf.value
        if not title:
            if not (show_all or is_xbox):
                return 1
            cbuf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cbuf, 256)
            title = f"(sem título) <{cbuf.value}>"
        if pname is None:
            pname = proc_name(hwnd)
        found.append((hwnd, title, pname))
        return 1

    user32.EnumWindows(EnumProc(cb), 0)
    return found


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Xbox Stretch")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)

        self.windows = []
        self.active = False
        self.overlay = None
        self.thumb = None
        self.src_hwnd = None
        self.hotkey_flag = False

        pad = {"padx": 10, "pady": 5}
        ttk.Label(self.root, text="Janela alvo (hook):").grid(row=0, column=0, sticky="w", **pad)
        self.combo = ttk.Combobox(self.root, state="readonly", width=70)
        self.combo.grid(row=1, column=0, columnspan=2, sticky="we", **pad)
        ttk.Button(self.root, text="Atualizar lista", command=self.refresh).grid(row=0, column=1, sticky="e", **pad)

        self.btn = ttk.Button(self.root, text="▶ Iniciar", command=self.toggle)
        self.btn.grid(row=4, column=0, columnspan=2, sticky="we", padx=10, pady=8, ipady=8)

        self.status = ttk.Label(self.root, text="Parado  |  Atalho: Ctrl+Alt+X")
        self.status.grid(row=5, column=0, columnspan=2, sticky="w", **pad)

        self.all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.root, text="Mostrar todas as janelas (inclui sem título / ocultas)",
                        variable=self.all_var, command=self.refresh).grid(row=6, column=0, columnspan=2, sticky="w", **pad)

        self.refresh()
        threading.Thread(target=self.hotkey_loop, daemon=True).start()
        self.root.after(300, self.tick)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    # ---- lista de janelas
    def refresh(self):
        self.windows = [w for w in list_windows(self.all_var.get()) if w[1] != "Xbox Stretch"]
        # Ordem: "Xbox" + ApplicationFrameHost.exe primeiro, depois outras janelas do Xbox
        def prioridade(w):
            titulo, proc = w[1].strip().lower(), w[2].lower()
            if titulo == "xbox" and proc == "applicationframehost.exe":
                return 0
            if titulo == "xbox":
                return 1
            if "xbox" in titulo or "xbox" in proc:
                return 2
            return 3

        self.windows.sort(key=prioridade)
        titles = [f"{t}  —  {p or '?'}  [{h}]" for h, t, p in self.windows]
        self.combo["values"] = titles
        self.combo.set("")
        if self.windows and ("xbox" in self.windows[0][1].lower() or "xbox" in self.windows[0][2].lower()):
            self.combo.current(0)
            self.status.config(text="Janela do Xbox encontrada.  |  Atalho: Ctrl+Alt+X")
        else:
            self.status.config(text="Xbox não encontrado. Abra a transmissão, ou marque 'Mostrar todas'.")

    # ---- atalho
    def hotkey_loop(self):
        if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord("X")):
            return
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY:
                self.hotkey_flag = True

    # ---- foco
    def focus_src(self):
        """Devolve o foco para a janela do Xbox (senão ele pausa os comandos)."""
        if not (self.src_hwnd and user32.IsWindow(self.src_hwnd)):
            return
        try:
            fg = user32.GetForegroundWindow()
            t_fg = user32.GetWindowThreadProcessId(fg, None) if fg else 0
            t_me = kernel32.GetCurrentThreadId()
            if t_fg and t_fg != t_me:
                user32.AttachThreadInput(t_me, t_fg, True)
            user32.SetForegroundWindow(self.src_hwnd)
            if t_fg and t_fg != t_me:
                user32.AttachThreadInput(t_me, t_fg, False)
        except Exception:
            pass

    def set_noactivate(self, on):
        """Com o esticado ligado, clicar nesta janela não rouba o foco do Xbox."""
        h = user32.GetAncestor(self.root.winfo_id(), GA_ROOT) or self.root.winfo_id()
        ex = user32.GetWindowLongPtrW(h, GWL_EXSTYLE)
        ex = (ex | WS_EX_NOACTIVATE) if on else (ex & ~WS_EX_NOACTIVATE)
        user32.SetWindowLongPtrW(h, GWL_EXSTYLE, ex)

    # ---- iniciar / pausar
    def toggle(self):
        if self.active:
            self.stop()
        else:
            self.start()

    def start(self):
        idx = self.combo.current()
        if idx < 0:
            self.status.config(text="Selecione a janela do app Xbox primeiro.")
            return
        self.src_hwnd = self.windows[idx][0]
        if not user32.IsWindow(self.src_hwnd):
            self.status.config(text="Janela não existe mais. Clique em Atualizar lista.")
            return

        r = RECT()
        user32.GetWindowRect(self.src_hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top

        ov = tk.Toplevel(self.root)
        ov.overrideredirect(True)
        ov.configure(bg="black")
        ov.geometry(f"{w}x{h}+{r.left}+{r.top}")
        ov.attributes("-topmost", True)
        ov.update_idletasks()

        hwnd = user32.GetAncestor(ov.winfo_id(), GA_ROOT) or ov.winfo_id()
        ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        ex |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex)
        user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)

        thumb = ctypes.c_void_p()
        hr = dwm.DwmRegisterThumbnail(hwnd, self.src_hwnd, ctypes.byref(thumb))
        if hr != 0:
            ov.destroy()
            self.status.config(text=f"Falha ao anexar (DWM erro {hr & 0xFFFFFFFF:#x}).")
            return

        self.overlay, self.overlay_hwnd, self.thumb = ov, hwnd, thumb
        self.ow, self.oh = w, h
        self.active = True
        self.update_thumb()
        self.root.lift()
        self.btn.config(text="⏸ Pausar")
        self.status.config(text="Esticando  |  Atalho: Ctrl+Alt+X")
        self.set_noactivate(True)
        self.root.after(150, self.focus_src)

    def stop(self):
        if self.thumb:
            dwm.DwmUnregisterThumbnail(self.thumb)
            self.thumb = None
        if self.overlay:
            self.overlay.destroy()
            self.overlay = None
        self.active = False
        self.set_noactivate(False)
        self.btn.config(text="▶ Iniciar")
        self.status.config(text="Parado  |  Atalho: Ctrl+Alt+X")

    # ---- recorte
    def update_thumb(self):
        if not (self.active and self.thumb):
            return
        size = SIZE()
        if dwm.DwmQueryThumbnailSourceSize(self.thumb, ctypes.byref(size)) != 0:
            return
        sw, sh = size.cx, size.cy
        cw = min(sw, int(sh * CONTENT_ASPECT))  # recorta as barras pretas (conteúdo 16:9)
        left = (sw - cw) // 2

        p = DWM_THUMBNAIL_PROPERTIES()
        p.dwFlags = (DWM_TNP_RECTDESTINATION | DWM_TNP_RECTSOURCE | DWM_TNP_OPACITY |
                     DWM_TNP_VISIBLE | DWM_TNP_SOURCECLIENTAREAONLY)
        p.rcDestination = RECT(0, 0, self.ow, self.oh)
        p.rcSource = RECT(left, 0, left + cw, sh)
        p.opacity = 255
        p.fVisible = True
        p.fSourceClientAreaOnly = True
        dwm.DwmUpdateThumbnailProperties(self.thumb, ctypes.byref(p))

    
    def tick(self):
        if self.hotkey_flag:
            self.hotkey_flag = False
            self.toggle()
        if self.active:
            if not user32.IsWindow(self.src_hwnd):
                self.stop()
                self.status.config(text="Janela do Xbox fechou. Parado.")
            else:
                self.update_thumb()
        self.root.after(500, self.tick)

    def quit(self):
        self.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
