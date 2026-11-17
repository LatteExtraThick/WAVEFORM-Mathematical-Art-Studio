"""WAVEFORM — draw freely, then represent every stroke mathematically."""
import json
import math
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser, ttk
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageTk

from waveform.art_engine import simplify_rdp, points_to_beziers, sample_bezier, validate_art_code

BG = "#08070D"
PANEL = "#11101A"
PANEL_ALT = "#21182F"
TEXT = "#F7F2FF"
MUTED = "#A99BBF"
ACCENT = "#A855F7"
PAPER = "#FBF9FF"


def resource_path(relative_path):
    """Resolve bundled assets in both development and PyInstaller builds."""
    base_path = getattr(sys, "_MEIPASS", str(Path(__file__).resolve().parent))
    return str(Path(base_path) / relative_path)



class ScrollablePanel(tk.Frame):
    """A themed panel with reliable wheel scrolling over every child control."""
    def __init__(self, parent, bg=PANEL, scrollbar_bg=PANEL):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.scrollbar = tk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview,
            bg=scrollbar_bg, troughcolor=bg, activebackground="#C084FC",
            relief="flat", bd=0, width=11
        )
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._update_region)
        self.canvas.bind("<Configure>", self._resize_inner)

        # The wheel must work while the pointer is over buttons, labels, scales,
        # text boxes, or empty space—not only over the canvas itself.
        self.bind("<Enter>", self._bind_wheel, add="+")
        self.bind("<Leave>", self._leave_panel, add="+")
        self.canvas.bind("<Enter>", self._bind_wheel, add="+")
        self.inner.bind("<Enter>", self._bind_wheel, add="+")

    def enable_wheel_scrolling(self):
        """Attach enter/leave handling to all existing descendants."""
        def visit(widget):
            widget.bind("<Enter>", self._bind_wheel, add="+")
            widget.bind("<Leave>", self._leave_panel, add="+")
            for child in widget.winfo_children():
                visit(child)
        visit(self.inner)
        visit(self.canvas)
        visit(self.scrollbar)

    def _is_inside_panel(self, widget):
        while widget is not None:
            if widget == self:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _update_region(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_inner(self, event):
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _bind_wheel(self, _event=None):
        self.bind_all("<MouseWheel>", self._mousewheel, add="+")
        self.bind_all("<Button-4>", self._linux_up, add="+")
        self.bind_all("<Button-5>", self._linux_down, add="+")

    def _leave_panel(self, event=None):
        if event is not None:
            under_pointer = self.winfo_containing(event.x_root, event.y_root)
            if self._is_inside_panel(under_pointer):
                return
        self.unbind_all("<MouseWheel>")
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")

    def _mousewheel(self, event):
        delta = getattr(event, "delta", 0)
        units = int(-delta / 120)
        if units == 0 and delta:
            units = -1 if delta > 0 else 1
        self.canvas.yview_scroll(units, "units")
        return "break"

    def _linux_up(self, _event):
        self.canvas.yview_scroll(-1, "units")
        return "break"

    def _linux_down(self, _event):
        self.canvas.yview_scroll(1, "units")
        return "break"


class WaveformApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WAVEFORM Studio | Black + Purple Edition")
        self.geometry("1360x860")
        self.minsize(980, 650)
        self.configure(bg=BG)
        self._app_icon = None
        self._brand_logo = None
        try:
            icon_image = Image.open(resource_path("assets/waveform_logo.png")).convert("RGBA")
            self._app_icon = ImageTk.PhotoImage(icon_image.resize((64, 64), Image.Resampling.LANCZOS))
            self.iconphoto(True, self._app_icon)
        except Exception:
            pass

        self.strokes = []
        self.converted_strokes = []
        self.generated_art = []
        self.current_points = []
        self.undo_stack = []
        self.redo_stack = []
        self.current_project_path = None
        self.current_project_name = "Untitled project"
        self.current_color = "#25283B"
        self.brush_width = tk.IntVar(value=4)
        self.tool = tk.StringVar(value="Pencil")
        self.view_mode = tk.StringVar(value="Original")
        self._configure_style()
        self._build_ui()

    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Wave.TCombobox", fieldbackground=PANEL_ALT,
                        background=PANEL_ALT, foreground=TEXT,
                        arrowcolor=TEXT, borderwidth=0, padding=7)
        style.map("Wave.TCombobox",
                  fieldbackground=[("readonly", PANEL_ALT)],
                  foreground=[("readonly", TEXT)])
        style.configure("Wave.Vertical.TScrollbar",
                        background=PANEL_ALT, troughcolor=PANEL,
                        bordercolor=PANEL, arrowcolor=MUTED)

    def button(self, parent, text, command, primary=False, compact=False):
        normal_bg = ACCENT if primary else PANEL_ALT
        normal_fg = "#100817" if primary else TEXT
        hover_bg = "#C084FC" if primary else "#332044"
        btn = tk.Button(
            parent, text=text, command=command,
            bg=normal_bg, fg=normal_fg,
            activebackground=hover_bg, activeforeground="#FFFFFF",
            relief="flat", bd=0,
            padx=12 if compact else 14,
            pady=8 if compact else 10,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2", anchor="w",
            highlightthickness=1,
            highlightbackground="#38234F",
            highlightcolor=ACCENT
        )
        btn.bind("<Enter>", lambda _e: btn.configure(bg=hover_bg), add="+")
        btn.bind("<Leave>", lambda _e: btn.configure(bg=normal_bg), add="+")
        return btn

    def _section(self, parent, title, hint=None):
        wrap = tk.Frame(parent, bg=PANEL)
        wrap.pack(fill="x", padx=12, pady=(15, 4))
        tk.Label(wrap, text=title.upper(), bg=PANEL, fg="#D8B4FE",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        if hint:
            tk.Label(wrap, text=hint, bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 8), wraplength=190,
                     justify="left").pack(anchor="w", pady=(3, 0))
        return wrap

    def _tool_choice(self, parent, label, value):
        rb = tk.Radiobutton(
            parent, text=label, variable=self.tool, value=value,
            command=self._tool_changed, bg=PANEL_ALT, fg=TEXT,
            selectcolor="#3B1D54", activebackground=PANEL_ALT,
            activeforeground=TEXT, font=("Segoe UI", 9),
            padx=10, pady=7, indicatoron=False, relief="flat",
        )
        rb.pack(side="left", expand=True, fill="x", padx=(0, 5))
        return rb

    def _build_ui(self):
        self.geometry("1440x900")
        self.minsize(1100, 700)

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=22, pady=(16, 13))
        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left")
        try:
            logo_image = Image.open(resource_path("assets/waveform_logo.png")).convert("RGBA")
            logo_image.thumbnail((42, 42), Image.Resampling.LANCZOS)
            self._brand_logo = ImageTk.PhotoImage(logo_image)
            tk.Label(brand, image=self._brand_logo, bg=BG).pack(side="left", padx=(0, 10))
        except Exception:
            pass
        tk.Label(brand, text="WAVEFORM", bg=BG, fg=TEXT,
                 font=("Segoe UI", 22, "bold")).pack(side="left")
        tk.Label(brand, text="✦ STUDIO", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(8, 0), pady=(8, 0))
        tk.Label(header, text="A CREATIVE SPACE FOR MATHEMATICAL ART",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(20, 0), pady=(8, 0))
        tk.Label(header, text="●  DRAW     ●  CONVERT     ●  CREATE",
                 bg=BG, fg="#9B7AB8", font=("Segoe UI", 8, "bold")).pack(side="right", pady=(8, 0))
        project_actions = tk.Frame(header, bg=BG)
        project_actions.pack(side="right", padx=(0, 18))
        self.button(project_actions, "▣  Open project", self.open_project, compact=True).pack(side="left", padx=(0, 6))
        self.button(project_actions, "✦  Save project", self.save_project, primary=True, compact=True).pack(side="left")

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        # Left: grouped tools with plain-language actions.
        tools = tk.Frame(body, bg=PANEL, width=224,
                         highlightthickness=1, highlightbackground="#292D42")
        tools.pack(side="left", fill="y", padx=(0, 11))
        tools.pack_propagate(False)
        tools_scroll = ScrollablePanel(tools)
        tools_scroll.pack(fill="both", expand=True)
        content = tools_scroll.inner

        tk.Label(content, text="WORKSPACE", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(16, 2))
        tk.Label(content, text="Create and share mathematical artwork.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8),
                 wraplength=190, justify="left").pack(anchor="w", padx=14, pady=(0, 7))

        self._section(content, "✎  1 · DRAW", "Choose a tool, colour and stroke size.")
        tool_row = tk.Frame(content, bg=PANEL)
        tool_row.pack(fill="x", padx=12, pady=(5, 2))
        self._tool_choice(tool_row, "✎  Pencil", "Pencil")
        self._tool_choice(tool_row, "▱  Eraser", "Eraser")

        tk.Label(content, text="STROKE SIZE", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(10, 2))
        tk.Scale(content, from_=1, to=20, orient="horizontal",
                 variable=self.brush_width, bg=PANEL, fg=TEXT,
                 troughcolor=PANEL_ALT, activebackground=ACCENT,
                 highlightthickness=0, bd=0, showvalue=True,
                 font=("Segoe UI", 8)).pack(fill="x", padx=8)

        colour_row = tk.Frame(content, bg=PANEL)
        colour_row.pack(fill="x", padx=13, pady=(4, 2))
        self.color_swatch = tk.Label(colour_row, text="  ", bg=self.current_color,
                                     relief="flat", width=3)
        self.color_swatch.pack(side="left", padx=(0, 8), ipady=5)
        self.button(colour_row, "◉  Choose colour", self.choose_color, compact=True).pack(side="left", fill="x", expand=True)

        self._section(content, "⟲  2 · EDIT", "Changes can be undone or redone.")
        edit_row = tk.Frame(content, bg=PANEL)
        edit_row.pack(fill="x", padx=12, pady=(5, 2))
        self.button(edit_row, "↶  Undo", self.undo, compact=True).pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.button(edit_row, "↷  Redo", self.redo, compact=True).pack(side="left", fill="x", expand=True)
        self.button(content, "⌫  Clear canvas", self.clear_canvas, compact=True).pack(fill="x", padx=12, pady=(4, 2))

        self._section(content, "⌁  3 · CONVERT", "Turn your freehand strokes into connected cubic Bézier functions.")
        self.button(content, "ƒ  Convert drawing to maths  →", self.convert_drawing,
                    primary=True).pack(fill="x", padx=12, pady=(5, 3))

        self._section(content, "∿  4 · MATHEMATICAL CREATOR",
                      "Generate waves and geometric forms directly from equations.")
        self.button(content, "∿  Create mathematical wave", self.open_wave_creator,
                    primary=True, compact=True).pack(fill="x", padx=12, pady=(5, 2))
        self.button(content, "◇  Create mathematical shape", self.open_shape_creator,
                    compact=True).pack(fill="x", padx=12, pady=2)
        self.button(content, "▰  Fill / colour settings", self.open_style_creator,
                    compact=True).pack(fill="x", padx=12, pady=(2, 5))

        self._section(content, "◉  5 · VIEW", "Switch between the drawing and its mathematical reconstruction.")
        view_grid = tk.Frame(content, bg=PANEL)
        view_grid.pack(fill="x", padx=12, pady=(5, 3))
        for label, mode in (("Original", "Original"), ("Math curves", "Mathematical"), ("Overlay", "Overlay")):
            self.button(view_grid, label, lambda m=mode: self.set_view(m),
                        compact=True).pack(fill="x", pady=2)

        self._section(content, "▣  6 · MY PROJECTS", "Save a project to a folder and reopen it later with the original strokes ready to edit.")
        self.button(content, "▣  Save project to folder", self.save_project,
                    primary=True, compact=True).pack(fill="x", padx=12, pady=(5, 2))
        self.button(content, "▤  Open saved project", self.open_project,
                    compact=True).pack(fill="x", padx=12, pady=2)
        tk.Label(content, text="Project files use .wproj and keep both your original drawing and its converted curves.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8),
                 wraplength=190, justify="left").pack(anchor="w", padx=13, pady=(3, 7))

        self._section(content, "↗  7 · SHARE ARTWORK", "Use these options to send a drawing to another WAVEFORM installation.")
        self.button(content, "⧉  Copy artwork data", self.copy_wave_code,
                    primary=True, compact=True).pack(fill="x", padx=12, pady=(5, 2))
        self.button(content, "⇩  Paste artwork data", self.paste_wave_code,
                    compact=True).pack(fill="x", padx=12, pady=2)
        file_row = tk.Frame(content, bg=PANEL)
        file_row.pack(fill="x", padx=12, pady=(2, 2))
        self.button(file_row, "↙  Import .wave", self.import_wave, compact=True).pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.button(file_row, "↗  Export .wave", self.export_wave, compact=True).pack(side="left", fill="x", expand=True)

        self._section(content, "⇩  8 · EXPORT", "Equations are for reading or reports; PNG is an image.")
        self.button(content, "ƒ  Copy equations (for report)", self.copy_functions,
                    compact=True).pack(fill="x", padx=12, pady=(5, 2))
        self.button(content, "▤  Save equations as .txt", self.export_functions_txt,
                    compact=True).pack(fill="x", padx=12, pady=2)
        self.button(content, "▧  Export canvas as PNG", self.export_png,
                    compact=True).pack(fill="x", padx=12, pady=(2, 16))

        # Centre: uncluttered artboard.
        workspace = tk.Frame(body, bg=BG)
        workspace.pack(side="left", fill="both", expand=True)
        canvas_header = tk.Frame(workspace, bg=BG)
        canvas_header.pack(fill="x", pady=(2, 9))
        tk.Label(canvas_header, text="ARTBOARD", bg=BG, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self.status = tk.StringVar(value="Start drawing anywhere on the white artboard.")
        tk.Label(canvas_header, textvariable=self.status, bg=BG, fg=MUTED,
                 font=("Segoe UI", 8), anchor="e").pack(side="right")

        canvas_shell = tk.Frame(workspace, bg="#191122",
                                highlightthickness=1, highlightbackground="#5B2A82")
        canvas_shell.pack(fill="both", expand=True)
        canvas_top = tk.Frame(canvas_shell, bg="#191122")
        canvas_top.pack(fill="x", padx=13, pady=(9, 5))
        tk.Label(canvas_top, text="YOUR DRAWING", bg="#191122", fg="#D8B4FE",
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Label(canvas_top, text="Mouse / trackpad", bg="#191122", fg="#9B7AB8",
                 font=("Segoe UI", 8)).pack(side="right")
        self.canvas = tk.Canvas(canvas_shell, bg=PAPER, highlightthickness=0,
                                cursor="pencil")
        self.canvas.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.canvas.bind("<ButtonPress-1>", self.start_stroke)
        self.canvas.bind("<B1-Motion>", self.continue_stroke)
        self.canvas.bind("<ButtonRelease-1>", self.end_stroke)

        # Right: concise result summary and scrollable equation inspector.
        inspector = tk.Frame(body, bg=PANEL, width=310,
                             highlightthickness=1, highlightbackground="#292D42")
        inspector.pack(side="right", fill="y", padx=(11, 0))
        inspector.pack_propagate(False)
        inspector_scroll = ScrollablePanel(inspector)
        inspector_scroll.pack(fill="both", expand=True)
        inspect = inspector_scroll.inner

        tk.Label(inspect, text="RESULTS", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(17, 2))
        tk.Label(inspect, text="Your drawing, represented as mathematics.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8),
                 wraplength=270, justify="left").pack(anchor="w", padx=14, pady=(0, 12))

        self.stats = tk.StringVar(value="No conversion yet\nDraw something, then convert it.")
        stats_card = tk.Frame(inspect, bg=PANEL_ALT)
        stats_card.pack(fill="x", padx=12, pady=(0, 13))
        tk.Label(stats_card, text="CONVERSION SUMMARY", bg=PANEL_ALT, fg="#B9B2D8",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=11, pady=(9, 3))
        tk.Label(stats_card, textvariable=self.stats, bg=PANEL_ALT, fg=TEXT,
                 justify="left", anchor="w", padx=11, pady=0,
                 font=("Segoe UI", 9)).pack(fill="x", pady=(0, 10))

        tk.Label(inspect, text="MATHEMATICAL FUNCTIONS", bg=PANEL, fg="#D8B4FE",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=13, pady=(4, 6))
        tk.Label(inspect, text="These equations describe the curves. Copy them for a report; use artwork data to recreate the drawing.",
                 bg=PANEL, fg=MUTED, wraplength=270, justify="left",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=13, pady=(0, 8))
        formula_frame = tk.Frame(inspect, bg="#0D0A13")
        formula_frame.pack(fill="both", expand=True, padx=11, pady=(0, 14))
        formula_scroll = tk.Scrollbar(formula_frame, orient="vertical")
        self.formula_text = tk.Text(
            formula_frame, height=22, bg="#0D0A13", fg="#E9D5FF",
            insertbackground=TEXT, relief="flat", wrap="word",
            font=("Consolas", 8), padx=10, pady=10,
            yscrollcommand=formula_scroll.set
        )
        formula_scroll.configure(command=self.formula_text.yview)
        formula_scroll.pack(side="right", fill="y")
        self.formula_text.pack(side="left", fill="both", expand=True)
        self.formula_text.insert(
            "1.0",
            "Nothing here yet.\n\n"
            "1. Draw on the white artboard.\n"
            "2. Click Convert drawing to maths.\n"
            "3. Explore the generated functions here.\n\n"
            "Each curve is represented by cubic Bézier parametric equations, "
            "with 0 ≤ t ≤ 1 for each segment."
        )
        self.formula_text.configure(state="disabled")

        footer = tk.Frame(self, bg=BG)
        footer.pack(fill="x", padx=22, pady=(0, 9))
        tk.Label(footer, text="WAVEFORM  ·  PIECEWISE PARAMETRIC CURVE RECONSTRUCTION",
                 bg=BG, fg="#777D96", font=("Segoe UI", 8)).pack(side="left")
        tk.Label(footer, text="v4.8  ·  MATHEMATICAL CREATOR", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 8, "bold")).pack(side="right")

        tools_scroll.enable_wheel_scrolling()
        inspector_scroll.enable_wheel_scrolling()

        self.bind("<Control-s>", lambda _event: self.save_project())
        self.bind("<Control-o>", lambda _event: self.open_project())
        self.bind("<Control-z>", lambda _event: self.undo())
        self.bind("<Control-y>", lambda _event: self.redo())
        self._update_window_title()

    def _label(self, parent, text):
        tk.Label(parent, text=text, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(12, 4))

    def _tool_changed(self):
        self.canvas.configure(cursor="dotbox" if self.tool.get() == "Eraser" else "pencil")

    def choose_color(self):
        result = colorchooser.askcolor(color=self.current_color, title="Choose drawing colour")
        if result and result[1]:
            self.current_color = result[1]
            self.color_swatch.configure(bg=self.current_color)


    def _creator_dialog(self, title, size="430x470"):
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.configure(bg=BG)
        dialog.geometry(size)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        return dialog

    def _field(self, parent, label, default, row):
        tk.Label(parent, text=label, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).grid(row=row, column=0, sticky="w", padx=14, pady=7)
        entry = tk.Entry(parent, bg=PANEL_ALT, fg=TEXT, insertbackground=TEXT,
                         relief="flat", font=("Segoe UI", 10))
        entry.insert(0, str(default))
        entry.grid(row=row, column=1, sticky="ew", padx=14, pady=7, ipady=6)
        return entry

    def _add_generated(self, item):
        self._snapshot()
        self.generated_art.append(item)
        self.view_mode.set("Mathematical")
        self._redraw()
        self._show_functions()
        self.status.set(f"Created {item.get('label', 'mathematical artwork')}")

    def open_wave_creator(self):
        dialog = self._creator_dialog("Create a mathematical wave", "470x560")
        tk.Label(dialog, text="MATHEMATICAL WAVE GENERATOR", bg=BG, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=18, pady=(17, 4))
        tk.Label(dialog, text="Choose a function and tune its parameters.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(0, 12))
        panel = tk.Frame(dialog, bg=PANEL)
        panel.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        panel.columnconfigure(1, weight=1)
        tk.Label(panel, text="WAVE TYPE", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", padx=14, pady=8)
        kind = tk.StringVar(value="Sine")
        ttk.Combobox(panel, textvariable=kind, values=[
            "Sine", "Cosine", "Tangent", "Square", "Triangle", "Sawtooth"
        ], state="readonly", style="Wave.TCombobox").grid(row=0, column=1, sticky="ew", padx=14, pady=8)
        amp = self._field(panel, "AMPLITUDE (px)", 100, 1)
        freq = self._field(panel, "FREQUENCY", 1.5, 2)
        phase = self._field(panel, "PHASE (radians)", 0, 3)
        offset = self._field(panel, "VERTICAL OFFSET (px)", 0, 4)
        span = self._field(panel, "HORIZONTAL SPAN (px)", 520, 5)
        colour = tk.StringVar(value=self.current_color)
        tk.Label(panel, text="LINE COLOUR", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).grid(row=6, column=0, sticky="w", padx=14, pady=8)
        swatch = tk.Label(panel, text="      ", bg=colour.get())
        swatch.grid(row=6, column=1, sticky="w", padx=14)
        def choose():
            picked = colorchooser.askcolor(color=colour.get(), title="Wave colour")
            if picked and picked[1]:
                colour.set(picked[1]); swatch.configure(bg=picked[1])
        self.button(panel, "Choose", choose, compact=True).grid(row=6, column=1, sticky="e", padx=14)
        def create():
            try:
                values = [float(x.get()) for x in (amp, freq, phase, offset, span)]
                a, f, p, off, width = values
                if not all(math.isfinite(v) for v in values) or a <= 0 or f <= 0 or width < 80 or width > 2000:
                    raise ValueError
                cx, cy = self.canvas.winfo_width()/2, self.canvas.winfo_height()/2
                points = []
                for i in range(801):
                    u = i / 800
                    x = cx - width/2 + u*width
                    theta = 2*math.pi*f*u + p
                    name = kind.get()
                    if name == "Sine": yv = math.sin(theta)
                    elif name == "Cosine": yv = math.cos(theta)
                    elif name == "Tangent": yv = max(-3, min(3, math.tan(theta))) / 3
                    elif name == "Square": yv = 1 if math.sin(theta) >= 0 else -1
                    elif name == "Triangle": yv = 2/math.pi * math.asin(math.sin(theta))
                    else: yv = 2*((theta/(2*math.pi)) % 1)-1
                    points.append([x, cy - off - a*yv])
                item = {"type": "wave", "label": f"{kind.get()} wave",
                        "wave": kind.get(), "points": points, "color": colour.get(),
                        "width": 3, "equation": f"y = {a:g}·{kind.get().lower()}(2π·{f:g}·u + {p:g}) + {off:g}; 0 ≤ u ≤ 1"}
                self._add_generated(item)
                dialog.destroy()
            except Exception:
                messagebox.showerror("Invalid parameters", "Use valid numbers. Amplitude and frequency must be positive; span must be 80–2000 px.", parent=dialog)
        self.button(dialog, "Generate wave  →", create, primary=True).pack(fill="x", padx=16, pady=(0, 16))

    def open_shape_creator(self):
        dialog = self._creator_dialog("Create a mathematical shape", "470x570")
        tk.Label(dialog, text="GEOMETRIC SHAPE GENERATOR", bg=BG, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=18, pady=(17, 4))
        panel = tk.Frame(dialog, bg=PANEL)
        panel.pack(fill="both", expand=True, padx=16, pady=12)
        panel.columnconfigure(1, weight=1)
        tk.Label(panel, text="SHAPE", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", padx=14, pady=8)
        kind = tk.StringVar(value="Circle")
        ttk.Combobox(panel, textvariable=kind, values=[
            "Circle", "Ellipse", "Square", "Rectangle", "Triangle",
            "Pentagon", "Hexagon", "Star", "Spiral"
        ], state="readonly", style="Wave.TCombobox").grid(row=0, column=1, sticky="ew", padx=14, pady=8)
        w = self._field(panel, "WIDTH / DIAMETER (px)", 220, 1)
        h = self._field(panel, "HEIGHT (px)", 150, 2)
        sides = self._field(panel, "POLYGON SIDES (3–12)", 6, 3)
        fill_var = tk.StringVar(value="#C084FC")
        outline_var = tk.StringVar(value="#6B21A8")
        def color_row(label, var, row):
            tk.Label(panel, text=label, bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 8, "bold")).grid(row=row, column=0, sticky="w", padx=14, pady=8)
            sw = tk.Label(panel, text="      ", bg=var.get())
            sw.grid(row=row, column=1, sticky="w", padx=14)
            def pick():
                result = colorchooser.askcolor(color=var.get(), title=label.title())
                if result and result[1]:
                    var.set(result[1]); sw.configure(bg=result[1])
            self.button(panel, "Choose", pick, compact=True).grid(row=row, column=1, sticky="e", padx=14)
        color_row("FILL COLOUR", fill_var, 4)
        color_row("OUTLINE COLOUR", outline_var, 5)
        filled = tk.BooleanVar(value=True)
        tk.Checkbutton(panel, text="Enable colour fill", variable=filled, bg=PANEL,
                       fg=TEXT, selectcolor=PANEL_ALT, activebackground=PANEL,
                       activeforeground=TEXT).grid(row=6, column=0, columnspan=2, sticky="w", padx=14, pady=8)
        def create():
            try:
                width, height, n = float(w.get()), float(h.get()), int(sides.get())
                if not (20 <= width <= 1000 and 20 <= height <= 1000 and 3 <= n <= 12):
                    raise ValueError
                cx, cy = self.canvas.winfo_width()/2, self.canvas.winfo_height()/2
                name = kind.get()
                if name in ("Circle", "Ellipse", "Square", "Rectangle"):
                    ww = width if name in ("Ellipse", "Rectangle") else min(width, height)
                    hh = height if name in ("Ellipse", "Rectangle") else min(width, height)
                    points = [[cx + ww/2*math.cos(2*math.pi*i/240),
                               cy + hh/2*math.sin(2*math.pi*i/240)] for i in range(241)]
                    equation = "x = cx + a cos(t), y = cy + b sin(t), 0 ≤ t ≤ 2π"
                elif name == "Spiral":
                    points = []
                    for i in range(601):
                        t = i/600 * 6*math.pi
                        r = (i/600) * min(width, height)/2
                        points.append([cx+r*math.cos(t), cy+r*math.sin(t)])
                    equation = "r = a·t, x = cx + r cos(t), y = cy + r sin(t)"
                else:
                    count = 10 if name == "Star" else (3 if name == "Triangle" else n)
                    points = []
                    for i in range(count):
                        angle = -math.pi/2 + 2*math.pi*i/count
                        radius = min(width, height)/2
                        if name == "Star" and i % 2:
                            radius *= 0.42
                        points.append([cx+radius*math.cos(angle), cy+radius*math.sin(angle)])
                    points.append(points[0])
                    equation = f"Regular polygon vertices: (cx + r cos(2πk/{count}), cy + r sin(2πk/{count}))"
                item = {"type": "shape", "label": name, "shape": name, "points": points,
                        "fill": fill_var.get() if filled.get() else "",
                        "outline": outline_var.get(), "width": 3,
                        "equation": equation}
                self._add_generated(item)
                dialog.destroy()
            except Exception:
                messagebox.showerror("Invalid dimensions", "Enter valid dimensions (20–1000 px) and polygon sides (3–12).", parent=dialog)
        self.button(dialog, "Create shape  →", create, primary=True).pack(fill="x", padx=16, pady=(0, 16))

    def open_style_creator(self):
        if not self.generated_art:
            messagebox.showinfo("No generated artwork", "Create a mathematical shape first to use fill and colour settings.")
            return
        item = self.generated_art[-1]
        dialog = self._creator_dialog("Fill and colour settings", "420x330")
        tk.Label(dialog, text="STYLE SELECTED MATHEMATICAL ART", bg=BG, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=18, pady=(18, 12))
        fill_var = tk.StringVar(value=item.get("fill") or "#C084FC")
        outline_var = tk.StringVar(value=item.get("outline") or item.get("color") or "#6B21A8")
        enabled = tk.BooleanVar(value=bool(item.get("fill")))
        def choose(var, label):
            result = colorchooser.askcolor(color=var.get(), title=label)
            if result and result[1]: var.set(result[1])
        row = tk.Frame(dialog, bg=PANEL); row.pack(fill="x", padx=16, pady=6)
        self.button(row, "Choose fill colour", lambda: choose(fill_var, "Fill colour"), compact=True).pack(side="left")
        self.button(row, "Choose outline", lambda: choose(outline_var, "Outline colour"), compact=True).pack(side="left", padx=8)
        tk.Checkbutton(dialog, text="Enable colour fill", variable=enabled, bg=BG, fg=TEXT,
                       selectcolor=PANEL_ALT, activebackground=BG).pack(anchor="w", padx=20, pady=12)
        def apply():
            item["fill"] = fill_var.get() if enabled.get() else ""
            item["outline"] = outline_var.get()
            self._redraw(); dialog.destroy()
            self.status.set("Fill and outline styling updated")
        self.button(dialog, "Apply style", apply, primary=True).pack(fill="x", padx=16, pady=12)

    def _snapshot(self):
        self.undo_stack.append({
            "strokes": [dict(s, points=list(s["points"])) for s in self.strokes],
            "generated": [dict(a, points=list(a["points"])) for a in self.generated_art]
        })
        self.undo_stack = self.undo_stack[-30:]
        self.redo_stack.clear()

    def start_stroke(self, event):
        self._snapshot()
        self.current_points = [(event.x, event.y)]
        self._stroke_color = PAPER if self.tool.get() == "Eraser" else self.current_color
        self._stroke_width = max(8, self.brush_width.get() * 3) if self.tool.get() == "Eraser" else self.brush_width.get()

    def continue_stroke(self, event):
        if not self.current_points:
            return
        previous = self.current_points[-1]
        point = (event.x, event.y)
        self.current_points.append(point)
        self.canvas.create_line(*previous, *point, fill=self._stroke_color,
                                 width=self._stroke_width, capstyle=tk.ROUND,
                                 joinstyle=tk.ROUND, smooth=True)

    def end_stroke(self, event):
        if not self.current_points:
            return
        self.current_points.append((event.x, event.y))
        self.strokes.append({
            "points": self.current_points.copy(),
            "color": self._stroke_color,
            "width": self._stroke_width
        })
        self.current_points = []
        self.converted_strokes = []
        self.view_mode.set("Original")
        self.status.set(f"{len(self.strokes)} stroke(s) captured — ready for mathematical conversion")

    def _redraw(self):
        self.canvas.delete("all")
        if self.view_mode.get() in ("Original", "Overlay"):
            for stroke in self.strokes:
                pts = stroke.get("points", [])
                if len(pts) == 1:
                    x, y = pts[0]
                    r = stroke["width"] / 2
                    self.canvas.create_oval(x-r, y-r, x+r, y+r,
                                             fill=stroke["color"], outline=stroke["color"])
                elif len(pts) > 1:
                    flat = [v for p in pts for v in p]
                    self.canvas.create_line(*flat, fill=stroke["color"],
                                            width=stroke["width"], capstyle=tk.ROUND,
                                            joinstyle=tk.ROUND, smooth=True)
        if self.converted_strokes and self.view_mode.get() in ("Mathematical", "Overlay"):
            for stroke in self.converted_strokes:
                for segment in stroke["segments"]:
                    pts = sample_bezier(segment, 32)
                    flat = [v for p in pts for v in p]
                    self.canvas.create_line(*flat, fill=stroke["color"],
                                            width=stroke["width"], capstyle=tk.ROUND,
                                            joinstyle=tk.ROUND, smooth=True)
        for item in self.generated_art:
            pts = item.get("points", [])
            if len(pts) < 2:
                continue
            flat = [v for point in pts for v in point]
            if item.get("type") == "shape":
                fill = item.get("fill") or ""
                self.canvas.create_polygon(*flat, fill=fill, outline=item.get("outline", "#6B21A8"),
                                           width=item.get("width", 3), smooth=False)
            else:
                self.canvas.create_line(*flat, fill=item.get("color", ACCENT),
                                        width=item.get("width", 3), capstyle=tk.ROUND,
                                        joinstyle=tk.ROUND, smooth=True)

    def set_view(self, mode):
        if mode != "Original" and not self.converted_strokes and not self.generated_art:
            messagebox.showinfo("Create artwork first", "Draw and convert something, or create a mathematical wave or shape.")
            return
        self.view_mode.set(mode)
        self._redraw()
        self.status.set(f"Viewing: {mode}")

    def convert_drawing(self):
        if not self.strokes:
            messagebox.showinfo("Nothing to convert", "Draw something on the canvas first.")
            return
        self.converted_strokes = []
        original_points = 0
        segment_count = 0
        for stroke in self.strokes:
            points = stroke["points"]
            original_points += len(points)
            simplified = simplify_rdp(points, epsilon=2.0)
            segments = points_to_beziers(simplified)
            segment_count += len(segments)
            self.converted_strokes.append({
                "segments": segments,
                "color": stroke["color"],
                "width": stroke["width"]
            })
        self.view_mode.set("Overlay")
        self._redraw()
        self.stats.set(f"Strokes: {len(self.strokes)}\nInput points: {original_points}\nBézier segments: {segment_count}\nStatus: converted")
        self._show_functions()
        self.status.set(f"Converted {original_points} points into {segment_count} cubic Bézier segments")

    def _functions_as_text(self):
        """Return every generated parametric Bézier segment as plain text."""
        if not self.converted_strokes and not self.generated_art:
            return ""
        lines = [
            "WAVEFORM — MATHEMATICAL ARTWORK",
            "Freehand strokes use piecewise cubic Bézier parametric functions.",
            "Generated waves and shapes use sampled parametric/function definitions.",
            "Parameter range: 0 <= t <= 1 for each segment",
            "",
            "For each segment:",
            "x(t) = (1-t)^3*x0 + 3*(1-t)^2*t*x1 + 3*(1-t)*t^2*x2 + t^3*x3",
            "y(t) = (1-t)^3*y0 + 3*(1-t)^2*t*y1 + 3*(1-t)*t^2*y2 + t^3*y3",
            "",
            "The coordinates use the WAVEFORM canvas coordinate system (origin at top-left; y increases downward).",
            "Each segment starts where the previous segment in its stroke ended.",
            ""
        ]
        for stroke_index, stroke in enumerate(self.converted_strokes, 1):
            lines.append(f"STROKE {stroke_index}")
            lines.append(f"color = {stroke['color']}")
            lines.append(f"width = {stroke['width']}")
            for segment_index, segment in enumerate(stroke["segments"], 1):
                p0, p1, p2, p3 = segment
                coords = [tuple(float(v) for v in point) for point in (p0, p1, p2, p3)]
                lines.append(f"\n  SEGMENT {segment_index}")
                lines.append(
                    "  x(t) = (1-t)^3*({:.6f}) + 3*(1-t)^2*t*({:.6f}) + "
                    "3*(1-t)*t^2*({:.6f}) + t^3*({:.6f})".format(
                        coords[0][0], coords[1][0], coords[2][0], coords[3][0])
                )
                lines.append(
                    "  y(t) = (1-t)^3*({:.6f}) + 3*(1-t)^2*t*({:.6f}) + "
                    "3*(1-t)*t^2*({:.6f}) + t^3*({:.6f})".format(
                        coords[0][1], coords[1][1], coords[2][1], coords[3][1])
                )
                lines.append(
                    "  control_points = P0{}, P1{}, P2{}, P3{}".format(
                        coords[0], coords[1], coords[2], coords[3])
                )
            lines.append("")
        return "\n".join(lines)

    def _show_functions(self):
        content = self._functions_as_text()
        self.formula_text.configure(state="normal")
        self.formula_text.delete("1.0", "end")
        self.formula_text.insert("1.0", content if content else "No curve segments generated.")
        self.formula_text.configure(state="disabled")

    def copy_functions(self):
        if not self.converted_strokes and not self.generated_art:
            messagebox.showinfo("No mathematical artwork", "Create a wave/shape or convert a freehand drawing first.")
            return
        content = self._functions_as_text()
        self.clipboard_clear()
        self.clipboard_append(content)
        self.update()
        self.status.set("Readable equations copied — use these in a report")
        messagebox.showinfo("Copied", "All generated mathematical functions have been copied.")

    def export_functions_txt(self):
        if not self.converted_strokes and not self.generated_art:
            messagebox.showinfo("No mathematical artwork", "Create a wave/shape or convert a freehand drawing first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="waveform_mathematical_functions.txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        Path(path).write_text(self._functions_as_text(), encoding="utf-8")
        self.status.set(f"Mathematical functions exported to {Path(path).name}")
        messagebox.showinfo("Export complete", f"All mathematical functions saved to:\n{path}")

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append({
            "strokes": [dict(s, points=list(s["points"])) for s in self.strokes],
            "generated": [dict(a, points=list(a["points"])) for a in self.generated_art]
        })
        snapshot = self.undo_stack.pop()
        self.strokes = snapshot["strokes"]
        self.generated_art = snapshot["generated"]
        self.converted_strokes = []
        self.view_mode.set("Original")
        self._redraw()
        self.status.set("Undo")

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append({
            "strokes": [dict(s, points=list(s["points"])) for s in self.strokes],
            "generated": [dict(a, points=list(a["points"])) for a in self.generated_art]
        })
        snapshot = self.redo_stack.pop()
        self.strokes = snapshot["strokes"]
        self.generated_art = snapshot["generated"]
        self.converted_strokes = []
        self.view_mode.set("Original")
        self._redraw()
        self.status.set("Redo")

    def clear_canvas(self):
        if self.strokes:
            self._snapshot()
        self.strokes = []
        self.converted_strokes = []
        self.generated_art = []
        self.view_mode.set("Original")
        self._redraw()
        self.stats.set("No conversion yet")
        self.status.set("Canvas cleared")

    def _default_projects_folder(self):
        documents = Path.home() / "Documents"
        if not documents.exists():
            documents = Path.home()
        return documents / "WAVEFORM Projects"

    def _update_window_title(self):
        self.title(f"WAVEFORM Studio | {self.current_project_name}")

    def _project_payload(self):
        return {
            "format": "WAVEFORM_PROJECT",
            "version": 1,
            "name": self.current_project_name,
            "saved": datetime.now().isoformat(timespec="seconds"),
            "view": self.view_mode.get(),
            "source_strokes": self.strokes,
            "generated_art": self.generated_art,
            "artwork": self._wave_payload() if self.converted_strokes else None
        }

    def save_project(self):
        if not self.strokes and not self.converted_strokes:
            messagebox.showinfo("Nothing to save", "Draw something first, then save your project.")
            return
        if self.strokes and not self.converted_strokes:
            self.convert_drawing()
        initial_dir = self._default_projects_folder()
        initial_dir.mkdir(parents=True, exist_ok=True)
        if self.current_project_path and Path(self.current_project_path).suffix.lower() == ".wproj":
            target = Path(self.current_project_path)
        else:
            initial_name = "My_WAVEFORM_Project.wproj"
            path = filedialog.asksaveasfilename(
                title="Save WAVEFORM project",
                initialdir=str(initial_dir),
                initialfile=initial_name,
                defaultextension=".wproj",
                filetypes=[("WAVEFORM project", "*.wproj")]
            )
            if not path:
                return
            target = Path(path)
            if target.suffix.lower() != ".wproj":
                target = target.with_suffix(".wproj")
        self.current_project_name = target.stem
        payload = self._project_payload()
        payload["name"] = self.current_project_name
        try:
            target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self.current_project_path = str(target)
            self._update_window_title()
            self.status.set(f"Project saved: {target.name}")
            messagebox.showinfo(
                "Project saved",
                f"Your editable project is saved here:\n{target}\n\n"
                "Open it later to continue editing the original drawing."
            )
        except Exception as error:
            messagebox.showerror("Could not save project", str(error))

    def _validate_source_strokes(self, strokes):
        if not isinstance(strokes, list) or len(strokes) > 100:
            raise ValueError("The project contains an invalid number of original strokes.")
        cleaned = []
        for stroke in strokes:
            if not isinstance(stroke, dict):
                raise ValueError("An original stroke is invalid.")
            points = stroke.get("points")
            if not isinstance(points, list) or len(points) > 100000:
                raise ValueError("An original stroke has invalid drawing points.")
            clean_points = []
            for point in points:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    raise ValueError("A drawing point must contain x and y coordinates.")
                x, y = float(point[0]), float(point[1])
                if not (math.isfinite(x) and math.isfinite(y) and -10000 <= x <= 10000 and -10000 <= y <= 10000):
                    raise ValueError("A drawing point is outside the supported canvas area.")
                clean_points.append([x, y])
            color = str(stroke.get("color", "#25283B"))
            if len(color) != 7 or not color.startswith("#"):
                raise ValueError("An original stroke has an invalid colour.")
            int(color[1:], 16)
            width = max(1, min(40, int(stroke.get("width", 4))))
            cleaned.append({"points": clean_points, "color": color, "width": width})
        return cleaned

    def open_project(self):
        initial_dir = self._default_projects_folder()
        initial_dir.mkdir(parents=True, exist_ok=True)
        path = filedialog.askopenfilename(
            title="Open WAVEFORM project",
            initialdir=str(initial_dir),
            filetypes=[
                ("WAVEFORM projects and artwork", "*.wproj *.wave"),
                ("WAVEFORM project", "*.wproj"),
                ("WAVEFORM artwork", "*.wave"),
                ("All files", "*.*")
            ]
        )
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload.get("format") == "WAVEFORM_PROJECT":
                self._load_project_payload(payload, Path(path))
            else:
                self._load_wave_payload(payload, Path(path).name)
                self.current_project_path = None
                self.current_project_name = Path(path).stem
                self._update_window_title()
            self.status.set(f"Opened: {Path(path).name}")
        except Exception as error:
            messagebox.showerror("Could not open project", str(error))

    def _load_project_payload(self, payload, path):
        if payload.get("version") != 1:
            raise ValueError("This WAVEFORM project version is not supported.")
        source_strokes = self._validate_source_strokes(payload.get("source_strokes", []))
        artwork = payload.get("artwork")
        converted = []
        if artwork is not None:
            result = validate_art_code(artwork)
            if result["kind"] != "freehand":
                raise ValueError("The mathematical artwork inside this project is invalid.")
            converted = result["strokes"]

        self.strokes = source_strokes
        self.converted_strokes = converted
        self.generated_art = payload.get("generated_art", [])
        if not isinstance(self.generated_art, list):
            self.generated_art = []
        self.current_points = []
        self.undo_stack.clear()
        self.redo_stack.clear()
        saved_view = payload.get("view", "Original")
        if saved_view not in ("Original", "Mathematical", "Overlay"):
            saved_view = "Original"
        if saved_view != "Original" and not converted and not self.generated_art:
            saved_view = "Original"
        self.view_mode.set(saved_view)
        self.current_project_path = str(path)
        self.current_project_name = str(payload.get("name") or path.stem)
        self._update_window_title()
        self._redraw()
        if converted:
            point_count = sum(len(stroke["points"]) for stroke in source_strokes)
            segment_count = sum(len(stroke["segments"]) for stroke in converted)
            self.stats.set(
                f"Strokes: {len(source_strokes)}\nInput points: {point_count}\n"
                f"Bézier segments: {segment_count}\nStatus: project opened"
            )
        else:
            self.stats.set(f"Strokes: {len(source_strokes)}\nStatus: ready to convert")
        self._show_functions()
        self.status.set(f"Project opened: {path.name}")

    def _wave_payload(self):
        return {
            "format": "WAVEFORM_ART", "version": 1, "kind": "freehand",
            "representation": "piecewise_cubic_bezier_parametric",
            "created": datetime.now().isoformat(timespec="seconds"),
            "strokes": self.converted_strokes
        }

    def copy_wave_code(self):
        if not self.converted_strokes:
            messagebox.showinfo("Convert first", "Draw something and click Convert to mathematics first.")
            return
        code = json.dumps(self._wave_payload(), indent=2)
        self.clipboard_clear()
        self.clipboard_append(code)
        self.update()
        self.status.set("Shareable artwork data copied — ready to transfer")
        messagebox.showinfo("Artwork data copied", "The complete shareable artwork data is on your clipboard. On the other computer, open WAVEFORM, choose Paste artwork data, paste it, then click Recreate artwork.")

    def paste_wave_code(self):
        """Open a guided import dialog for WAVEFORM's shareable artwork data."""
        dialog = tk.Toplevel(self)
        dialog.title("Import artwork data")
        dialog.configure(bg=BG)
        dialog.geometry("760x590")
        dialog.minsize(600, 460)
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(
            dialog, text="RECREATE ARTWORK",
            bg=BG, fg=TEXT, font=("Segoe UI", 13, "bold")
        ).pack(anchor="w", padx=18, pady=(17, 4))
        tk.Label(
            dialog,
            text="Paste the artwork data copied from another WAVEFORM window. This is the structured code that rebuilds the drawing—not the readable equations for a report.",
            bg=BG, fg=MUTED, font=("Segoe UI", 9), wraplength=710, justify="left"
        ).pack(anchor="w", padx=18, pady=(0, 12))

        tip = tk.Frame(dialog, bg="#241332")
        tip.pack(fill="x", padx=18, pady=(0, 10))
        tk.Label(tip, text="WHAT SHOULD I PASTE?", bg="#241332", fg="#E9D5FF",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=11, pady=(8, 2))
        tk.Label(tip, text='Valid artwork data starts with { and contains "format": "WAVEFORM_ART".',
                 bg="#241332", fg=TEXT, font=("Segoe UI", 8),
                 wraplength=690, justify="left").pack(anchor="w", padx=11, pady=(0, 8))

        text_frame = tk.Frame(dialog, bg=PANEL)
        text_frame.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        paste_box = tk.Text(
            text_frame, bg="#0D0A13", fg="#E8E5F5",
            insertbackground=TEXT, selectbackground="#514477",
            relief="flat", wrap="none", undo=True,
            font=("Consolas", 9), padx=11, pady=11
        )
        ybar = tk.Scrollbar(text_frame, orient="vertical", command=paste_box.yview)
        xbar = tk.Scrollbar(text_frame, orient="horizontal", command=paste_box.xview)
        paste_box.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        ybar.pack(side="right", fill="y")
        xbar.pack(side="bottom", fill="x")
        paste_box.pack(side="left", fill="both", expand=True)

        def try_clipboard_paste():
            try:
                clipboard_text = self.clipboard_get()
                paste_box.delete("1.0", "end")
                paste_box.insert("1.0", clipboard_text)
                paste_box.focus_set()
            except tk.TclError:
                messagebox.showinfo(
                    "Clipboard unavailable",
                    "The clipboard has no readable text. Click inside the box and press Ctrl+V.",
                    parent=dialog
                )

        def load_pasted_artwork():
            raw = paste_box.get("1.0", "end-1c").strip()
            if not raw:
                messagebox.showwarning("Nothing pasted", "Paste the artwork data into the box first.", parent=dialog)
                return
            cleaned = raw
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\\s*|\\s*```$", "", cleaned, flags=re.IGNORECASE).strip()
            if cleaned.startswith("WAVEFORM") or "MATHEMATICAL FREEHAND REPRESENTATION" in cleaned[:200]:
                messagebox.showerror(
                    "These are equations, not artwork data",
                    "You copied the readable mathematical functions. Close this window, return to the drawing, and choose:\n\nCopy artwork data\n\nThat option copies the structured data needed to recreate the drawing.",
                    parent=dialog
                )
                return
            try:
                payload = json.loads(cleaned)
                self._load_wave_payload(payload, "pasted artwork data")
                dialog.destroy()
                messagebox.showinfo(
                    "Artwork recreated",
                    "Your mathematical drawing has been rebuilt on the artboard.",
                    parent=self
                )
            except Exception as error:
                messagebox.showerror(
                    "Could not recreate artwork",
                    "This does not look like complete WAVEFORM artwork data. Copy it again using Copy artwork data, and include everything from the opening { to the closing }.\n\n"
                    f"Details: {error}",
                    parent=dialog
                )

        actions = tk.Frame(dialog, bg=BG)
        actions.pack(fill="x", padx=18, pady=(0, 16))
        self.button(actions, "Paste from clipboard", try_clipboard_paste, compact=True).pack(side="left")
        self.button(actions, "Cancel", dialog.destroy, compact=True).pack(side="right", padx=(0, 8))
        self.button(actions, "Recreate artwork", load_pasted_artwork, primary=True, compact=True).pack(side="right")
        paste_box.focus_set()
        dialog.bind("<Control-Return>", lambda _event: load_pasted_artwork())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())

    def _load_wave_payload(self, payload, source_name="imported file"):
        result = validate_art_code(payload)
        if result["kind"] != "freehand":
            raise ValueError("This code does not contain converted freehand artwork.")
        self.converted_strokes = result["strokes"]
        self.strokes = []
        self.generated_art = []
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.view_mode.set("Mathematical")
        self._redraw()
        count = sum(len(s["segments"]) for s in self.converted_strokes)
        self.stats.set(f"Strokes: {len(self.converted_strokes)}\nBézier segments: {count}\nStatus: recreated")
        self._show_functions()
        self.status.set(f"Recreated mathematical artwork from {source_name}")

    def export_wave(self):
        if not self.converted_strokes:
            self.convert_drawing()
        if not self.converted_strokes:
            return
        export_dir = self._default_projects_folder()
        export_dir.mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(
            initialdir=str(export_dir),
            defaultextension=".wave", initialfile="my_mathematical_art.wave",
            filetypes=[("WAVEFORM mathematical artwork", "*.wave"), ("JSON", "*.json")])
        if not path:
            return
        Path(path).write_text(json.dumps(self._wave_payload(), indent=2), encoding="utf-8")
        messagebox.showinfo("Export complete", "Mathematical artwork saved as a .wave file.")

    def import_wave(self):
        path = filedialog.askopenfilename(
            filetypes=[("WAVEFORM mathematical artwork", "*.wave *.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            self._load_wave_payload(payload, Path(path).name)
        except Exception as error:
            messagebox.showerror("Import failed", str(error))

    def export_png(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png", initialfile="waveform_art.png",
            filetypes=[("PNG image", "*.png")])
        if not path:
            return
        try:
            from PIL import Image, ImageDraw
            width = max(1, self.canvas.winfo_width())
            height = max(1, self.canvas.winfo_height())
            image = Image.new("RGB", (width, height), PAPER)
            draw = ImageDraw.Draw(image)
            if self.view_mode.get() in ("Original", "Overlay"):
                for stroke in self.strokes:
                    pts = [tuple(map(float, p)) for p in stroke["points"]]
                    if len(pts) == 1:
                        x, y = pts[0]
                        r = stroke["width"] / 2
                        draw.ellipse((x-r, y-r, x+r, y+r), fill=stroke["color"])
                    elif len(pts) > 1:
                        draw.line(pts, fill=stroke["color"], width=stroke["width"], joint="curve")
            if self.converted_strokes and self.view_mode.get() in ("Mathematical", "Overlay"):
                for stroke in self.converted_strokes:
                    for seg in stroke["segments"]:
                        pts = [tuple(p) for p in sample_bezier(seg, 48)]
                        draw.line(pts, fill=stroke["color"], width=stroke["width"], joint="curve")
            for item in self.generated_art:
                pts = [tuple(map(float, point)) for point in item.get("points", [])]
                if len(pts) < 2:
                    continue
                if item.get("type") == "shape":
                    draw.polygon(pts, fill=item.get("fill") or None,
                                 outline=item.get("outline", "#6B21A8"),
                                 width=item.get("width", 3))
                else:
                    draw.line(pts, fill=item.get("color", ACCENT),
                              width=item.get("width", 3), joint="curve")
            image.save(path)
            messagebox.showinfo("PNG exported", f"Saved artwork to:\n{path}")
        except Exception as error:
            messagebox.showerror("PNG export failed", str(error))


if __name__ == "__main__":
    WaveformApp().mainloop()
