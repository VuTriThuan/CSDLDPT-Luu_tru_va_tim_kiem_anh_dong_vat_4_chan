"""Tkinter demo; one worker, all Tk updates on the main thread."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from tools.features import b400
from tools.project_paths import B400_OUTPUT_DIR, PROJECT_ROOT
from tools.search.index import SearchIndex
from tools.search.mask_quality import analyze_mask, review_message
from tools.search.query import (load_image, load_mask, create_mask, refine, overlay,
                                retrieve, export_result, output_base, digest)


def fit(width, height, image_width, image_height):
    scale = min(width/image_width, height/image_height)
    w, h = max(1, round(image_width*scale)), max(1, round(image_height*scale))
    return w, h, (width-w)//2, (height-h)//2


class SearchApp:
    def __init__(self, root, feature_dir=B400_OUTPUT_DIR, run_id=None, project_root=PROJECT_ROOT):
        self.root, self.project_root = root, Path(project_root).resolve()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='b400-search')
        self.future = None
        self.index = self.query = self.mask = self.result = None
        self.mask_info, self.history, self.photos = {}, [], []
        self.strokes = self.applied_strokes = None
        self.bbox = self.previous = None
        self.closed = False
        self.controls = []
        root.title('Tìm 5 ảnh động vật — B400')
        root.geometry('1280x940')
        root.minsize(1050, 780)
        toolbar = ttk.Frame(root, padding=8); toolbar.pack(fill='x')
        self.button(toolbar, 'Chọn ảnh JPG/PNG', self.choose_image)
        self.button(toolbar, 'Tạo lại mask tự động', self.generate_mask)
        self.button(toolbar, 'Áp dụng nét tô / GrabCut', self.refine_mask)
        self.button(toolbar, 'Hoàn tác mask', self.undo)
        self.button(toolbar, 'Tìm kiếm', self.search)
        self.button(toolbar, 'Xuất lượt truy vấn', self.export)
        editing = ttk.Frame(root, padding=(8, 0)); editing.pack(fill='x')
        self.mode = tk.StringVar(value='keep')
        for text, mode in [('Tô giữ (xanh)', 'keep'), ('Tô loại (đỏ)', 'remove')]:
            radio = ttk.Radiobutton(editing, text=text, variable=self.mode, value=mode)
            radio.pack(side='left', padx=5); self.controls.append(radio)
        ttk.Label(editing, text='Bán kính bút (pixel ảnh):').pack(side='left', padx=6)
        self.radius = tk.IntVar(value=8)
        spin = ttk.Spinbox(editing, from_=1, to=100, width=5, textvariable=self.radius)
        spin.pack(side='left'); self.controls.append(spin)
        self.include_self = tk.BooleanVar(value=False)
        self.include_self_button = ttk.Checkbutton(editing, text='Hiện cả ảnh trùng truy vấn',
                                                  variable=self.include_self, command=self.clear_results)
        self.include_self_button.pack(side='left', padx=14)
        self.controls.append(self.include_self_button)
        ttk.Label(root, text='Chọn ảnh để tự tạo mask; kiểm tra overlay, tô vùng giữ/loại rồi áp dụng GrabCut. '
                  'Các hình xem trước giữ tỉ lệ.').pack(anchor='w', padx=12, pady=4)
        self.mask_review = tk.StringVar(value='Chưa có mask. Chọn ảnh để tự tạo mask.')
        ttk.Label(root, textvariable=self.mask_review, wraplength=1180).pack(anchor='w', padx=12)
        views = ttk.Frame(root, padding=8); views.pack(fill='both', expand=True)
        left = ttk.LabelFrame(views, text='Ảnh gốc — tô sửa mask'); left.pack(side='left', fill='both', expand=True)
        self.canvas = tk.Canvas(left, width=650, height=330, bg='#232730', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self.redraw())
        self.canvas.bind('<ButtonPress-1>', self.begin)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.end)
        previews = ttk.Frame(views); previews.pack(side='right', fill='y', padx=(8, 0))
        self.mask_view = self.preview(previews, 'Mask 0/255')
        self.overlay_view = self.preview(previews, 'Overlay — nền tô đỏ')
        results = ttk.LabelFrame(root, text='Top 5 tệp ảnh — khoảng cách nhỏ đứng trước', padding=5)
        results.pack(fill='x', padx=8)
        self.other_image_button = ttk.Button(results, text='Chọn ảnh khác', command=self.choose_image)
        self.other_image_button.grid(row=0, column=0, columnspan=5, sticky='e', pady=(0, 4))
        self.controls.append(self.other_image_button)
        self.reference_mask_button = ttk.Button(results, text='Dùng mask đã lưu trong CSDL', command=self.choose_reference_mask)
        self.reference_mask_button.grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 4))
        self.controls.append(self.reference_mask_button)
        self.cards = []
        for i in range(5):
            card = ttk.Frame(results); card.grid(row=1, column=i, sticky='nsew', padx=3)
            results.columnconfigure(i, weight=1, uniform='hits')
            picture = ttk.Label(card, anchor='center'); picture.pack(fill='x')
            text = ttk.Label(card, text=f'#{i+1} —', wraplength=230, justify='center', anchor='center')
            text.pack(fill='x')
            action = ttk.Button(card, text='Xem đóng góp / validity', command=lambda n=i: self.show_hit(n))
            action.pack(fill='x', pady=3); self.controls.append(action)
            self.cards.append((picture, text))
        details = ttk.Notebook(root); details.pack(fill='both', expand=True, padx=8, pady=6)
        detail_frame = ttk.Frame(details); details.add(detail_frame, text='Mask / vùng tự động / đóng góp / chất lượng')
        self.detail = scrolledtext.ScrolledText(detail_frame, height=8, wrap='word', font=('Menlo', 10))
        self.detail.pack(fill='both', expand=True)
        vector_frame = ttk.Frame(details); details.add(vector_frame, text='Vector theo khối và validity')
        selectors = ttk.Frame(vector_frame); selectors.pack(fill='x')
        self.variant = tk.StringVar(value='original'); self.block = tk.StringVar(value='C1')
        for variable, values in [(self.variant, ['original', 'flipped']), (self.block, [b[0] for b in b400.BLOCKS])]:
            combo = ttk.Combobox(selectors, state='readonly', values=values, textvariable=variable, width=18)
            combo.pack(side='left', padx=4)
            combo.bind('<<ComboboxSelected>>', lambda e: self.show_vector())
        self.vector_text = scrolledtext.ScrolledText(vector_frame, height=8, font=('Menlo', 10))
        self.vector_text.pack(fill='both', expand=True)
        footer = ttk.Frame(root, padding=8); footer.pack(fill='x')
        self.progress = ttk.Progressbar(footer, mode='indeterminate', length=130); self.progress.pack(side='right')
        self.status = tk.StringVar(value='Đang nạp CSDL…')
        ttk.Label(footer, textvariable=self.status, wraplength=1050).pack(side='left', fill='x', expand=True)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.start(lambda: SearchIndex(feature_dir, run_id, self.project_root), self.loaded_index, 'Đang kiểm tra và nạp vector SQLite…')

    def button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=command)
        button.pack(side='left', padx=3)
        self.controls.append(button)

    def preview(self, parent, title):
        frame = ttk.LabelFrame(parent, text=title); frame.pack(pady=2)
        view = ttk.Label(frame, anchor='center', width=42); view.pack()
        return view

    def busy(self):
        return self.future is not None

    def start(self, action, done, status):
        if self.busy() or self.closed:
            return False
        self.status.set(status)
        for control in self.controls:
            control.state(['disabled'])
        self.progress.start(12)
        self.done = done
        self.future = self.executor.submit(action)
        self.root.after(60, self.poll)
        return True

    def poll(self):
        if self.closed:
            return
        if not self.future.done():
            self.root.after(60, self.poll)
            return
        future, done = self.future, self.done
        self.future = None
        self.progress.stop()
        for control in self.controls:
            control.state(['!disabled'])
        try:
            done(future.result())
        except Exception as exc:
            self.status.set(f'Lỗi: {exc}')
            messagebox.showerror('Không thể xử lý', str(exc), parent=self.root)

    def loaded_index(self, index):
        self.index = index
        self.status.set(f'Đã nạp đủ {len(index.records)} tệp; mỗi tệp được xét riêng. '
                        f'Run {index.run["id"][:12]}. Chọn ảnh truy vấn.')

    def choose_image(self):
        if self.busy(): return
        path = filedialog.askopenfilename(parent=self.root, filetypes=[('Ảnh JPG/PNG', '*.jpg *.jpeg *.png')])
        if path:
            self.start(lambda: load_image(path), self.set_query, 'Đang đọc ảnh truy vấn…')

    def clear_results(self):
        self.result = None
        for i, (picture, label) in enumerate(self.cards):
            picture.configure(image=''); picture.image = None
            label.configure(text=f'#{i+1} —')
        self.detail.delete('1.0', 'end'); self.vector_text.delete('1.0', 'end')

    def set_query(self, query):
        self.query, self.mask = query, None
        self.bbox, self.history, self.mask_info = None, [], {}
        self.previous = None
        self.mode.set('keep')
        self.include_self.set(False)
        self.variant.set('original'); self.block.set('C1')
        self.strokes = np.full(query.rgb.shape[:2], 255, np.uint8)
        self.applied_strokes = self.strokes.copy()
        self.clear_results()
        self.mask_view.configure(image=''); self.mask_view.image = None
        self.overlay_view.configure(image=''); self.overlay_view.image = None
        self.redraw()
        self.mask_review.set('Đang tạo mask tự động…')
        self.auto_mask()

    def auto_mask(self):
        if self.busy() or self.query is None: return
        if self.index is not None and any(row['sha256'] == self.query.sha256 for row in self.index.records):
            self.choose_reference_mask()
        else:
            self.generate_mask()

    def choose_reference_mask(self):
        if self.busy() or self.query is None or self.index is None: return
        matches = sorted((row for row in self.index.records if row['sha256'] == self.query.sha256),
                         key=lambda row: (row['filename'], row['mask_path']))
        if not matches:
            messagebox.showinfo('Chưa có mask cho ảnh này', 'Ảnh này chưa có cùng SHA-256 trong CSDL. Có thể tạo lại mask tự động rồi tô sửa.', parent=self.root)
            return
        row, rgb = matches[0], self.query.rgb.copy()
        def work():
            mask, info = load_mask(self.index.root/row['mask_path'], rgb)
            if info['input_sha256'] != row['mask_sha256']:
                raise ValueError('Mask CSDL đã thay đổi so với run B400')
            info.update(method='stored_mask_for_identical_source_sha256', reference_run_id=self.index.run['id'])
            return mask, info
        self.start(work, self.set_mask, 'Đang đọc mask đã lưu cho đúng hash ảnh…')

    def checkpoint(self):
        self.history.append((None if self.mask is None else self.mask.copy(), self.strokes.copy(),
                             self.applied_strokes.copy(), dict(self.mask_info), self.bbox))
        self.history = self.history[-20:]

    def set_mask(self, values):
        mask, info = values
        self.checkpoint()
        self.mask, self.mask_info = mask, info
        self.bbox = tuple(info['initial_bbox']) if info.get('initial_bbox') is not None else None
        self.strokes.fill(255); self.applied_strokes = self.strokes.copy()
        self.clear_results(); self.redraw()
        self.mask_review.set(review_message(info['diagnostics']))
        self.status.set('Đã có mask. Xem overlay và sửa phần thiếu/thừa trước khi tìm kiếm.')

    def generate_mask(self):
        if self.busy() or self.query is None: return
        rgb = self.query.rgb.copy()
        self.start(lambda: create_mask(rgb), self.set_mask, 'Đang tạo mask GrabCut tự động trên kích thước gốc…')

    def refine_mask(self):
        if self.busy() or self.mask is None: return
        if np.array_equal(self.strokes, self.applied_strokes):
            messagebox.showinfo('Chưa có nét tô mới', 'Tô vùng cần giữ hoặc loại trước khi áp dụng GrabCut.', parent=self.root)
            return
        rgb, mask, strokes, old_info = self.query.rgb.copy(), self.mask.copy(), self.strokes.copy(), dict(self.mask_info)
        def work():
            new_mask, seconds = refine(rgb, mask, strokes)
            edits = list(old_info.get('edits', []))
            edits.append(dict(strokes_pixels_sha256=digest(strokes.tobytes()), keep_pixels=int((strokes == 1).sum()),
                              remove_pixels=int((strokes == 0).sum()), seconds=seconds))
            return new_mask, dict(old_info, mask_seconds=old_info.get('mask_seconds', 0.)+seconds, edits=edits,
                                  diagnostics=analyze_mask(new_mask, old_info.get('initial_bbox')))
        def done(values):
            self.checkpoint()
            self.mask, self.mask_info = values
            self.applied_strokes = self.strokes.copy()
            self.clear_results(); self.redraw()
            self.mask_review.set(review_message(self.mask_info['diagnostics']))
            self.status.set('Đã áp dụng nét tô. Mask sẵn sàng tìm kiếm.')
        self.start(work, done, 'Đang tinh chỉnh mask bằng vùng giữ/loại…')

    def undo(self):
        if self.busy() or not self.history: return
        self.mask, self.strokes, self.applied_strokes, self.mask_info, self.bbox = self.history.pop()
        self.clear_results(); self.redraw()
        self.mask_review.set(review_message(self.mask_info['diagnostics']) if self.mask is not None else 'Chưa có mask. Bấm “Tạo lại mask tự động”.')
        self.status.set('Đã hoàn tác chỉnh mask.')

    def point(self, event):
        if self.query is None: return None
        h, w = self.query.rgb.shape[:2]
        rw, rh, ox, oy = fit(max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height()), w, h)
        if not (ox <= event.x < ox+rw and oy <= event.y < oy+rh): return None
        return min(w-1, int((event.x-ox)*w/rw)), min(h-1, int((event.y-oy)*h/rh))

    def begin(self, event):
        if self.busy(): return
        point = self.point(event)
        if point is None: return
        if self.mask is not None:
            self.checkpoint(); self.previous = point; self.paint(point)

    def paint(self, point):
        try:
            radius = min(100, max(1, self.radius.get()))
        except tk.TclError:
            radius = 8
        label = 1 if self.mode.get() == 'keep' else 0
        cv2.line(self.strokes, self.previous, point, label, 2*radius+1)
        cv2.circle(self.strokes, point, radius, label, -1)
        self.previous = point
        if self.result is not None: self.clear_results()
        self.redraw()
        self.status.set('Nét tô chưa áp dụng. Bấm “Áp dụng nét tô / GrabCut” trước khi tìm kiếm.')

    def drag(self, event):
        if self.busy(): return
        point = self.point(event)
        if point is None: return
        if self.previous is not None:
            self.paint(point)

    def end(self, event):
        self.previous = None

    def photo(self, widget, array, size):
        image = Image.fromarray(array)
        image.thumbnail(size, Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image)
        widget.configure(image=photo); widget.image = photo

    def redraw(self):
        if self.query is None or self.closed: return
        rgb = self.query.rgb.copy()
        if self.strokes is not None:
            rgb[self.strokes == 1] = [0, 230, 90]
            rgb[self.strokes == 0] = [255, 50, 50]
        h, w = rgb.shape[:2]
        rw, rh, ox, oy = fit(max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height()), w, h)
        self.canvas_photo = ImageTk.PhotoImage(Image.fromarray(rgb).resize((rw, rh), Image.Resampling.LANCZOS))
        self.canvas.delete('all'); self.canvas.create_image(ox, oy, image=self.canvas_photo, anchor='nw')
        if self.bbox:
            x, y, bw, bh = self.bbox
            self.canvas.create_rectangle(ox+x*rw/w, oy+y*rh/h, ox+(x+bw)*rw/w, oy+(y+bh)*rh/h,
                                         outline='#ffd454', width=2)
        if self.mask is not None:
            self.photo(self.mask_view, self.mask, (300, 150))
            self.photo(self.overlay_view, overlay(self.query.rgb, self.mask), (300, 150))
        else:
            for view in [self.mask_view, self.overlay_view]:
                view.configure(image=''); view.image = None

    def search(self):
        if self.busy() or self.index is None or self.query is None or self.mask is None: return
        if not np.array_equal(self.strokes, self.applied_strokes):
            messagebox.showinfo('Nét tô chưa áp dụng', 'Áp dụng GrabCut hoặc hoàn tác nét tô trước khi tìm kiếm.', parent=self.root)
            return
        query, mask, info, strokes = self.query, self.mask.copy(), dict(self.mask_info), self.strokes.copy()
        exclude_self = not self.include_self.get()
        self.start(lambda: retrieve(self.index, query, mask, info, exclude_self=exclude_self, strokes=strokes), self.show_result,
                   'Đang trích B400 gốc/lật và tìm 5 tệp ảnh…')

    def show_result(self, result):
        self.clear_results()
        self.result = result
        for hit in result['results']:
            picture, label = self.cards[hit['rank']-1]
            with Image.open(Path(result['output_directory'])/hit['artifact_image']) as image:
                self.photo(picture, np.array(image.convert('RGB')), (215, 115))
            label.configure(text=f'#{hit["rank"]} {hit["filename"]}\n{hit["label"]}\n'
                                 f'D = {hit["distance"]:.6f} | {hit["orientation"]}')
        self.status.set(f'Trả {result["returned"]}/5; loại {result["excluded_self_files"]} tệp trùng hash truy vấn. '
                        f'Đặc trưng {result["timings"]["feature_seconds"]:.3f}s; tìm kiếm '
                        f'{result["timings"]["search_seconds"]:.4f}s. '+(result['shortfall_reason'] or 'Đã lưu lượt truy vấn.'))
        if result['results']: self.show_hit(0)
        self.show_vector()

    def show_hit(self, position):
        if self.result is None or position >= len(self.result['results']): return
        hit = self.result['results'][position]
        details = dict(filename=hit['filename'], label_metadata=hit['label'], distance=hit['distance'],
                       orientation=hit['orientation'], group_distances=hit['group_distances'],
                       contribution_sum=sum(hit['group_distances'].values()),
                       candidate_valid_dimensions=sum(hit['validity']), candidate_validity=hit['validity'],
                       candidate_quality=hit['quality'], candidate_source_flags=hit['source_flags'],
                       query_quality=self.result['query']['quality'][hit['orientation']], query_mask=self.result['query']['mask'],
                       mask_diagnostics=self.result['query'].get('mask_diagnostics'))
        self.detail.delete('1.0', 'end')
        self.detail.insert('1.0', json.dumps(details, ensure_ascii=False, indent=2))

    def show_vector(self):
        if self.result is None: return
        variant = self.variant.get()
        _, start, stop = next(b for b in b400.BLOCKS if b[0] == self.block.get())
        with np.load(Path(self.result['output_directory'])/'vectors.npz', allow_pickle=False) as arrays:
            names = b400.feature_names()
            rows = ['index  name                          raw          normalized    valid']
            for i in range(start, stop):
                rows.append(f'{i:3d}  {names[i]:30s} {arrays[variant+"_raw"][i]:12.6g} '
                            f'{arrays[variant+"_normalized"][i]:12.6g} {bool(arrays[variant+"_validity"][i])}')
        self.vector_text.delete('1.0', 'end'); self.vector_text.insert('1.0', '\n'.join(rows))

    def export(self):
        if self.busy() or self.result is None: return
        base = output_base(self.project_root)
        path = filedialog.askdirectory(parent=self.root, initialdir=base, title='Xuất vào thư mục trong outputs/search/')
        if path:
            result = self.result
            self.start(lambda: export_result(result, path, self.project_root),
                       lambda p: self.status.set(f'Đã xuất đầy đủ ảnh, mask, vector, cấu hình và top 5: {p}'), 'Đang xuất lượt truy vấn…')

    def close(self):
        if self.busy():
            messagebox.showinfo('Đang xử lý', 'Chờ tác vụ hiện tại hoàn tất rồi đóng cửa sổ.', parent=self.root)
            return
        self.closed = True
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def launch(feature_dir=B400_OUTPUT_DIR, run_id=None, project_root=PROJECT_ROOT):
    cv2.setNumThreads(1)
    root = tk.Tk()
    SearchApp(root, feature_dir, run_id, project_root)
    root.mainloop()
