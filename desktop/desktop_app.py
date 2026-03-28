"""
desktop_app.py
--------------
Offline Tkinter desktop application for SBDPS.
Designed for rural/low-connectivity environments.

Run:
    python desktop/desktop_app.py
"""

import sys
import os
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from models.predictor import DiseasePredictor
    PREDICTOR_AVAILABLE = True
except FileNotFoundError:
    PREDICTOR_AVAILABLE = False


# ------------------------------------------------------------------ #
#  Colours                                                             #
# ------------------------------------------------------------------ #
COLORS = {
    'bg': '#f5f7fa',
    'primary': '#1a6b9a',
    'primary_dark': '#0d4f74',
    'white': '#ffffff',
    'border': '#dee2e6',
    'text': '#2c3e50',
    'text_light': '#6c757d',
    'red': '#dc3545',
    'yellow': '#ffc107',
    'green': '#28a745',
    'red_bg': '#fff5f5',
    'yellow_bg': '#fffdf0',
    'green_bg': '#f0fff4',
}

FONT_TITLE = ('Segoe UI', 18, 'bold')
FONT_SUBTITLE = ('Segoe UI', 11)
FONT_LABEL = ('Segoe UI', 10, 'bold')
FONT_BODY = ('Segoe UI', 10)
FONT_SMALL = ('Segoe UI', 9)
FONT_BTN = ('Segoe UI', 11, 'bold')


class SBDPSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('SBDPS – Disease Prediction System')
        self.geometry('900x700')
        self.minsize(800, 600)
        self.configure(bg=COLORS['bg'])

        self.predictor = None
        self.selected_symptoms: set = set()
        self.symptom_vars: dict = {}

        self._build_ui()
        self._load_predictor_async()

    # ----------------------------------------------------------------
    # UI Layout
    # ----------------------------------------------------------------
    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=COLORS['primary'], pady=12)
        header.pack(fill='x')
        tk.Label(header, text='🩺 SBDPS – Symptom-Based Disease Prediction System',
                 font=FONT_TITLE, bg=COLORS['primary'], fg='white').pack()
        tk.Label(header, text='42 Diseases · 132 Symptoms · English & Hinglish Support',
                 font=FONT_SMALL, bg=COLORS['primary'], fg='#cde').pack()

        # Disclaimer
        disc = tk.Frame(self, bg='#fff3cd', bd=1, relief='solid')
        disc.pack(fill='x', padx=10, pady=(8, 4))
        tk.Label(disc, text='⚠️ For informational purposes only. Not a substitute for medical advice.',
                 font=FONT_SMALL, bg='#fff3cd', fg='#856404', pady=4).pack()

        # Main PanedWindow
        paned = ttk.PanedWindow(self, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=10, pady=6)

        # Left: Input
        left = tk.Frame(paned, bg=COLORS['white'], bd=1, relief='solid')
        paned.add(left, weight=1)
        self._build_input_panel(left)

        # Right: Results
        right = tk.Frame(paned, bg=COLORS['white'], bd=1, relief='solid')
        paned.add(right, weight=1)
        self._build_results_panel(right)

        # Status bar
        self.status_var = tk.StringVar(value='Loading model…')
        status = tk.Label(self, textvariable=self.status_var,
                          font=FONT_SMALL, bg=COLORS['border'], fg=COLORS['text_light'],
                          anchor='w', padx=10, pady=3)
        status.pack(fill='x', side='bottom')

    def _build_input_panel(self, parent):
        tk.Label(parent, text='Describe Your Symptoms', font=FONT_LABEL,
                 bg=COLORS['white'], fg=COLORS['primary']).pack(anchor='w', padx=12, pady=(10, 0))

        # Notebook tabs
        nb = ttk.Notebook(parent)
        nb.pack(fill='both', expand=True, padx=8, pady=6)

        # Tab 1: Free Text
        tab_text = tk.Frame(nb, bg=COLORS['white'])
        nb.add(tab_text, text='📝 Free Text')
        tk.Label(tab_text, text='Type in English or Hinglish:', font=FONT_BODY,
                 bg=COLORS['white']).pack(anchor='w', padx=8, pady=(8, 2))
        self.text_input = scrolledtext.ScrolledText(tab_text, height=8, font=FONT_BODY,
                                                    wrap='word', relief='solid', bd=1)
        self.text_input.pack(fill='both', expand=True, padx=8, pady=(0, 4))
        tk.Label(tab_text, text='💡 e.g. "mujhe bukhar hai aur sar dard ho raha hai"',
                 font=FONT_SMALL, bg=COLORS['white'], fg=COLORS['text_light']).pack(anchor='w', padx=8)

        # Tab 2: Symptom Checklist
        tab_check = tk.Frame(nb, bg=COLORS['white'])
        nb.add(tab_check, text='☑️ Checklist')
        search_frame = tk.Frame(tab_check, bg=COLORS['white'])
        search_frame.pack(fill='x', padx=8, pady=(8, 4))
        tk.Label(search_frame, text='Search:', font=FONT_BODY, bg=COLORS['white']).pack(side='left')
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self._filter_symptoms)
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, font=FONT_BODY,
                                relief='solid', bd=1)
        search_entry.pack(side='left', fill='x', expand=True, padx=(4, 0))

        # Scrollable symptom list
        canvas_frame = tk.Frame(tab_check, bg=COLORS['white'])
        canvas_frame.pack(fill='both', expand=True, padx=8)
        self.canvas = tk.Canvas(canvas_frame, bg=COLORS['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient='vertical', command=self.canvas.yview)
        self.symptom_frame = tk.Frame(self.canvas, bg=COLORS['bg'])
        self.symptom_frame.bind('<Configure>',
                                lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.create_window((0, 0), window=self.symptom_frame, anchor='nw')
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.nb = nb  # store reference

        # Predict Button
        btn_frame = tk.Frame(parent, bg=COLORS['white'])
        btn_frame.pack(fill='x', padx=8, pady=8)
        self.predict_btn = tk.Button(
            btn_frame, text='🔍  Predict Disease',
            font=FONT_BTN, bg=COLORS['primary'], fg='white',
            activebackground=COLORS['primary_dark'], activeforeground='white',
            relief='flat', cursor='hand2', padx=16, pady=10,
            command=self._run_prediction
        )
        self.predict_btn.pack(fill='x')

        self.selected_label = tk.Label(parent, text='', font=FONT_SMALL,
                                       bg=COLORS['white'], fg=COLORS['text_light'])
        self.selected_label.pack()

    def _build_results_panel(self, parent):
        tk.Label(parent, text='Prediction Results', font=FONT_LABEL,
                 bg=COLORS['white'], fg=COLORS['primary']).pack(anchor='w', padx=12, pady=(10, 4))

        self.results_text = scrolledtext.ScrolledText(
            parent, font=FONT_BODY, wrap='word', state='disabled',
            relief='solid', bd=1, bg='#fafbfc'
        )
        self.results_text.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        # Configure text tags
        self.results_text.tag_configure('title', font=('Segoe UI', 13, 'bold'), foreground=COLORS['primary'])
        self.results_text.tag_configure('heading', font=('Segoe UI', 11, 'bold'), foreground=COLORS['text'])
        self.results_text.tag_configure('subheading', font=('Segoe UI', 9, 'bold'), foreground=COLORS['text_light'])
        self.results_text.tag_configure('body', font=FONT_BODY)
        self.results_text.tag_configure('red', foreground=COLORS['red'], font=('Segoe UI', 10, 'bold'))
        self.results_text.tag_configure('yellow', foreground='#856404', font=('Segoe UI', 10, 'bold'))
        self.results_text.tag_configure('green', foreground=COLORS['green'], font=('Segoe UI', 10, 'bold'))
        self.results_text.tag_configure('small', font=FONT_SMALL, foreground=COLORS['text_light'])
        self.results_text.tag_configure('separator', foreground=COLORS['border'])

        self._write_results([('Welcome!\n\nDescribe your symptoms in the left panel and click Predict.\n', 'body')])

    # ----------------------------------------------------------------
    # Symptom Checklist Rendering
    # ----------------------------------------------------------------
    def _populate_symptoms(self, symptoms: list):
        for widget in self.symptom_frame.winfo_children():
            widget.destroy()
        self.symptom_vars.clear()

        cols = 2
        for i, sym in enumerate(symptoms):
            var = tk.BooleanVar(value=sym['id'] in self.selected_symptoms)
            self.symptom_vars[sym['id']] = var
            cb = tk.Checkbutton(
                self.symptom_frame, text=sym['label'], variable=var,
                font=FONT_SMALL, bg=COLORS['bg'], anchor='w',
                command=lambda s=sym['id'], v=var: self._toggle_sym(s, v)
            )
            cb.grid(row=i // cols, column=i % cols, sticky='w', padx=6, pady=1)

    def _toggle_sym(self, sym_id, var):
        if var.get():
            self.selected_symptoms.add(sym_id)
        else:
            self.selected_symptoms.discard(sym_id)
        count = len(self.selected_symptoms)
        self.selected_label.config(text=f'{count} symptom{"s" if count != 1 else ""} selected' if count else '')

    def _filter_symptoms(self, *_):
        q = self.search_var.get().lower()
        if self.predictor:
            filtered = [{'id': s, 'label': s.replace('_', ' ').title()}
                        for s in self.predictor.symptoms_list
                        if q in s.replace('_', ' ').lower() or not q]
            self._populate_symptoms(filtered)

    # ----------------------------------------------------------------
    # Async Model Loading
    # ----------------------------------------------------------------
    def _load_predictor_async(self):
        def _load():
            global PREDICTOR_AVAILABLE
            try:
                p = DiseasePredictor()
                self.predictor = p
                syms = [{'id': s, 'label': s.replace('_', ' ').title()} for s in p.symptoms_list]
                self.after(0, lambda: self._populate_symptoms(syms))
                self.after(0, lambda: self.status_var.set(
                    f'Ready · {len(p.label_encoder.classes_)} diseases · {len(p.symptoms_list)} symptoms'))
                PREDICTOR_AVAILABLE = True
            except FileNotFoundError:
                self.after(0, lambda: self.status_var.set(
                    '⚠️ Model not found. Run: python models/train_models.py'))
                PREDICTOR_AVAILABLE = False

        threading.Thread(target=_load, daemon=True).start()

    # ----------------------------------------------------------------
    # Prediction
    # ----------------------------------------------------------------
    def _run_prediction(self):
        if not PREDICTOR_AVAILABLE or not self.predictor:
            messagebox.showerror('Model Not Ready',
                                 'Please run:\n  python models/train_models.py\nfirst.')
            return

        active_tab = self.nb.index(self.nb.select())
        text = self.text_input.get('1.0', 'end').strip() if active_tab == 0 else ''
        structured = list(self.selected_symptoms)

        if not text and not structured:
            messagebox.showwarning('No Input', 'Please describe your symptoms or select from the checklist.')
            return

        self.predict_btn.config(state='disabled', text='Analysing…')
        self.status_var.set('Analysing symptoms…')

        def _predict():
            try:
                result = self.predictor.predict(text=text, structured_symptoms=structured, top_k=3)
                self.after(0, lambda: self._display_results(result))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror('Error', str(e)))
            finally:
                self.after(0, lambda: self.predict_btn.config(state='normal', text='🔍  Predict Disease'))
                self.after(0, lambda: self.status_var.set('Ready'))

        threading.Thread(target=_predict, daemon=True).start()

    def _display_results(self, data):
        lines = []
        nlp = data.get('nlp_result', {})

        if nlp.get('readable'):
            lines.append((f"Language: {nlp.get('language', '').capitalize()}\n", 'subheading'))
            lines.append((f"Symptoms detected: {', '.join(nlp['readable'])}\n\n", 'small'))

        if not data.get('predictions'):
            lines.append(('No predictions found. Please add more symptoms.\n', 'body'))
        else:
            for pred in data['predictions']:
                urgency_tag = pred['urgency']
                lines.append((f"{'─'*50}\n", 'separator'))
                lines.append((f"#{pred['rank']} {pred['disease']}", 'heading'))
                lines.append((f"  ({pred['confidence']}% confidence)\n", 'small'))
                lines.append((f"{pred['urgency_label']}\n\n", urgency_tag))
                lines.append(('Description:\n', 'subheading'))
                lines.append((f"{pred['description']}\n\n", 'body'))
                if pred.get('matched_symptoms'):
                    lines.append(('Matched symptoms: ', 'subheading'))
                    lines.append((', '.join(pred['matched_symptoms']) + '\n\n', 'body'))
                lines.append(('Resources:\n', 'subheading'))
                for v in (pred.get('resources') or {}).values():
                    lines.append((f"  • {v}\n", 'small'))
                lines.append(('\n', 'body'))

        self._write_results(lines)

    def _write_results(self, lines):
        self.results_text.config(state='normal')
        self.results_text.delete('1.0', 'end')
        for text, tag in lines:
            self.results_text.insert('end', text, tag)
        self.results_text.config(state='disabled')
        self.results_text.see('1.0')


# ------------------------------------------------------------------ #
#  Entry point                                                         #
# ------------------------------------------------------------------ #
if __name__ == '__main__':
    app = SBDPSApp()
    app.mainloop()
