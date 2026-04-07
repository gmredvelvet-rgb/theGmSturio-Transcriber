"""TheGmStudio Transcriber v2 GUI with CustomTkinter.

Includes: campaign management, transcription, local AI summary, Discord integration.
"""

import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, simpledialog

import customtkinter as ctk

from . import __version__, __app_name__
from .campaigns import Campaign, CampaignManager
from .config import AVAILABLE_MODELS, DEFAULT_MODEL, OUTPUT_FORMATS, SUPPORTED_EXTENSIONS, TranscriptionConfig
from .discord_hook import send_to_discord, validate_webhook_url
from .formatter import export_transcript
from .merger import merge_and_sort, merge_consecutive
from .summarizer import (
    AVAILABLE_MODELS as AI_MODELS,
    DEFAULT_MODEL as AI_DEFAULT_MODEL,
    DEFAULT_OLLAMA_URL,
    check_ollama_running,
    generate_summary,
    list_ollama_models,
    save_summary,
)
from .transcribe import Segment, transcribe_session

# -- Paleta de colores --
C_BG = "#0d0d12"
C_CARD = "#161625"
C_CARD_ALT = "#1c1c30"
C_SIDEBAR = "#111118"
C_ACCENT = "#e94560"
C_ACCENT_H = "#ff6b81"
C_GREEN = "#0f9b58"
C_GREEN_H = "#12b86a"
C_BLUE = "#2d7dd2"
C_BLUE_H = "#4a9eff"
C_PURPLE = "#7c3aed"
C_PURPLE_H = "#9f67ff"
C_RED = "#c0392b"
C_RED_H = "#e74c3c"
C_ORANGE = "#e67e22"
C_TEXT = "#eaeaea"
C_DIM = "#6b7280"
C_BORDER = "#2a2a40"
C_INPUT = "#0a0a16"
C_LIST_SEL = "#e94560"

LANGUAGE_OPTIONS = {
    "Spanish": "es",
    "English": "en",
    "Auto-detect": None,
    "Portuguese": "pt",
    "French": "fr",
    "German": "de",
}


class GUIProgressCallback:
    def __init__(self, app):
        self._app = app

    def on_status(self, msg):
        self._app.after(0, self._app._set_status, msg)

    def on_progress(self, cur, total):
        if total > 0:
            self._app.after(0, self._app._set_progress, cur / total)

    def on_log(self, msg):
        self._app.after(0, self._app._append_log, msg)


class WhispererApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{__app_name__} v{__version__}")
        self.geometry("1100x820")
        self.minsize(950, 720)
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=C_BG)

        # Load logo
        self._logo_image = None
        logo_path = self._find_logo()
        if logo_path:
            try:
                from PIL import Image
                pil_img = Image.open(logo_path)
                self._logo_image = ctk.CTkImage(pil_img, size=(96, 96))
                # Set window icon
                ico_path = logo_path.replace(".png", ".ico") if logo_path.endswith(".png") else None
                if ico_path and Path(ico_path).exists():
                    self.iconbitmap(ico_path)
                else:
                    self.iconphoto(True, tk.PhotoImage(file=logo_path))
            except Exception:
                pass

        self._audio_files = []
        self._cancel_event = threading.Event()
        self._is_running = False
        self._open_btn = None
        self._last_transcript_path = None
        self._last_summary_path = None

        self._cm = CampaignManager(Path("campaigns").resolve())
        self._current_campaign = None

        self._build_ui()
        self._refresh_campaigns()

    @staticmethod
    def _find_logo() -> str | None:
        """Find thegmstudiologo.png in common locations."""
        candidates = [
            Path(getattr(sys, '_MEIPASS', '')) / "thegmstudiologo.png",
            Path(sys.executable).parent / "thegmstudiologo.png",
            Path(__file__).resolve().parent.parent / "thegmstudiologo.png",
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return None

    # === UI CONSTRUCTION ===

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main_panel()

    # -- SIDEBAR --

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=260, fg_color=C_SIDEBAR, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_rowconfigure(3, weight=1)

        if self._logo_image:
            ctk.CTkLabel(sb, image=self._logo_image, text="").grid(row=0, column=0, pady=(20, 0))
        else:
            ctk.CTkLabel(sb, text="\U0001f3b2", font=ctk.CTkFont(size=36)).grid(row=0, column=0, pady=(20, 0))
        ctk.CTkLabel(sb, text=__app_name__, font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=C_TEXT).grid(row=1, column=0, pady=(4, 0))
        ctk.CTkLabel(sb, text=f"v{__version__}", font=ctk.CTkFont(size=11),
                     text_color=C_DIM).grid(row=2, column=0, pady=(0, 12))

        list_frame = ctk.CTkFrame(sb, fg_color="transparent")
        list_frame.grid(row=3, column=0, sticky="nsew", padx=12)
        list_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(list_frame, text="CAMPAIGNS", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C_DIM).grid(row=0, column=0, sticky="w", pady=(0, 6))

        self._campaign_list = tk.Listbox(
            list_frame, height=10, bg=C_INPUT, fg=C_TEXT,
            selectbackground=C_ACCENT, selectforeground="white",
            font=("Segoe UI", 11), borderwidth=0, highlightthickness=0,
            activestyle="none", relief="flat", exportselection=False,
        )
        self._campaign_list.grid(row=1, column=0, sticky="nsew")
        self._campaign_list.bind("<<ListboxSelect>>", self._on_campaign_select)

        btn_frame = ctk.CTkFrame(sb, fg_color="transparent")
        btn_frame.grid(row=4, column=0, sticky="ew", padx=12, pady=(8, 4))

        ctk.CTkButton(btn_frame, text="+ New Campaign", height=34, corner_radius=8,
                      font=ctk.CTkFont(size=12), fg_color=C_GREEN, hover_color=C_GREEN_H,
                      command=self._create_campaign).pack(fill="x", pady=(0, 4))
        ctk.CTkButton(btn_frame, text="Delete", height=30, corner_radius=8,
                      font=ctk.CTkFont(size=11), fg_color="transparent",
                      hover_color="#3a1a1a", border_width=1, border_color="#5a2a2a",
                      text_color="#ff6b6b", command=self._delete_campaign).pack(fill="x")

        wh_frame = ctk.CTkFrame(sb, fg_color=C_CARD, corner_radius=10)
        wh_frame.grid(row=5, column=0, sticky="ew", padx=12, pady=(12, 16))

        ctk.CTkLabel(wh_frame, text="Discord Webhook",
                     font=ctk.CTkFont(size=11, weight="bold"), text_color=C_DIM
                     ).pack(anchor="w", padx=10, pady=(8, 4))

        self._webhook_var = ctk.StringVar()
        self._webhook_entry = ctk.CTkEntry(
            wh_frame, textvariable=self._webhook_var, height=30,
            placeholder_text="https://discord.com/api/webhooks/...",
            font=ctk.CTkFont(size=10), fg_color=C_INPUT, border_color=C_BORDER,
            corner_radius=6,
        )
        self._webhook_entry.pack(fill="x", padx=10, pady=(0, 4))

        ctk.CTkButton(wh_frame, text="Save Webhook", height=28, corner_radius=6,
                      font=ctk.CTkFont(size=11), fg_color=C_BLUE, hover_color=C_BLUE_H,
                      command=self._save_webhook).pack(fill="x", padx=10, pady=(0, 8))

        # -- Links --
        links_frame = ctk.CTkFrame(sb, fg_color="transparent")
        links_frame.grid(row=6, column=0, sticky="ew", padx=12, pady=(4, 16))
        links_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(links_frame, text="\u2615 Buy me a Ko-Fi", height=28, corner_radius=6,
                      font=ctk.CTkFont(size=11), fg_color="#ff5e5b", hover_color="#ff7875",
                      command=lambda: __import__('webbrowser').open("https://ko-fi.com/thegmstudio")
                      ).grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkButton(links_frame, text="\U0001f310 TheGmStudio", height=28, corner_radius=6,
                      font=ctk.CTkFont(size=11), fg_color=C_CARD_ALT, hover_color="#252540",
                      border_width=1, border_color=C_BORDER,
                      command=lambda: __import__('webbrowser').open("https://thegmstudio.com/")
                      ).grid(row=1, column=0, sticky="ew")

    # -- MAIN PANEL --

    def _build_main_panel(self):
        main = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        self._main = main

        self._build_header()
        self._build_files_card()
        self._build_config_card()
        self._build_actions()
        self._build_ai_card()
        self._build_log_card()

    def _build_header(self):
        f = ctk.CTkFrame(self._main, fg_color="transparent")
        f.grid(row=0, column=0, sticky="ew", padx=24, pady=(16, 4))

        self._header_label = ctk.CTkLabel(f, text="Select or create a campaign to get started",
                                          font=ctk.CTkFont(size=20, weight="bold"), text_color=C_TEXT)
        self._header_label.pack(anchor="w")
        self._header_sub = ctk.CTkLabel(f, text="Transcriptions will be saved in the campaign folder",
                                        font=ctk.CTkFont(size=12), text_color=C_DIM)
        self._header_sub.pack(anchor="w")

        ctk.CTkFrame(self._main, height=1, fg_color=C_BORDER).grid(row=1, column=0, sticky="ew", padx=24, pady=(8, 4))

    def _build_files_card(self):
        card = ctk.CTkFrame(self._main, fg_color=C_CARD, corner_radius=12,
                            border_width=1, border_color=C_BORDER)
        card.grid(row=2, column=0, sticky="ew", padx=24, pady=(8, 6))
        card.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        ctk.CTkLabel(top, text="Audio Files",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color=C_TEXT).pack(side="left")
        self._file_count = ctk.CTkLabel(top, text="No files",
                                        font=ctk.CTkFont(size=11), text_color=C_DIM)
        self._file_count.pack(side="right")

        self._file_list = tk.Listbox(
            card, height=4, bg=C_INPUT, fg=C_TEXT,
            selectbackground=C_LIST_SEL, selectforeground="white",
            font=("Segoe UI", 11), borderwidth=0, highlightthickness=0,
            activestyle="none", relief="flat",
        )
        self._file_list.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))

        self._empty_label = ctk.CTkLabel(card,
            text="Drag files or use the buttons - WAV MP3 M4A OGG AAC",
            font=ctk.CTkFont(size=11), text_color=C_DIM, justify="center")
        self._empty_label.grid(row=2, column=0, padx=14, pady=(0, 4))

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.grid(row=3, column=0, sticky="ew", padx=14, pady=(2, 12))

        ctk.CTkButton(btns, text="Add Files", width=130, height=34, corner_radius=8,
                      fg_color=C_ACCENT, hover_color=C_ACCENT_H,
                      font=ctk.CTkFont(size=12), command=self._add_files).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btns, text="Craig Folder", width=155, height=34, corner_radius=8,
                      fg_color=C_CARD_ALT, hover_color="#252540",
                      border_width=1, border_color=C_BORDER,
                      font=ctk.CTkFont(size=12), command=self._add_folder).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btns, text="Clear", width=80, height=34, corner_radius=8,
                      fg_color="transparent", hover_color="#2a2a2a",
                      border_width=1, border_color=C_BORDER, text_color=C_DIM,
                      font=ctk.CTkFont(size=11), command=self._clear_files).pack(side="right")
        ctk.CTkButton(btns, text="Remove", width=90, height=34, corner_radius=8,
                      fg_color="transparent", hover_color="#3a1a1a",
                      border_width=1, border_color="#5a2a2a", text_color="#ff6b6b",
                      font=ctk.CTkFont(size=11), command=self._remove_selected).pack(side="right", padx=(0, 6))

    def _build_config_card(self):
        card = ctk.CTkFrame(self._main, fg_color=C_CARD, corner_radius=12,
                            border_width=1, border_color=C_BORDER)
        card.grid(row=3, column=0, sticky="ew", padx=24, pady=6)

        ctk.CTkLabel(card, text="Configuration",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color=C_TEXT
                     ).grid(row=0, column=0, columnspan=6, sticky="w", padx=14, pady=(12, 8))

        self._lbl(card, "Model", 1, 0)
        self._model_var = ctk.StringVar(value=DEFAULT_MODEL)
        self._opt(card, self._model_var, list(AVAILABLE_MODELS), 140, 1, 1)

        self._lbl(card, "Language", 1, 2)
        self._lang_var = ctk.StringVar(value="Spanish")
        self._opt(card, self._lang_var, list(LANGUAGE_OPTIONS.keys()), 145, 1, 3)

        self._lbl(card, "Format", 1, 4)
        self._format_var = ctk.StringVar(value="txt")
        self._opt(card, self._format_var, list(OUTPUT_FORMATS), 110, 1, 5)

        self._lbl(card, "CPU Threads", 2, 0)
        tf = ctk.CTkFrame(card, fg_color="transparent")
        tf.grid(row=2, column=1, padx=(0, 14), pady=5, sticky="w")
        self._threads_var = tk.IntVar(value=6)
        ctk.CTkSlider(tf, from_=1, to=12, number_of_steps=11, variable=self._threads_var,
                      width=105, height=16, progress_color=C_ACCENT, button_color=C_ACCENT,
                      button_hover_color=C_ACCENT_H, command=self._on_threads).pack(side="left")
        self._threads_lbl = ctk.CTkLabel(tf, text="6", width=26,
                                         font=ctk.CTkFont(size=13, weight="bold"), text_color=C_ACCENT)
        self._threads_lbl.pack(side="left", padx=(6, 0))

        self._lbl(card, "Output", 2, 2)
        of = ctk.CTkFrame(card, fg_color="transparent")
        of.grid(row=2, column=3, columnspan=3, padx=(0, 14), pady=5, sticky="ew")
        self._output_var = ctk.StringVar(value=str(Path("output").resolve()))
        ctk.CTkEntry(of, textvariable=self._output_var, height=30, corner_radius=8,
                     fg_color=C_INPUT, border_color=C_BORDER).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(of, text="...", width=34, height=30, corner_radius=8,
                      fg_color=C_CARD_ALT, hover_color="#252540",
                      command=self._browse_output).pack(side="left", padx=(5, 0))

        self._lbl(card, "Filename", 3, 0)
        self._filename_var = ctk.StringVar(value="transcript")
        ctk.CTkEntry(card, textvariable=self._filename_var, width=130, height=30,
                     corner_radius=8, fg_color=C_INPUT, border_color=C_BORDER
                     ).grid(row=3, column=1, padx=(0, 14), pady=(5, 12), sticky="w")

        self._merge_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(card, text="Merge consecutive segments", variable=self._merge_var,
                        font=ctk.CTkFont(size=12), fg_color=C_ACCENT, hover_color=C_ACCENT_H,
                        border_color=C_BORDER
                        ).grid(row=3, column=2, columnspan=4, padx=(0, 14), pady=(5, 12), sticky="w")

    def _build_actions(self):
        f = ctk.CTkFrame(self._main, fg_color="transparent")
        f.grid(row=4, column=0, sticky="ew", padx=24, pady=(6, 2))
        f.grid_columnconfigure(0, weight=1)

        bf = ctk.CTkFrame(f, fg_color="transparent")
        bf.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        bf.grid_columnconfigure(0, weight=1)

        self._start_btn = ctk.CTkButton(
            bf, text="Start Transcription",
            font=ctk.CTkFont(size=16, weight="bold"), height=48, corner_radius=12,
            fg_color=C_GREEN, hover_color=C_GREEN_H, command=self._start_transcription)
        self._start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self._cancel_btn = ctk.CTkButton(
            bf, text="Cancel", font=ctk.CTkFont(size=13), height=48, width=120,
            corner_radius=12, fg_color=C_RED, hover_color=C_RED_H,
            state="disabled", command=self._cancel_transcription)
        self._cancel_btn.grid(row=0, column=1)

        self._progress = ctk.CTkProgressBar(f, height=8, corner_radius=4, progress_color=C_ACCENT)
        self._progress.grid(row=1, column=0, sticky="ew")
        self._progress.set(0)

        self._status = ctk.CTkLabel(f, text="Select a campaign to get started",
                                    font=ctk.CTkFont(size=12), text_color=C_DIM)
        self._status.grid(row=2, column=0, sticky="w", pady=(3, 0))

    def _build_ai_card(self):
        card = ctk.CTkFrame(self._main, fg_color=C_CARD, corner_radius=12,
                            border_width=1, border_color=C_BORDER)
        card.grid(row=5, column=0, sticky="ew", padx=24, pady=(8, 6))
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="Local AI Analysis (Ollama)",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color=C_TEXT
                     ).grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(12, 8))

        self._ollama_status = ctk.CTkLabel(card, text="",
                                           font=ctk.CTkFont(size=11), text_color=C_DIM)
        self._ollama_status.grid(row=0, column=3, sticky="e", padx=14, pady=(12, 8))

        self._lbl(card, "Ollama URL", 1, 0)
        self._ollama_url_var = ctk.StringVar(value=DEFAULT_OLLAMA_URL)
        url_frame = ctk.CTkFrame(card, fg_color="transparent")
        url_frame.grid(row=1, column=1, columnspan=3, padx=(0, 14), pady=5, sticky="ew")
        ctk.CTkEntry(url_frame, textvariable=self._ollama_url_var, height=30,
                     corner_radius=8, fg_color=C_INPUT, border_color=C_BORDER,
                     placeholder_text="http://localhost:11434",
                     font=ctk.CTkFont(size=11)).pack(side="left", fill="x", expand=True)

        self._lbl(card, "AI Model", 2, 0)
        self._ai_model_var = ctk.StringVar(value=AI_DEFAULT_MODEL)
        self._opt(card, self._ai_model_var, list(AI_MODELS), 150, 2, 1)

        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=4, sticky="ew", padx=14, pady=(4, 12))

        self._ai_btn = ctk.CTkButton(
            btn_frame, text="Analyze with AI",
            font=ctk.CTkFont(size=13, weight="bold"), height=40, corner_radius=10,
            fg_color=C_PURPLE, hover_color=C_PURPLE_H, command=self._run_ai_summary)
        self._ai_btn.pack(side="left", padx=(0, 8))

        self._discord_btn = ctk.CTkButton(
            btn_frame, text="Send to Discord",
            font=ctk.CTkFont(size=13, weight="bold"), height=40, corner_radius=10,
            fg_color=C_BLUE, hover_color=C_BLUE_H, command=self._send_discord)
        self._discord_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(btn_frame, text="Refresh", width=60, height=40, corner_radius=10,
                      fg_color=C_CARD_ALT, hover_color="#252540",
                      command=self._check_ollama_status).pack(side="right")

        self._ai_preview = ctk.CTkTextbox(
            card, height=120, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=C_INPUT, text_color="#c0d0e0", corner_radius=8,
            border_width=1, border_color=C_BORDER, state="disabled", wrap="word")
        self._ai_preview.grid(row=4, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 12))

        self._check_ollama_status()

    def _build_log_card(self):
        card = ctk.CTkFrame(self._main, fg_color=C_CARD, corner_radius=12,
                            border_width=1, border_color=C_BORDER)
        card.grid(row=6, column=0, sticky="nsew", padx=24, pady=(6, 18))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(card, text="Log",
                     font=ctk.CTkFont(size=14, weight="bold"), text_color=C_TEXT
                     ).grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))

        self._log = ctk.CTkTextbox(
            card, height=140, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=C_INPUT, text_color="#a0b0c0", corner_radius=8,
            border_width=1, border_color=C_BORDER, state="disabled", wrap="word")
        self._log.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))

    # -- Helpers --

    def _lbl(self, parent, text, row, col):
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=12),
                     text_color=C_DIM).grid(row=row, column=col, padx=(14, 6), pady=5, sticky="e")

    def _opt(self, parent, var, values, width, row, col):
        ctk.CTkOptionMenu(
            parent, variable=var, values=values, width=width, height=30, corner_radius=8,
            fg_color=C_CARD_ALT, button_color=C_ACCENT, button_hover_color=C_ACCENT_H,
        ).grid(row=row, column=col, padx=(0, 14), pady=5, sticky="w")

    # === CAMPAIGN MANAGEMENT ===

    def _refresh_campaigns(self):
        self._campaign_list.delete(0, tk.END)
        for c in self._cm.list_campaigns():
            self._campaign_list.insert(tk.END, f"  {c.name}")

    def _on_campaign_select(self, _event=None):
        sel = self._campaign_list.curselection()
        if not sel:
            return
        campaigns = self._cm.list_campaigns()
        if sel[0] < len(campaigns):
            self._current_campaign = campaigns[sel[0]]
            self._load_campaign(self._current_campaign)

    def _load_campaign(self, campaign):
        self._header_label.configure(text=campaign.name)
        self._header_sub.configure(text=str(campaign.path))
        self._output_var.set(str(campaign.transcripts_dir))
        self._webhook_var.set(campaign.discord_webhook)
        self._status.configure(text=f"Campaign: {campaign.name}", text_color=C_GREEN)
        self._append_log(f"Campaign loaded: {campaign.name}")

    def _create_campaign(self):
        name = simpledialog.askstring("New Campaign", "Campaign name:", parent=self)
        if not name or not name.strip():
            return
        try:
            campaign = self._cm.create_campaign(name.strip())
            self._refresh_campaigns()
            self._current_campaign = campaign
            self._load_campaign(campaign)
            campaigns = self._cm.list_campaigns()
            for i, c in enumerate(campaigns):
                if c.name == campaign.name:
                    self._campaign_list.selection_clear(0, tk.END)
                    self._campaign_list.selection_set(i)
                    break
        except ValueError as e:
            self._append_log(f"Error: {e}")

    def _delete_campaign(self):
        if not self._current_campaign:
            self._append_log("Select a campaign first")
            return
        from tkinter import messagebox
        confirm = messagebox.askyesno(
            "Delete Campaign",
            f"Delete '{self._current_campaign.name}' and all its files?",
            parent=self)
        if confirm:
            self._cm.delete_campaign(self._current_campaign)
            self._current_campaign = None
            self._refresh_campaigns()
            self._header_label.configure(text="Select or create a campaign")
            self._header_sub.configure(text="")
            self._append_log("Campaign deleted")

    def _save_webhook(self):
        if not self._current_campaign:
            self._append_log("Select a campaign first")
            return
        url = self._webhook_var.get().strip()
        if url and not validate_webhook_url(url):
            self._append_log("Invalid webhook URL. Must start with https://discord.com/api/webhooks/")
            return
        self._current_campaign.discord_webhook = url
        self._current_campaign.save()
        self._append_log(f"Webhook saved for '{self._current_campaign.name}'")

    # === FILE MANAGEMENT ===

    def _add_files(self):
        exts = " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))
        files = filedialog.askopenfilenames(
            title="Select audio files",
            filetypes=[("Audio", exts), ("All files", "*.*")])
        for f in files:
            p = Path(f)
            if p not in self._audio_files and p.suffix.lower() in SUPPORTED_EXTENSIONS:
                self._audio_files.append(p)
        self._refresh_files()

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select Craig Bot folder")
        if not folder:
            return
        added = 0
        for f in sorted(Path(folder).iterdir()):
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS and f not in self._audio_files:
                self._audio_files.append(f)
                added += 1
        if added == 0:
            self._append_log(f"No audio files found in: {folder}")
        else:
            self._append_log(f"{added} files loaded from folder")
        self._refresh_files()

    def _remove_selected(self):
        sel = self._file_list.curselection()
        if sel and 0 <= sel[0] < len(self._audio_files):
            self._audio_files.pop(sel[0])
            self._refresh_files()

    def _clear_files(self):
        self._audio_files.clear()
        self._refresh_files()

    def _refresh_files(self):
        self._file_list.delete(0, tk.END)
        for i, f in enumerate(self._audio_files, 1):
            sz = f.stat().st_size / 1e6 if f.exists() else 0
            ext = f.suffix.upper().replace(".", "")
            self._file_list.insert(tk.END, f"  {i}. {f.stem}  -  {sz:.1f} MB  -  {ext}")
        n = len(self._audio_files)
        if n:
            self._file_count.configure(text=f"{n} file{'s' if n != 1 else ''}", text_color=C_ACCENT)
            self._empty_label.grid_remove()
        else:
            self._file_count.configure(text="No files", text_color=C_DIM)
            self._empty_label.grid()

    def _browse_output(self):
        f = filedialog.askdirectory(title="Select output folder")
        if f:
            self._output_var.set(f)

    def _on_threads(self, v):
        self._threads_lbl.configure(text=str(int(v)))

    # === GUI HELPERS ===

    def _set_status(self, msg):
        self._status.configure(text=msg, text_color=C_BLUE)

    def _set_progress(self, v):
        self._progress.set(v)

    def _append_log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.configure(state="normal")
        self._log.insert("end", f"[{ts}]  {msg}\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _check_ollama_status(self):
        url = self._ollama_url_var.get().strip() or DEFAULT_OLLAMA_URL
        if check_ollama_running(url):
            models = list_ollama_models(url)
            self._ollama_status.configure(
                text=f"Ollama active - {len(models)} model(s)", text_color=C_GREEN)
            if models:
                self._ai_model_var.set(models[0])
        else:
            self._ollama_status.configure(text="Ollama not detected", text_color=C_RED)

    # === TRANSCRIPTION ===

    def _start_transcription(self):
        if not self._audio_files:
            self._append_log("No audio files loaded")
            return
        if self._is_running:
            return
        if self._open_btn:
            self._open_btn.destroy()
            self._open_btn = None

        self._is_running = True
        self._cancel_event.clear()
        self._start_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")
        self._progress.set(0)
        self._set_status("Starting transcription...")

        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

        threading.Thread(target=self._run_transcription, daemon=True).start()

    def _cancel_transcription(self):
        if self._is_running:
            self._cancel_event.set()
            self._append_log("Cancelling...")

    def _run_transcription(self):
        try:
            input_dir = self._prepare_input()
            output_dir = Path(self._output_var.get())
            language = LANGUAGE_OPTIONS.get(self._lang_var.get())

            config = TranscriptionConfig(
                input_dir=input_dir, output_dir=output_dir,
                model_size=self._model_var.get(), language=language,
                output_format=self._format_var.get(),
                threads=int(self._threads_var.get()))
            config.validate()
            progress = GUIProgressCallback(self)

            segments = transcribe_session(config, progress, self._cancel_event)

            if self._cancel_event.is_set():
                self.after(0, self._on_cancelled)
                return
            if not segments:
                self.after(0, self._append_log, "No segments with content")
                self.after(0, self._on_finished)
                return

            progress.on_log("Sorting segments...")
            segments = merge_and_sort(segments)
            if self._merge_var.get():
                progress.on_log("Merging consecutive segments...")
                segments = merge_consecutive(segments)

            filename = self._filename_var.get() or "transcript"
            txt_path = export_transcript(segments, output_dir, "txt", filename)
            fmt = config.output_format
            if fmt != "txt":
                export_transcript(segments, output_dir, fmt, filename)

            speakers = sorted({s.speaker for s in segments})
            progress.on_log(f"Transcription completed!")
            progress.on_log(f"   File: {txt_path}")
            progress.on_log(f"   Speakers: {', '.join(speakers)}")
            progress.on_log(f"   Segments: {len(segments)}")

            self._last_transcript_path = txt_path

            if self._current_campaign:
                session_name = filename
                if session_name not in self._current_campaign.sessions:
                    self._current_campaign.sessions.append(session_name)
                    self._current_campaign.save()

            self.after(0, self._on_success, str(txt_path))
        except Exception as e:
            self.after(0, self._append_log, f"Error: {e}")
            self.after(0, self._on_finished)
        finally:
            self._cleanup_input()

    def _prepare_input(self):
        import shutil
        tmp = Path(self._output_var.get()) / "_input_temp"
        tmp.mkdir(parents=True, exist_ok=True)
        for f in self._audio_files:
            dest = tmp / f.name
            if not dest.exists():
                shutil.copy2(f, dest)
        return tmp

    def _cleanup_input(self):
        import shutil
        tmp = Path(self._output_var.get()) / "_input_temp"
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)

    def _on_success(self, path):
        self._set_status("Transcription completed!")
        self._status.configure(text_color=C_GREEN)
        self._progress.set(1.0)
        self._on_finished()
        self._open_btn = ctk.CTkButton(
            self._main, text=f"Open {Path(path).name}",
            font=ctk.CTkFont(size=13, weight="bold"), height=38, corner_radius=10,
            fg_color=C_ACCENT, hover_color=C_ACCENT_H,
            command=lambda: os.startfile(path))
        self._open_btn.grid(row=7, column=0, padx=24, pady=(0, 12))

    def _on_cancelled(self):
        self._append_log("Transcription cancelled")
        self._status.configure(text="Cancelled", text_color=C_ORANGE)
        self._on_finished()

    def _on_finished(self):
        self._is_running = False
        self._start_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")

    # === AI SUMMARY ===

    def _run_ai_summary(self):
        if not self._last_transcript_path or not self._last_transcript_path.exists():
            self._append_log("Generate a transcription first")
            return
        if self._is_running:
            return

        self._ai_btn.configure(state="disabled")
        self._append_log("Starting AI analysis...")
        self._ai_preview.configure(state="normal")
        self._ai_preview.delete("1.0", "end")
        self._ai_preview.configure(state="disabled")

        threading.Thread(target=self._do_ai_summary, daemon=True).start()

    def _do_ai_summary(self):
        try:
            transcript = self._last_transcript_path.read_text(encoding="utf-8")
            model = self._ai_model_var.get()
            self.after(0, self._append_log, f"Using model: {model}")
            self.after(0, self._set_status, "Generating AI summary...")

            ollama_url = self._ollama_url_var.get().strip() or DEFAULT_OLLAMA_URL

            def on_token(token):
                self.after(0, self._ai_append_token, token)

            summary = generate_summary(transcript, model, callback=on_token, base_url=ollama_url)

            output_dir = self._last_transcript_path.parent
            if self._current_campaign:
                output_dir = self._current_campaign.summaries_dir

            summary_name = self._last_transcript_path.stem + "_summary.txt"
            summary_path = save_summary(summary, output_dir / summary_name)
            self._last_summary_path = summary_path

            self.after(0, self._append_log, f"Summary saved: {summary_path}")
            self.after(0, self._set_status, "AI summary generated")
            self.after(0, lambda: self._status.configure(text_color=C_PURPLE))
        except ConnectionError as e:
            self.after(0, self._append_log, f"Error: {e}")
        except Exception as e:
            self.after(0, self._append_log, f"AI Error: {e}")
        finally:
            self.after(0, lambda: self._ai_btn.configure(state="normal"))

    def _ai_append_token(self, token):
        self._ai_preview.configure(state="normal")
        self._ai_preview.insert("end", token)
        self._ai_preview.see("end")
        self._ai_preview.configure(state="disabled")

    # === DISCORD ===

    def _send_discord(self):
        webhook = self._webhook_var.get().strip()
        if not webhook:
            if self._current_campaign and self._current_campaign.discord_webhook:
                webhook = self._current_campaign.discord_webhook
            else:
                self._append_log("No webhook configured for this campaign")
                return

        content = None
        label = ""
        if self._last_summary_path and self._last_summary_path.exists():
            content = self._last_summary_path.read_text(encoding="utf-8")
            label = "summary"
        elif self._last_transcript_path and self._last_transcript_path.exists():
            content = self._last_transcript_path.read_text(encoding="utf-8")
            label = "transcript"
        else:
            self._append_log("No transcript or summary to send")
            return

        self._discord_btn.configure(state="disabled")
        campaign_name = self._current_campaign.name if self._current_campaign else ""

        def do_send():
            try:
                self.after(0, self._set_status, "Sending to Discord...")
                send_to_discord(webhook, content, "Session Summary", campaign_name)
                self.after(0, self._append_log, f"{label.capitalize()} sent to Discord")
                self.after(0, self._set_status, "Sent to Discord")
                self.after(0, lambda: self._status.configure(text_color=C_BLUE))
            except Exception as e:
                self.after(0, self._append_log, f"Error Discord: {e}")
            finally:
                self.after(0, lambda: self._discord_btn.configure(state="normal"))

        threading.Thread(target=do_send, daemon=True).start()


def launch_gui():
    app = WhispererApp()
    app.mainloop()
