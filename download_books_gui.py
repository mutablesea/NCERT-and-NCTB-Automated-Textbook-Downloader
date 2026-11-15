#!/usr/bin/env python3
"""
NCERT & NCTB Textbook Downloader — Tkinter GUI
==============================================
Interactive desktop interface for browsing, filtering, selecting,
and downloading NCERT and NCTB textbooks.
"""

import os
import re
import sys
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from concurrent.futures import ThreadPoolExecutor, as_completed

from download_books import (
    DEFAULT_ACADEMIC_YEAR,
    get_ncert_books,
    get_nctb_books,
    scan_existing_ncert_codes,
    download_ncert_book,
    download_nctb_book,
    filter_books_by_classes,
)


class _QueueWriter:
    """Redirect stdout/stderr writes into a thread-safe Tkinter log queue."""

    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue

    def write(self, msg: str):
        if msg:
            self.log_queue.put(('log', msg))

    def flush(self):
        pass


class TextbookDownloaderGUI:
    """Main Tkinter application window."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("NCERT & NCTB Textbook Downloader")
        self.root.geometry("980x720")
        self.root.minsize(820, 600)

        self.books = []
        self.filtered_books = []
        self.log_queue = queue.Queue()
        self.is_busy = False

        self._build_ui()
        self._poll_queue()

    def _build_ui(self):
        pad = {'padx': 8, 'pady': 4}

        # Top Configuration Frame
        cfg = ttk.LabelFrame(self.root, text="Configuration & Filters", padding=10)
        cfg.pack(fill='x', **pad)

        # Row 0: Source, Academic Year, Workers
        ttk.Label(cfg, text="Source:").grid(row=0, column=0, sticky='w', padx=4, pady=3)
        self.source_var = tk.StringVar(value='all')
        src_cb = ttk.Combobox(cfg, textvariable=self.source_var, values=['all', 'ncert', 'nctb'], state='readonly', width=10)
        src_cb.grid(row=0, column=1, sticky='w', padx=4, pady=3)

        ttk.Label(cfg, text="NCTB Academic Year:").grid(row=0, column=2, sticky='w', padx=4, pady=3)
        self.ay_var = tk.StringVar(value=DEFAULT_ACADEMIC_YEAR)
        ttk.Entry(cfg, textvariable=self.ay_var, width=12).grid(row=0, column=3, sticky='w', padx=4, pady=3)

        ttk.Label(cfg, text="Workers:").grid(row=0, column=4, sticky='w', padx=4, pady=3)
        self.workers_var = tk.IntVar(value=6)
        ttk.Spinbox(cfg, from_=1, to=16, textvariable=self.workers_var, width=5).grid(row=0, column=5, sticky='w', padx=4, pady=3)

        self.voc_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(cfg, text="Include NCERT Vocational", variable=self.voc_var).grid(row=0, column=6, sticky='w', padx=8, pady=3)

        self.web_fallback_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg, text="Web Search Fallback", variable=self.web_fallback_var).grid(row=0, column=7, sticky='w', padx=4, pady=3)

        # Row 1: Classes, NCTB Stage, Output Dir
        ttk.Label(cfg, text="Classes (e.g. 1 2 9 or all):").grid(row=1, column=0, sticky='w', padx=4, pady=3)
        self.classes_var = tk.StringVar(value='all')
        ttk.Entry(cfg, textvariable=self.classes_var, width=16).grid(row=1, column=1, sticky='w', padx=4, pady=3)

        ttk.Label(cfg, text="NCTB Stage:").grid(row=1, column=2, sticky='w', padx=4, pady=3)
        self.stage_var = tk.StringVar(value='All')
        stage_opts = ['All', 'Pre-Primary', 'Primary', 'Secondary', 'Higher Secondary', 'Ibtedayi', 'Dakhil', 'Vocational', 'Ethnic Minority']
        ttk.Combobox(cfg, textvariable=self.stage_var, values=stage_opts, state='readonly', width=18).grid(row=1, column=3, sticky='w', padx=4, pady=3)

        ttk.Label(cfg, text="Output Folder:").grid(row=1, column=4, sticky='w', padx=4, pady=3)
        self.output_var = tk.StringVar(value=os.path.abspath('.'))
        ttk.Entry(cfg, textvariable=self.output_var, width=28).grid(row=1, column=5, columnspan=2, sticky='ew', padx=4, pady=3)
        ttk.Button(cfg, text="Browse...", command=self._choose_output).grid(row=1, column=7, sticky='w', padx=4, pady=3)

        cfg.columnconfigure(6, weight=1)

        # Action Bar
        act = ttk.Frame(self.root)
        act.pack(fill='x', **pad)

        self.load_btn = ttk.Button(act, text="Load / Refresh Book List", command=self._start_load_books)
        self.load_btn.pack(side='left', padx=4)

        ttk.Button(act, text="Select All", command=self._select_all).pack(side='left', padx=4)
        ttk.Button(act, text="Clear Selection", command=self._clear_selection).pack(side='left', padx=4)

        ttk.Label(act, text="Search:").pack(side='left', padx=(16, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *_: self._apply_search_filter())
        ttk.Entry(act, textvariable=self.search_var, width=24).pack(side='left', padx=4)

        self.dl_btn = ttk.Button(act, text="Download Selected", command=self._start_download)
        self.dl_btn.pack(side='right', padx=4)

        # Book List Frame
        list_frame = ttk.LabelFrame(self.root, text="Available Books (Select specific books or click Select All)", padding=6)
        list_frame.pack(fill='both', expand=True, **pad)

        self.book_listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED, font=('Menlo', 11))
        sb_y = ttk.Scrollbar(list_frame, orient='vertical', command=self.book_listbox.yview)
        sb_x = ttk.Scrollbar(list_frame, orient='horizontal', command=self.book_listbox.xview)
        self.book_listbox.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        self.book_listbox.grid(row=0, column=0, sticky='nsew')
        sb_y.grid(row=0, column=1, sticky='ns')
        sb_x.grid(row=1, column=0, sticky='ew')
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        # Progress & Log Frame
        prog_frame = ttk.LabelFrame(self.root, text="Progress & Logs", padding=6)
        prog_frame.pack(fill='both', expand=False, **pad)

        self.progress = ttk.Progressbar(prog_frame, mode='determinate')
        self.progress.pack(fill='x', padx=4, pady=(0, 4))

        self.status_var = tk.StringVar(value="Ready. Click 'Load / Refresh Book List' to fetch catalog.")
        ttk.Label(prog_frame, textvariable=self.status_var).pack(anchor='w', padx=4, pady=(0, 4))

        self.log_text = scrolledtext.ScrolledText(prog_frame, height=10, state='disabled', font=('Menlo', 10))
        self.log_text.pack(fill='both', expand=True, padx=4, pady=2)

    def _choose_output(self):
        chosen = filedialog.askdirectory(initialdir=self.output_var.get())
        if chosen:
            self.output_var.set(chosen)

    def _append_log(self, text: str):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', text)
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def _set_busy(self, busy: bool):
        self.is_busy = busy
        state = 'disabled' if busy else 'normal'
        self.load_btn.configure(state=state)
        self.dl_btn.configure(state=state)

    def _parse_classes(self):
        raw = self.classes_var.get().strip().lower()
        if not raw or raw == 'all':
            return None
        nums = [int(x) for x in re.findall(r'\d+', raw)]
        return nums if nums else None

    def _start_load_books(self):
        if self.is_busy:
            return
        self._set_busy(True)
        self.status_var.set("Crawling book catalog...")
        source = self.source_var.get()
        ay = self.ay_var.get().strip() or DEFAULT_ACADEMIC_YEAR
        classes = self._parse_classes()
        stage = self.stage_var.get()
        inc_voc = self.voc_var.get()
        web_fb = self.web_fallback_var.get()

        def worker():
            old_out, old_err = sys.stdout, sys.stderr
            writer = _QueueWriter(self.log_queue)
            sys.stdout = writer
            sys.stderr = writer
            try:
                ncert = get_ncert_books(include_vocational=inc_voc) if source in ('all', 'ncert') else []
                nctb = get_nctb_books(academic_year=ay, allow_web_search=web_fb) if source in ('all', 'nctb') else []
                if stage != 'All':
                    nctb = [b for b in nctb if b['stage'] == stage]
                ncert, nctb = filter_books_by_classes(ncert, nctb, classes)
                self.log_queue.put(('loaded', ncert + nctb))
            except Exception as e:
                self.log_queue.put(('log', f"[!] Error loading catalog: {e}\n"))
                self.log_queue.put(('loaded', []))
            finally:
                sys.stdout, sys.stderr = old_out, old_err

        threading.Thread(target=worker, daemon=True).start()

    def _format_book_row(self, b: dict) -> str:
        if b['source'] == 'NCERT':
            return f"[NCERT | Class {b['class_num']} | {b['subject']} | {b['lang']}] {b['title']}"
        return f"[NCTB AY{b.get('academic_year', '')} | {b['stage']} | {b['class_folder']} | {b['lang']} | {b['subject']}] {b['title']}"

    def _apply_search_filter(self):
        q = self.search_var.get().strip().lower()
        self.book_listbox.delete(0, 'end')
        self.filtered_books = []
        for b in self.books:
            row = self._format_book_row(b)
            if not q or q in row.lower():
                self.filtered_books.append(b)
                self.book_listbox.insert('end', row)

    def _select_all(self):
        self.book_listbox.select_set(0, 'end')

    def _clear_selection(self):
        self.book_listbox.select_clear(0, 'end')

    def _start_download(self):
        if self.is_busy:
            return
        sel = self.book_listbox.curselection()
        if not sel:
            messagebox.showinfo("No Selection", "Please select one or more books from the list (or click 'Select All').")
            return

        selected_books = [self.filtered_books[i] for i in sel]
        base_dir = os.path.abspath(self.output_var.get() or '.')
        workers = max(1, int(self.workers_var.get() or 6))
        web_fb = self.web_fallback_var.get()

        self._set_busy(True)
        self.progress.configure(maximum=len(selected_books), value=0)
        self.status_var.set(f"Downloading {len(selected_books)} book(s)...")

        def worker():
            old_out, old_err = sys.stdout, sys.stderr
            writer = _QueueWriter(self.log_queue)
            sys.stdout = writer
            sys.stderr = writer
            ok, fail = 0, 0
            try:
                os.makedirs(base_dir, exist_ok=True)
                existing_codes = scan_existing_ncert_codes(os.path.join(base_dir, 'NCERT'))
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    futures = {}
                    for b in selected_books:
                        if b['source'] == 'NCERT':
                            futures[ex.submit(download_ncert_book, b, base_dir, existing_codes)] = b['title']
                        else:
                            futures[ex.submit(download_nctb_book, b, base_dir, web_fb)] = b['title']
                    done_count = 0
                    for fut in as_completed(futures):
                        done_count += 1
                        try:
                            if fut.result():
                                ok += 1
                            else:
                                fail += 1
                        except Exception as e:
                            print(f"[!] Error: {e}")
                            fail += 1
                        self.log_queue.put(('progress', done_count, len(selected_books)))
            finally:
                sys.stdout, sys.stderr = old_out, old_err
                self.log_queue.put(('done', ok, fail))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                kind = item[0]
                if kind == 'log':
                    self._append_log(item[1])
                elif kind == 'loaded':
                    self.books = item[1]
                    self._apply_search_filter()
                    self.status_var.set(f"Loaded {len(self.books)} book(s).")
                    self._set_busy(False)
                elif kind == 'progress':
                    done_c, total_c = item[1], item[2]
                    self.progress.configure(value=done_c)
                    self.status_var.set(f"Progress: {done_c} / {total_c}")
                elif kind == 'done':
                    ok, fail = item[1], item[2]
                    self.status_var.set(f"Completed! Success: {ok}, Failed: {fail}")
                    self._set_busy(False)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)


def main():
    root = tk.Tk()
    TextbookDownloaderGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
