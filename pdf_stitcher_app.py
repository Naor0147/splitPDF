"""
PDF Stitcher Desktop App

Dependencies:
    pip install customtkinter pymupdf pillow
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import List

import customtkinter as ctk
import fitz
from PIL import Image, ImageDraw, ImageFont
from tkinter import filedialog, messagebox


@dataclass(frozen=True)
class ProcessingRequest:
    pdf_path: Path
    pages_per_image: int
    layout_direction: str
    horizontal_order: str
    show_page_numbers: bool
    page_number_font_size: int
    output_root: Path
    remove_large_spaces: bool
    cleanup_strength: float


class PDFStitcherApp(ctk.CTk):
    """A minimalist desktop app that converts PDF pages into stitched images."""

    MIN_PAGES_PER_IMAGE = 1
    MAX_PAGES_PER_IMAGE = 20
    DEFAULT_PAGES_PER_IMAGE = 2
    DEFAULT_LAYOUT_DIRECTION = "Vertical"
    VALID_LAYOUT_DIRECTIONS = {"Vertical", "Horizontal"}
    DEFAULT_HORIZONTAL_ORDER = "Right to left"
    VALID_HORIZONTAL_ORDERS = {"Left to right", "Right to left"}
    DEFAULT_SHOW_PAGE_NUMBERS = True
    MIN_PAGE_NUMBER_FONT_SIZE = 8
    MAX_PAGE_NUMBER_FONT_SIZE = 36
    DEFAULT_PAGE_NUMBER_FONT_SIZE = 12
    DEFAULT_OUTPUT_ROOT = Path("F:/splitPdf")

    def __init__(self) -> None:
        super().__init__()

        self.title("PDF Stitcher")
        self.geometry("860x640")
        self.minsize(520, 420)
        self.resizable(True, True)

        self.default_output_root = self._resolve_default_output_root()
        self.settings_path = self._resolve_settings_path()

        self.pdf_path_var = ctk.StringVar(value="No PDF selected")
        self.pages_per_image_var = ctk.StringVar(value=str(self.DEFAULT_PAGES_PER_IMAGE))
        self.layout_direction_var = ctk.StringVar(value=self.DEFAULT_LAYOUT_DIRECTION)
        self.horizontal_order_var = ctk.StringVar(value=self.DEFAULT_HORIZONTAL_ORDER)
        self.show_page_numbers_var = ctk.BooleanVar(value=self.DEFAULT_SHOW_PAGE_NUMBERS)
        self.page_number_font_size_var = ctk.DoubleVar(value=float(self.DEFAULT_PAGE_NUMBER_FONT_SIZE))
        self.custom_output_var = ctk.BooleanVar(value=False)
        self.output_root_var = ctk.StringVar(value=str(self.default_output_root))
        self.default_output_note_var = ctk.StringVar(
            value=f"Default output folder: {self.default_output_root}"
        )
        self.remove_spaces_var = ctk.BooleanVar(value=False)
        self.cleanup_strength_var = ctk.DoubleVar(value=50.0)
        self.cleanup_strength_label_var = ctk.StringVar(value="Whitespace cleanup strength: 50%")
        self.page_number_font_size_label_var = ctk.StringVar(
            value=f"Page number size: {self.DEFAULT_PAGE_NUMBER_FONT_SIZE}"
        )
        self.status_var = ctk.StringVar(value="Select a PDF and choose your settings.")

        self.is_processing = False
        self.render_scale = 2.0

        self._load_settings()
        self._sync_setting_labels()
        self._build_ui()
        self._setup_setting_traces()
        self.bind("<Configure>", self._on_window_resize)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        card_color = "#1C1C1E"
        primary_text = "#F5F5F7"
        secondary_text = "#A1A1AA"

        main_frame = ctk.CTkScrollableFrame(
            self,
            corner_radius=18,
            fg_color="#101114",
            scrollbar_button_color="#2F2F32",
            scrollbar_button_hover_color="#3A3A3C",
        )
        main_frame.grid(row=0, column=0, sticky="nsew", padx=24, pady=(24, 12))
        main_frame.grid_columnconfigure(0, weight=1)

        header_frame = ctk.CTkFrame(main_frame, corner_radius=0, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=30, pady=(28, 18))
        header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            header_frame,
            text="PDF to Combined Images",
            font=("Segoe UI", 28, "bold"),
            text_color=primary_text,
        )
        title_label.grid(row=0, column=0, sticky="w")

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Minimal workflow. Clean output. Fast conversion.",
            font=("Segoe UI", 14),
            text_color=secondary_text,
        )
        subtitle_label.grid(row=1, column=0, sticky="w", pady=(6, 0))

        select_card = ctk.CTkFrame(main_frame, corner_radius=16, fg_color=card_color)
        select_card.grid(row=1, column=0, sticky="ew", padx=30, pady=(0, 16))
        select_card.grid_columnconfigure(1, weight=1)

        select_label = ctk.CTkLabel(
            select_card,
            text="Input PDF",
            font=("Segoe UI", 16, "bold"),
            text_color=primary_text,
        )
        select_label.grid(row=0, column=0, sticky="w", padx=20, pady=(18, 10), columnspan=2)

        select_button = ctk.CTkButton(
            select_card,
            text="Choose PDF",
            width=140,
            height=38,
            corner_radius=12,
            fg_color="#0A84FF",
            hover_color="#0071E3",
            font=("Segoe UI", 14, "bold"),
            command=self.choose_pdf,
        )
        select_button.grid(row=1, column=0, padx=20, pady=(0, 18), sticky="w")

        self.file_value_label = ctk.CTkLabel(
            select_card,
            textvariable=self.pdf_path_var,
            anchor="w",
            justify="left",
            wraplength=540,
            font=("Segoe UI", 13),
            text_color=secondary_text,
        )
        self.file_value_label.grid(row=1, column=1, sticky="ew", padx=(12, 20), pady=(0, 18))

        settings_card = ctk.CTkFrame(main_frame, corner_radius=16, fg_color=card_color)
        settings_card.grid(row=2, column=0, sticky="ew", padx=30, pady=(0, 16))
        settings_card.grid_columnconfigure(0, weight=1)

        settings_label = ctk.CTkLabel(
            settings_card,
            text="Settings",
            font=("Segoe UI", 16, "bold"),
            text_color=primary_text,
        )
        settings_label.grid(row=0, column=0, sticky="w", padx=20, pady=(18, 12))

        pages_label = ctk.CTkLabel(
            settings_card,
            text="Pages per image",
            font=("Segoe UI", 13),
            text_color=secondary_text,
        )
        pages_label.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))

        pages_row = ctk.CTkFrame(settings_card, fg_color="transparent")
        pages_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 14))
        pages_row.grid_columnconfigure(0, weight=1)

        self.pages_slider = ctk.CTkSlider(
            pages_row,
            from_=self.MIN_PAGES_PER_IMAGE,
            to=self.MAX_PAGES_PER_IMAGE,
            number_of_steps=self.MAX_PAGES_PER_IMAGE - self.MIN_PAGES_PER_IMAGE,
            command=self._on_slider_change,
            button_color="#0A84FF",
            button_hover_color="#0071E3",
            progress_color="#0A84FF",
        )
        self.pages_slider.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.pages_slider.set(self._parse_pages_per_image(self.pages_per_image_var.get()))

        self.pages_entry = ctk.CTkEntry(
            pages_row,
            textvariable=self.pages_per_image_var,
            width=72,
            height=34,
            justify="center",
            font=("Segoe UI", 13),
        )
        self.pages_entry.grid(row=0, column=1, sticky="e")
        self.pages_entry.bind("<Return>", self._on_pages_entry_commit)
        self.pages_entry.bind("<FocusOut>", self._on_pages_entry_commit)

        direction_label = ctk.CTkLabel(
            settings_card,
            text="Layout direction",
            font=("Segoe UI", 13),
            text_color=secondary_text,
        )
        direction_label.grid(row=3, column=0, sticky="w", padx=20, pady=(2, 8))

        direction_segmented = ctk.CTkSegmentedButton(
            settings_card,
            values=["Vertical", "Horizontal"],
            variable=self.layout_direction_var,
            height=36,
            fg_color="#2C2C2E",
            selected_color="#0A84FF",
            selected_hover_color="#0071E3",
            unselected_color="#2C2C2E",
            unselected_hover_color="#3A3A3C",
            font=("Segoe UI", 13, "bold"),
        )
        direction_segmented.grid(row=4, column=0, sticky="w", padx=20, pady=(0, 18))
        direction_segmented.set(self.DEFAULT_LAYOUT_DIRECTION)

        horizontal_order_label = ctk.CTkLabel(
            settings_card,
            text="Horizontal order",
            font=("Segoe UI", 13),
            text_color=secondary_text,
        )
        horizontal_order_label.grid(row=5, column=0, sticky="w", padx=20, pady=(0, 8))

        horizontal_order_segmented = ctk.CTkSegmentedButton(
            settings_card,
            values=["Right to left", "Left to right"],
            variable=self.horizontal_order_var,
            height=34,
            fg_color="#2C2C2E",
            selected_color="#0A84FF",
            selected_hover_color="#0071E3",
            unselected_color="#2C2C2E",
            unselected_hover_color="#3A3A3C",
            font=("Segoe UI", 12, "bold"),
        )
        horizontal_order_segmented.grid(row=6, column=0, sticky="w", padx=20, pady=(0, 18))
        horizontal_order_segmented.set(self.DEFAULT_HORIZONTAL_ORDER)

        self.page_numbers_switch = ctk.CTkSwitch(
            settings_card,
            text="Show page numbers",
            variable=self.show_page_numbers_var,
            onvalue=True,
            offvalue=False,
            font=("Segoe UI", 13),
            command=self._on_show_page_numbers_toggle,
        )
        self.page_numbers_switch.grid(row=7, column=0, sticky="w", padx=20, pady=(0, 18))

        page_number_size_row = ctk.CTkFrame(settings_card, fg_color="transparent")
        page_number_size_row.grid(row=8, column=0, sticky="ew", padx=20, pady=(0, 18))
        page_number_size_row.grid_columnconfigure(0, weight=1)

        self.page_number_font_size_label = ctk.CTkLabel(
            page_number_size_row,
            textvariable=self.page_number_font_size_label_var,
            font=("Segoe UI", 12),
            text_color=secondary_text,
        )
        self.page_number_font_size_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.page_number_font_size_slider = ctk.CTkSlider(
            page_number_size_row,
            from_=self.MIN_PAGE_NUMBER_FONT_SIZE,
            to=self.MAX_PAGE_NUMBER_FONT_SIZE,
            number_of_steps=self.MAX_PAGE_NUMBER_FONT_SIZE - self.MIN_PAGE_NUMBER_FONT_SIZE,
            variable=self.page_number_font_size_var,
            command=self._on_page_number_font_size_change,
            progress_color="#0A84FF",
            button_color="#0A84FF",
            button_hover_color="#0071E3",
        )
        self.page_number_font_size_slider.grid(row=1, column=0, sticky="ew")
        self.page_number_font_size_slider.set(self.page_number_font_size_var.get())

        self.remove_spaces_switch = ctk.CTkSwitch(
            settings_card,
            text="Remove large empty spaces",
            variable=self.remove_spaces_var,
            onvalue=True,
            offvalue=False,
            font=("Segoe UI", 13),
            command=self._on_remove_spaces_toggle,
        )
        self.remove_spaces_switch.grid(row=9, column=0, sticky="w", padx=20, pady=(0, 18))

        cleanup_strength_row = ctk.CTkFrame(settings_card, fg_color="transparent")
        cleanup_strength_row.grid(row=10, column=0, sticky="ew", padx=20, pady=(0, 18))
        cleanup_strength_row.grid_columnconfigure(0, weight=1)

        self.cleanup_strength_label = ctk.CTkLabel(
            cleanup_strength_row,
            textvariable=self.cleanup_strength_label_var,
            font=("Segoe UI", 12),
            text_color=secondary_text,
        )
        self.cleanup_strength_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.cleanup_strength_slider = ctk.CTkSlider(
            cleanup_strength_row,
            from_=0,
            to=100,
            number_of_steps=20,
            variable=self.cleanup_strength_var,
            command=self._on_cleanup_strength_change,
            progress_color="#0A84FF",
            button_color="#0A84FF",
            button_hover_color="#0071E3",
        )
        self.cleanup_strength_slider.grid(row=1, column=0, sticky="ew")
        self.cleanup_strength_slider.set(self.cleanup_strength_var.get())

        output_card = ctk.CTkFrame(main_frame, corner_radius=16, fg_color=card_color)
        output_card.grid(row=3, column=0, sticky="ew", padx=30, pady=(0, 16))
        output_card.grid_columnconfigure(0, weight=1)

        output_label = ctk.CTkLabel(
            output_card,
            text="Output",
            font=("Segoe UI", 16, "bold"),
            text_color=primary_text,
        )
        output_label.grid(row=0, column=0, sticky="w", padx=20, pady=(18, 12))

        self.custom_output_switch = ctk.CTkSwitch(
            output_card,
            text="Use custom destination",
            variable=self.custom_output_var,
            onvalue=True,
            offvalue=False,
            font=("Segoe UI", 13),
            command=self._toggle_output_controls,
        )
        self.custom_output_switch.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        default_output_note = ctk.CTkLabel(
            output_card,
            textvariable=self.default_output_note_var,
            font=("Segoe UI", 12),
            text_color=secondary_text,
        )
        default_output_note.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 8))

        output_row = ctk.CTkFrame(output_card, fg_color="transparent")
        output_row.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 18))
        output_row.grid_columnconfigure(0, weight=1)

        self.output_entry = ctk.CTkEntry(
            output_row,
            textvariable=self.output_root_var,
            state="disabled",
            height=34,
            font=("Segoe UI", 13),
        )
        self.output_entry.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.output_entry.bind("<Return>", self._on_output_entry_commit)
        self.output_entry.bind("<FocusOut>", self._on_output_entry_commit)

        self.output_button = ctk.CTkButton(
            output_row,
            text="Browse",
            width=110,
            height=34,
            corner_radius=10,
            state="disabled",
            font=("Segoe UI", 13, "bold"),
            command=self.choose_output_dir,
        )
        self.output_button.grid(row=0, column=1, sticky="e")

        footer_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        footer_frame.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 24))
        footer_frame.grid_columnconfigure(0, weight=1)

        self.process_button = ctk.CTkButton(
            footer_frame,
            text="Generate Images",
            height=42,
            corner_radius=12,
            fg_color="#1D1D1F",
            hover_color="#2F2F32",
            font=("Segoe UI", 14, "bold"),
            command=self.start_processing,
        )
        self.process_button.grid(row=0, column=0, sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(
            footer_frame,
            height=10,
            corner_radius=6,
            progress_color="#0A84FF",
            fg_color="#2C2C2E",
        )
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(12, 8))
        self.progress_bar.set(0.0)

        status_label = ctk.CTkLabel(
            footer_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 12),
            text_color=secondary_text,
            anchor="w",
        )
        status_label.grid(row=2, column=0, sticky="ew")

        self._toggle_output_controls()
        self._on_remove_spaces_toggle()
        self._on_show_page_numbers_toggle()

    def _on_window_resize(self, _event=None) -> None:
        dynamic_wrap = max(300, self.winfo_width() - 340)
        self.file_value_label.configure(wraplength=dynamic_wrap)

    @classmethod
    def _resolve_default_output_root(cls) -> Path:
        return cls.DEFAULT_OUTPUT_ROOT

    @staticmethod
    def _resolve_settings_path() -> Path:
        app_data_root = Path(os.environ.get("APPDATA", str(Path.home())))
        return app_data_root / "PDFStitcher" / "settings.json"

    def _load_settings(self) -> None:
        if not self.settings_path.exists():
            return

        try:
            raw_text = self.settings_path.read_text(encoding="utf-8")
            data = json.loads(raw_text)
        except (OSError, json.JSONDecodeError):
            return

        pages_value = data.get("pages_per_image")
        if pages_value is not None:
            self.pages_per_image_var.set(
                str(self._parse_pages_per_image(str(pages_value)))
            )

        layout_direction = data.get("layout_direction")
        if layout_direction in self.VALID_LAYOUT_DIRECTIONS:
            self.layout_direction_var.set(layout_direction)

        horizontal_order = data.get("horizontal_order")
        if horizontal_order in self.VALID_HORIZONTAL_ORDERS:
            self.horizontal_order_var.set(horizontal_order)

        show_page_numbers = data.get("show_page_numbers")
        if isinstance(show_page_numbers, bool):
            self.show_page_numbers_var.set(show_page_numbers)

        font_size_value = data.get("page_number_font_size")
        if isinstance(font_size_value, (int, float)):
            clamped_size = int(
                min(
                    max(int(round(font_size_value)), self.MIN_PAGE_NUMBER_FONT_SIZE),
                    self.MAX_PAGE_NUMBER_FONT_SIZE,
                )
            )
            self.page_number_font_size_var.set(float(clamped_size))

        custom_output = data.get("custom_output")
        if isinstance(custom_output, bool):
            self.custom_output_var.set(custom_output)

        output_root = data.get("output_root")
        if isinstance(output_root, str) and output_root.strip():
            self.output_root_var.set(output_root.strip())

        remove_large_spaces = data.get("remove_large_spaces")
        if isinstance(remove_large_spaces, bool):
            self.remove_spaces_var.set(remove_large_spaces)

        cleanup_strength = data.get("cleanup_strength")
        if isinstance(cleanup_strength, (int, float)):
            clamped_strength = min(max(float(cleanup_strength), 0.0), 100.0)
            self.cleanup_strength_var.set(clamped_strength)

    def _sync_setting_labels(self) -> None:
        self._set_cleanup_strength(self.cleanup_strength_var.get())
        self._set_page_number_font_size(self.page_number_font_size_var.get())

    def _setup_setting_traces(self) -> None:
        self.layout_direction_var.trace_add("write", lambda *_: self._persist_settings())
        self.horizontal_order_var.trace_add("write", lambda *_: self._persist_settings())

    def _persist_settings(self) -> None:
        font_size = int(round(self.page_number_font_size_var.get()))
        font_size = min(
            max(font_size, self.MIN_PAGE_NUMBER_FONT_SIZE),
            self.MAX_PAGE_NUMBER_FONT_SIZE,
        )
        data = {
            "pages_per_image": self._parse_pages_per_image(self.pages_per_image_var.get()),
            "layout_direction": self._validated_layout_direction(),
            "horizontal_order": self._validated_horizontal_order(),
            "show_page_numbers": bool(self.show_page_numbers_var.get()),
            "page_number_font_size": font_size,
            "custom_output": bool(self.custom_output_var.get()),
            "output_root": self.output_root_var.get().strip(),
            "remove_large_spaces": bool(self.remove_spaces_var.get()),
            "cleanup_strength": float(self.cleanup_strength_var.get()),
        }

        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _set_cleanup_strength(self, value: float) -> None:
        rounded_value = int(round(value))
        self.cleanup_strength_var.set(float(rounded_value))
        self.cleanup_strength_label_var.set(f"Whitespace cleanup strength: {rounded_value}%")

    def _set_page_number_font_size(self, value: float) -> None:
        rounded_value = int(round(value))
        clamped_value = min(
            max(rounded_value, self.MIN_PAGE_NUMBER_FONT_SIZE),
            self.MAX_PAGE_NUMBER_FONT_SIZE,
        )
        self.page_number_font_size_var.set(float(clamped_value))
        self.page_number_font_size_label_var.set(f"Page number size: {clamped_value}")

    @classmethod
    def _clamp_pages_per_image(cls, value: int) -> int:
        return min(max(value, cls.MIN_PAGES_PER_IMAGE), cls.MAX_PAGES_PER_IMAGE)

    @classmethod
    def _parse_pages_per_image(cls, raw_value: str) -> int:
        try:
            parsed_value = int(raw_value.strip())
        except (AttributeError, ValueError):
            parsed_value = cls.DEFAULT_PAGES_PER_IMAGE
        return cls._clamp_pages_per_image(parsed_value)

    def _validated_layout_direction(self) -> str:
        current_direction = self.layout_direction_var.get()
        if current_direction not in self.VALID_LAYOUT_DIRECTIONS:
            return self.DEFAULT_LAYOUT_DIRECTION
        return current_direction

    def _validated_horizontal_order(self) -> str:
        current_order = self.horizontal_order_var.get()
        if current_order not in self.VALID_HORIZONTAL_ORDERS:
            return self.DEFAULT_HORIZONTAL_ORDER
        return current_order

    def choose_pdf(self) -> None:
        selected_file = filedialog.askopenfilename(
            title="Select PDF",
            filetypes=[("PDF files", "*.pdf")],
        )
        if selected_file:
            self.pdf_path_var.set(selected_file)
            self.status_var.set("PDF selected. Ready to generate images.")

    def choose_output_dir(self) -> None:
        selected_dir = filedialog.askdirectory(title="Choose output destination")
        if selected_dir:
            self.output_root_var.set(selected_dir)
            self._persist_settings()

    def _toggle_output_controls(self) -> None:
        is_custom = self.custom_output_var.get()
        self.output_entry.configure(state="normal" if is_custom else "disabled")
        self.output_button.configure(state="normal" if is_custom else "disabled")
        if not is_custom:
            self.output_root_var.set(str(self.default_output_root))
        self._persist_settings()

    def _on_remove_spaces_toggle(self) -> None:
        slider_state = "normal" if self.remove_spaces_var.get() else "disabled"
        self.cleanup_strength_slider.configure(state=slider_state)
        self._persist_settings()

    def _on_show_page_numbers_toggle(self) -> None:
        slider_state = "normal" if self.show_page_numbers_var.get() else "disabled"
        self.page_number_font_size_slider.configure(state=slider_state)
        self._persist_settings()

    def _on_cleanup_strength_change(self, value: float) -> None:
        self._set_cleanup_strength(value)
        self._persist_settings()

    def _on_page_number_font_size_change(self, value: float) -> None:
        self._set_page_number_font_size(value)
        self._persist_settings()

    def _on_slider_change(self, value: float) -> None:
        rounded_value = self._clamp_pages_per_image(int(round(value)))
        self.pages_per_image_var.set(str(rounded_value))
        self._persist_settings()

    def _on_pages_entry_commit(self, _event=None) -> None:
        validated_value = self._parse_pages_per_image(self.pages_per_image_var.get())
        self.pages_per_image_var.set(str(validated_value))
        self.pages_slider.set(validated_value)
        self._persist_settings()

    def _on_output_entry_commit(self, _event=None) -> None:
        self.output_root_var.set(self.output_root_var.get().strip())
        self._persist_settings()

    def start_processing(self) -> None:
        if self.is_processing:
            return

        pdf_path_text = self.pdf_path_var.get().strip()
        pdf_path = Path(pdf_path_text)
        if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
            messagebox.showerror("Invalid Input", "Please select a valid PDF file.")
            return

        self._on_pages_entry_commit()
        pages_per_image = self._parse_pages_per_image(self.pages_per_image_var.get())
        layout_direction = self._validated_layout_direction()
        horizontal_order = self._validated_horizontal_order()
        show_page_numbers = self.show_page_numbers_var.get()
        page_number_font_size = int(round(self.page_number_font_size_var.get()))
        page_number_font_size = min(
            max(page_number_font_size, self.MIN_PAGE_NUMBER_FONT_SIZE),
            self.MAX_PAGE_NUMBER_FONT_SIZE,
        )
        remove_large_spaces = self.remove_spaces_var.get()
        cleanup_strength = self.cleanup_strength_var.get() / 100.0

        if self.custom_output_var.get():
            custom_output_root = self.output_root_var.get().strip()
            if not custom_output_root:
                messagebox.showerror("Output Required", "Please choose a custom destination folder.")
                return
            output_root = Path(custom_output_root).expanduser()
        else:
            output_root = self.default_output_root

        try:
            output_root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            messagebox.showerror(
                "Output Error",
                f"Could not create output folder:\n{output_root}\n\n{error}",
            )
            return

        request = ProcessingRequest(
            pdf_path=pdf_path,
            pages_per_image=pages_per_image,
            layout_direction=layout_direction,
            horizontal_order=horizontal_order,
            show_page_numbers=show_page_numbers,
            page_number_font_size=page_number_font_size,
            output_root=output_root,
            remove_large_spaces=remove_large_spaces,
            cleanup_strength=cleanup_strength,
        )

        self.is_processing = True
        self.process_button.configure(state="disabled")
        self.progress_bar.set(0.0)
        self.status_var.set("Processing PDF pages...")

        worker = threading.Thread(
            target=self._process_worker,
            args=(request,),
            daemon=True,
        )
        worker.start()

    def _process_worker(self, request: ProcessingRequest) -> None:
        try:
            output_folder, image_count = self.convert_pdf_to_combined_images(request)
        except Exception as error:
            print(f"Processing failed: {error}")
            print(traceback.format_exc())
            self.after(0, self._on_processing_error, str(error))
            return

        self.after(0, self._on_processing_success, output_folder, image_count)

    def _update_progress(self, value: float, text: str) -> None:
        self.progress_bar.set(value)
        self.status_var.set(text)

    def _on_processing_success(self, output_folder: Path, image_count: int) -> None:
        self.is_processing = False
        self.process_button.configure(state="normal")
        self.progress_bar.set(1.0)
        self.status_var.set(f"Completed. {image_count} image(s) saved.")
        self.open_output_folder(output_folder)

        message = (
            f"Successfully created {image_count} image(s).\n\n"
            f"Saved to:\n{output_folder}"
        )
        messagebox.showinfo("Done", message)

    def _on_processing_error(self, error_message: str) -> None:
        self.is_processing = False
        self.process_button.configure(state="normal")
        self.status_var.set("Processing failed. Please review the error and try again.")
        messagebox.showerror("Processing Error", error_message)

    @staticmethod
    def open_output_folder(folder_path: Path) -> None:
        if not folder_path.exists():
            return

        try:
            if hasattr(os, "startfile"):
                os.startfile(str(folder_path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder_path)], check=False)
            else:
                subprocess.run(["xdg-open", str(folder_path)], check=False)
        except Exception as error:
            print(f"Could not open output folder automatically: {error}")

    @staticmethod
    def _build_cleanup_profile(cleanup_strength: float) -> tuple[int, int, int, float]:
        strength = min(max(cleanup_strength, 0.0), 1.0)
        tolerance = int(round(10 + 20 * strength))
        min_empty_run = max(10, int(round(62 - 46 * strength)))
        keep_rows = max(3, int(round(14 - 10 * strength)))
        blank_ratio = max(0.96, min(0.998, 0.998 - 0.03 * strength))
        return tolerance, min_empty_run, keep_rows, blank_ratio

    def remove_large_empty_spaces(self, image: Image.Image, cleanup_strength: float) -> Image.Image:
        tolerance, min_empty_run, keep_rows, blank_ratio = self._build_cleanup_profile(cleanup_strength)
        background_color = self._estimate_background_color(image)
        cropped_image = self._crop_to_content_bounds(image, background_color, tolerance=tolerance)

        refined_background = self._estimate_background_color(cropped_image)
        compacted_image = self._compress_blank_rows(
            cropped_image,
            refined_background,
            tolerance=tolerance,
            min_empty_run=min_empty_run,
            keep_rows=keep_rows,
            blank_ratio=blank_ratio,
        )
        cropped_image.close()
        return compacted_image

    @staticmethod
    def _estimate_background_color(image: Image.Image) -> tuple[int, int, int]:
        width, height = image.size
        pixels = image.load()
        sample_points = [
            (0, 0),
            (width - 1, 0),
            (0, height - 1),
            (width - 1, height - 1),
            (width // 2, 0),
            (width // 2, height - 1),
            (0, height // 2),
            (width - 1, height // 2),
        ]

        red_total = 0
        green_total = 0
        blue_total = 0
        for x_coordinate, y_coordinate in sample_points:
            red, green, blue = pixels[x_coordinate, y_coordinate]
            red_total += red
            green_total += green
            blue_total += blue

        sample_count = len(sample_points)
        return (
            red_total // sample_count,
            green_total // sample_count,
            blue_total // sample_count,
        )

    @staticmethod
    def _is_near_background(
        pixel: tuple[int, int, int],
        background_color: tuple[int, int, int],
        tolerance: int,
    ) -> bool:
        return (
            abs(pixel[0] - background_color[0]) <= tolerance
            and abs(pixel[1] - background_color[1]) <= tolerance
            and abs(pixel[2] - background_color[2]) <= tolerance
        )

    def _crop_to_content_bounds(
        self,
        image: Image.Image,
        background_color: tuple[int, int, int],
        tolerance: int,
    ) -> Image.Image:
        width, height = image.size
        pixels = image.load()
        row_foreground_counts = [0] * height
        col_foreground_counts = [0] * width

        for y_coordinate in range(height):
            for x_coordinate in range(width):
                pixel = pixels[x_coordinate, y_coordinate]
                if not self._is_near_background(pixel, background_color, tolerance):
                    row_foreground_counts[y_coordinate] += 1
                    col_foreground_counts[x_coordinate] += 1

        min_foreground_in_row = max(1, width // 500)
        min_foreground_in_col = max(1, height // 500)

        top = next(
            (
                index
                for index, count in enumerate(row_foreground_counts)
                if count >= min_foreground_in_row
            ),
            None,
        )
        if top is None:
            return image.copy()

        bottom = next(
            (
                index
                for index in range(height - 1, -1, -1)
                if row_foreground_counts[index] >= min_foreground_in_row
            ),
            top,
        )
        left = next(
            (
                index
                for index, count in enumerate(col_foreground_counts)
                if count >= min_foreground_in_col
            ),
            0,
        )
        right = next(
            (
                index
                for index in range(width - 1, -1, -1)
                if col_foreground_counts[index] >= min_foreground_in_col
            ),
            left,
        )

        return image.crop((left, top, right + 1, bottom + 1))

    def _compress_blank_rows(
        self,
        image: Image.Image,
        background_color: tuple[int, int, int],
        tolerance: int,
        min_empty_run: int,
        keep_rows: int,
        blank_ratio: float,
    ) -> Image.Image:
        width, height = image.size
        pixels = image.load()
        blank_row_flags = [False] * height
        min_background_pixels = max(1, int(width * blank_ratio))

        for y_coordinate in range(height):
            background_pixels = 0
            for x_coordinate in range(width):
                pixel = pixels[x_coordinate, y_coordinate]
                if self._is_near_background(pixel, background_color, tolerance):
                    background_pixels += 1
            blank_row_flags[y_coordinate] = background_pixels >= min_background_pixels

        segments: List[tuple[str, int, int, int]] = []
        row_index = 0
        while row_index < height:
            start = row_index
            is_blank = blank_row_flags[row_index]
            while row_index < height and blank_row_flags[row_index] == is_blank:
                row_index += 1

            end = row_index
            run_height = end - start
            if is_blank and run_height >= min_empty_run:
                segments.append(("spacer", start, end, min(keep_rows, run_height)))
            else:
                segments.append(("keep", start, end, run_height))

        output_height = max(1, sum(segment[3] for segment in segments))
        output_image = Image.new("RGB", (width, output_height), background_color)

        cursor_y = 0
        for segment_type, start, end, segment_height in segments:
            if segment_type == "keep":
                image_slice = image.crop((0, start, width, end))
                output_image.paste(image_slice, (0, cursor_y))
                image_slice.close()
            cursor_y += segment_height

        return output_image

    @staticmethod
    def _load_page_number_font(font_size: int) -> ImageFont.ImageFont:
        requested_size = max(6, font_size)
        candidates = []
        if sys.platform.startswith("win"):
            windows_fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
            candidates.extend(
                [
                    windows_fonts / "segoeui.ttf",
                    windows_fonts / "arial.ttf",
                ]
            )

        candidates.extend(["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"])

        for candidate in candidates:
            try:
                return ImageFont.truetype(str(candidate), size=requested_size)
            except OSError:
                continue

        return ImageFont.load_default()

    @staticmethod
    def _draw_page_number(image: Image.Image, page_number: int, font_size: int) -> None:
        draw = ImageDraw.Draw(image)
        font = PDFStitcherApp._load_page_number_font(font_size)
        text = str(page_number)
        try:
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            text_width = right - left
            text_height = bottom - top
        except AttributeError:
            text_width, text_height = draw.textsize(text, font=font)

        margin = 6
        x_pos = max(0, image.width - text_width - margin)
        y_pos = max(0, margin)
        if y_pos + text_height > image.height:
            y_pos = max(0, image.height - text_height - margin)

        draw.text((x_pos, y_pos), text, fill="black", font=font)

    def convert_pdf_to_combined_images(self, request: ProcessingRequest) -> tuple[Path, int]:
        if request.layout_direction not in self.VALID_LAYOUT_DIRECTIONS:
            raise ValueError(f"Unsupported layout direction: {request.layout_direction}")

        output_folder = request.output_root / request.pdf_path.stem
        output_folder.mkdir(parents=True, exist_ok=True)

        with fitz.open(request.pdf_path) as document:
            total_pages = document.page_count
            if total_pages == 0:
                raise ValueError("The selected PDF has no pages.")

            total_output_images = (total_pages + request.pages_per_image - 1) // request.pages_per_image
            generated_count = 0

            for image_index, first_page in enumerate(
                range(0, total_pages, request.pages_per_image),
                start=1,
            ):
                last_page = min(first_page + request.pages_per_image, total_pages)
                page_images: List[Image.Image] = []
                stitched_image: Image.Image | None = None

                try:
                    for page_number in range(first_page, last_page):
                        page = document.load_page(page_number)
                        pixmap = page.get_pixmap(
                            matrix=fitz.Matrix(self.render_scale, self.render_scale),
                            alpha=False,
                        )

                        # Render each PDF page to a Pillow image before stitching.
                        rendered_image = Image.frombytes(
                            "RGB",
                            (pixmap.width, pixmap.height),
                            pixmap.samples,
                        )
                        if request.remove_large_spaces:
                            processed_image = self.remove_large_empty_spaces(
                                rendered_image,
                                request.cleanup_strength,
                            )
                            rendered_image.close()
                        else:
                            processed_image = rendered_image

                        if request.show_page_numbers:
                            self._draw_page_number(
                                processed_image,
                                page_number + 1,
                                request.page_number_font_size,
                            )
                        page_images.append(processed_image)

                    stitched_image = self.stitch_images(
                        page_images,
                        request.layout_direction,
                        request.horizontal_order,
                    )
                    output_image_path = output_folder / f"{request.pdf_path.stem}_{image_index:03d}.png"
                    stitched_image.save(output_image_path, format="PNG")

                    generated_count += 1
                    progress_value = image_index / total_output_images
                    status_text = f"Creating image {image_index} of {total_output_images}..."
                    self.after(0, self._update_progress, progress_value, status_text)
                finally:
                    if stitched_image is not None:
                        stitched_image.close()
                    for image in page_images:
                        image.close()

        return output_folder, generated_count

    @staticmethod
    def stitch_images(
        images: List[Image.Image],
        layout_direction: str,
        horizontal_order: str,
    ) -> Image.Image:
        if not images:
            raise ValueError("No images available for stitching.")

        if layout_direction == "Horizontal":
            if horizontal_order not in PDFStitcherApp.VALID_HORIZONTAL_ORDERS:
                horizontal_order = PDFStitcherApp.DEFAULT_HORIZONTAL_ORDER

            ordered_images = images
            if horizontal_order == "Right to left":
                ordered_images = list(reversed(images))

            combined_width = sum(image.width for image in ordered_images)
            combined_height = max(image.height for image in ordered_images)
            combined_image = Image.new("RGB", (combined_width, combined_height), "white")

            current_x = 0
            for image in ordered_images:
                y_offset = (combined_height - image.height) // 2
                combined_image.paste(image, (current_x, y_offset))
                current_x += image.width

            return combined_image

        combined_width = max(image.width for image in images)
        combined_height = sum(image.height for image in images)
        combined_image = Image.new("RGB", (combined_width, combined_height), "white")

        current_y = 0
        for image in images:
            x_offset = (combined_width - image.width) // 2
            combined_image.paste(image, (x_offset, current_y))
            current_y += image.height

        return combined_image


def main() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = PDFStitcherApp()
    app.mainloop()


if __name__ == "__main__":
    main()
