#!/usr/bin/env python3
"""
GUI wrapper for the lung lobe segmentation tool.

Provides a user-friendly graphical interface for selecting DICOM folders,
configuring parameters, and viewing results.
"""

import sys
import threading
from pathlib import Path
from tkinter import Tk, Frame, Label, Button, Entry, StringVar, Text, Scrollbar
from tkinter import filedialog, messagebox, ttk
from tkinter.constants import BOTH, EW, END, LEFT, NORMAL, NSEW, RIGHT, W, WORD, Y, DISABLED
import logging

# Import the core pipeline functions
from segment_lobes import (
    discover_series,
    run_pipeline,
    logger as core_logger,
)


class TextHandler(logging.Handler):
    """Custom logging handler that writes to a tkinter Text widget."""

    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.config(state=NORMAL)
        self.text_widget.insert(END, msg + "\n")
        self.text_widget.see(END)
        self.text_widget.config(state=DISABLED)


class SegmentLoblobesGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Lung CT Lobe Segmentation")
        self.root.geometry("800x700")
        self.root.resizable(True, True)

        # Variables
        self.dicom_dir = StringVar()
        self.output_file = StringVar(value="lobe_stats.csv")
        self.threshold = StringVar(value="-910")
        self.series_var = StringVar()
        self.available_series = []
        self.use_gpu = StringVar(value="auto")

        self._build_ui()
        self._setup_logging()

    def _build_ui(self):
        """Build the GUI layout."""
        # Main container with padding
        main_frame = Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=BOTH, expand=True)

        # --- Header ---
        header = Label(
            main_frame,
            text="Lung CT Lobe Segmentation Tool",
            font=("Arial", 16, "bold"),
        )
        header.grid(row=0, column=0, columnspan=3, pady=(0, 20))

        # --- Input Section ---
        Label(main_frame, text="DICOM Folder:", font=("Arial", 10, "bold")).grid(
            row=1, column=0, sticky=W, pady=5
        )
        Entry(main_frame, textvariable=self.dicom_dir, width=50, state=DISABLED).grid(
            row=1, column=1, sticky=EW, pady=5
        )
        Button(main_frame, text="Browse...", command=self._browse_dicom).grid(
            row=1, column=2, padx=(5, 0), pady=5
        )

        # --- Series Selection ---
        Label(main_frame, text="DICOM Series:", font=("Arial", 10, "bold")).grid(
            row=2, column=0, sticky=W, pady=5
        )
        self.series_combo = ttk.Combobox(
            main_frame, textvariable=self.series_var, state=DISABLED, width=47
        )
        self.series_combo.grid(row=2, column=1, sticky=EW, pady=5)
        Button(main_frame, text="Refresh", command=self._refresh_series).grid(
            row=2, column=2, padx=(5, 0), pady=5
        )

        # --- Threshold ---
        Label(main_frame, text="HU Threshold:", font=("Arial", 10, "bold")).grid(
            row=3, column=0, sticky=W, pady=5
        )
        threshold_frame = Frame(main_frame)
        threshold_frame.grid(row=3, column=1, sticky=W, pady=5)
        Entry(threshold_frame, textvariable=self.threshold, width=10).pack(
            side=LEFT, padx=(0, 5)
        )
        Label(threshold_frame, text="(default: -910 for emphysema detection)").pack(
            side=LEFT
        )

        # --- GPU Option ---
        Label(main_frame, text="GPU Acceleration:", font=("Arial", 10, "bold")).grid(
            row=4, column=0, sticky=W, pady=5
        )
        gpu_frame = Frame(main_frame)
        gpu_frame.grid(row=4, column=1, sticky=W, pady=5)
        ttk.Radiobutton(gpu_frame, text="Auto-detect", variable=self.use_gpu, value="auto").pack(
            side=LEFT, padx=(0, 10)
        )
        ttk.Radiobutton(gpu_frame, text="Force GPU", variable=self.use_gpu, value="gpu").pack(
            side=LEFT, padx=(0, 10)
        )
        ttk.Radiobutton(gpu_frame, text="CPU Only", variable=self.use_gpu, value="cpu").pack(
            side=LEFT
        )

        # --- Output Section ---
        Label(main_frame, text="Output CSV:", font=("Arial", 10, "bold")).grid(
            row=5, column=0, sticky=W, pady=5
        )
        Entry(main_frame, textvariable=self.output_file, width=50).grid(
            row=5, column=1, sticky=EW, pady=5
        )
        Button(main_frame, text="Save As...", command=self._browse_output).grid(
            row=5, column=2, padx=(5, 0), pady=5
        )

        # --- Run Button ---
        self.run_btn = Button(
            main_frame,
            text="▶ Run Segmentation",
            command=self._run_segmentation,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 12, "bold"),
            height=2,
        )
        self.run_btn.grid(row=6, column=0, columnspan=3, pady=20, sticky=EW)

        # --- Progress Bar ---
        self.progress = ttk.Progressbar(
            main_frame, mode="indeterminate", length=300
        )
        self.progress.grid(row=7, column=0, columnspan=3, pady=(0, 10), sticky=EW)

        # --- Log Output ---
        Label(main_frame, text="Log Output:", font=("Arial", 10, "bold")).grid(
            row=8, column=0, sticky=W, pady=(10, 5)
        )
        log_frame = Frame(main_frame)
        log_frame.grid(row=9, column=0, columnspan=3, sticky=NSEW)
        
        scrollbar = Scrollbar(log_frame)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        self.log_text = Text(
            log_frame,
            height=15,
            wrap=WORD,
            state=DISABLED,
            yscrollcommand=scrollbar.set,
        )
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)

        # Configure grid weights for responsive layout
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(9, weight=1)

    def _setup_logging(self):
        """Redirect logging to the GUI text widget."""
        text_handler = TextHandler(self.log_text)
        text_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        )
        core_logger.addHandler(text_handler)
        core_logger.setLevel(logging.INFO)

    def _browse_dicom(self):
        """Open a directory browser for DICOM folder selection."""
        directory = filedialog.askdirectory(title="Select DICOM Folder")
        if directory:
            self.dicom_dir.set(directory)
            self._refresh_series()

    def _browse_output(self):
        """Open a file save dialog for output CSV."""
        filename = filedialog.asksaveasfilename(
            title="Save Output CSV As",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=self.output_file.get(),
        )
        if filename:
            self.output_file.set(filename)

    def _refresh_series(self):
        """Scan DICOM folder and populate series dropdown."""
        dicom_path = self.dicom_dir.get()
        if not dicom_path:
            return

        try:
            self._log("Scanning DICOM folder for series...")
            series_map = discover_series(Path(dicom_path))
            self.available_series = list(series_map.keys())

            if not self.available_series:
                messagebox.showwarning(
                    "No Series Found",
                    "No DICOM series detected in the selected folder.",
                )
                self.series_combo["values"] = []
                self.series_combo.config(state=DISABLED)
                return

            self.series_combo["values"] = self.available_series
            self.series_combo.config(state="readonly")

            if len(self.available_series) == 1:
                self.series_var.set(self.available_series[0])
                self._log(f"Single series detected: {self.available_series[0]}")
            else:
                self.series_var.set(self.available_series[0])
                self._log(
                    f"Found {len(self.available_series)} series. Please select one."
                )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to scan DICOM folder:\n{e}")
            self._log(f"ERROR: {e}")

    def _log(self, message):
        """Append a message to the log text widget."""
        self.log_text.config(state=NORMAL)
        self.log_text.insert(END, message + "\n")
        self.log_text.see(END)
        self.log_text.config(state=DISABLED)

    def _validate_inputs(self):
        """Validate user inputs before running."""
        if not self.dicom_dir.get():
            messagebox.showerror("Error", "Please select a DICOM folder.")
            return False

        if not Path(self.dicom_dir.get()).is_dir():
            messagebox.showerror("Error", "Selected DICOM path is not a valid directory.")
            return False

        if not self.series_var.get():
            messagebox.showerror("Error", "Please select a DICOM series.")
            return False

        if not self.output_file.get():
            messagebox.showerror("Error", "Please specify an output CSV file.")
            return False

        try:
            float(self.threshold.get())
        except ValueError:
            messagebox.showerror("Error", "HU threshold must be a number.")
            return False

        return True

    def _run_segmentation(self):
        """Execute the segmentation pipeline in a background thread."""
        if not self._validate_inputs():
            return

        # Disable UI during processing
        self.run_btn.config(state=DISABLED, text="⏳ Processing...")
        self.progress.start()

        # Run pipeline in a separate thread to avoid blocking the GUI
        thread = threading.Thread(target=self._run_pipeline_thread, daemon=True)
        thread.start()

    def _run_pipeline_thread(self):
        """Background thread for running the segmentation pipeline."""
        try:
            # Parse GPU setting
            gpu_setting = self.use_gpu.get()
            use_gpu = None if gpu_setting == "auto" else (gpu_setting == "gpu")

            # Run the pipeline
            run_pipeline(
                dicom_dir=Path(self.dicom_dir.get()),
                output_csv=Path(self.output_file.get()),
                threshold_hu=float(self.threshold.get()),
                series_filter=self.series_var.get(),
                use_gpu=use_gpu,
            )

            # Success
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Success",
                    f"Segmentation completed!\n\nResults saved to:\n{self.output_file.get()}",
                ),
            )

        except Exception as e:
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Error", f"Segmentation failed:\n\n{str(e)}"
                ),
            )
            self._log(f"ERROR: {e}")

        finally:
            # Re-enable UI
            self.root.after(0, self._reset_ui)

    def _reset_ui(self):
        """Reset UI elements after pipeline completion."""
        self.progress.stop()
        self.run_btn.config(state=NORMAL, text="▶ Run Segmentation")


def main():
    root = Tk()
    app = SegmentLoblobesGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
