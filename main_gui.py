import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import os
import sys
import threading
import shutil
import asyncio
import glob
import zipfile
import requests
import subprocess
import re
import queue 
from collections import Counter

from renpy_core_engine import RenpyV15CoreEngine

APP_VERSION = "V15.0"
APP_CODENAME = "终极降维堡垒版"

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception: pass

def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

class RenpyTranslatorV15:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Ren'Py 汉化大师 {APP_VERSION} ({APP_CODENAME})")
        self.root.geometry("850x900")
        
        self.pause_event = threading.Event()
        self.pause_event.set()
        
        self.active_tasks = {}
        self.failed_sniper_lines = []
        
        self.ui_queue = queue.Queue()
        self.root.after(100, self._process_ui_queue)
        
        self.setup_ui()
        self.log(f"[就绪] {APP_VERSION} 终极引擎初始化完毕。等待指令...")

    def setup_ui(self):
        f_base = ("Microsoft YaHei", 10)
        f_bold = ("Microsoft YaHei", 10, "bold")

        path_frame = ttk.LabelFrame(self.root, text="第一步: 游戏目录配置")
        path_frame.pack(padx=15, pady=5, fill="x")
        self.path_var = tk.StringVar()
        ttk.Entry(path_frame, textvariable=self.path_var, font=f_base).pack(side="left", padx=10, pady=10, expand=True, fill="x")
        ttk.Button(path_frame, text="浏览游戏根目录...", command=self.browse_folder).pack(side="right", padx=10)

        env_frame = ttk.LabelFrame(self.root, text="第二步: 智能环境部署 (脱机拆包 + 字体)")
        env_frame.pack(padx=15, pady=5, fill="x")
        env_btn_frame = ttk.Frame(env_frame)
        env_btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(env_btn_frame, text="⚙️ 暴力解包与提取", command=self.smart_deploy_environment).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(env_btn_frame, text="🔠 注入自带黑体", command=lambda: self.configure_mixed_font(use_default=True)).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(env_btn_frame, text="🅰️ 选择自定义字体", command=lambda: self.configure_mixed_font(use_default=False)).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(env_btn_frame, text="🔤 注入中英菜单", command=self.inject_language_switch).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(env_frame, text="🚑 紧急复活游戏 (恢复.bak官方包)", command=self.rescue_game_environment).pack(fill="x", padx=10, pady=2)

        engine_frame = ttk.LabelFrame(self.root, text="第三步: 翻译引擎配置")
        engine_frame.pack(padx=15, pady=5, fill="x")
        ttk.Label(engine_frame, text="选择引擎:", font=f_base).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.engine_var = tk.StringVar(value="AI API (推荐: DeepSeek/OpenAI)")
        self.engine_combo = ttk.Combobox(engine_frame, textvariable=self.engine_var, values=["AI API (推荐: DeepSeek/OpenAI)", "Xiaomi MiMo (小米7亿Token特供)", "Google 网页直连 (免费/免配置)"], state="readonly", width=35, font=f_base)
        self.engine_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.engine_combo.bind("<<ComboboxSelected>>", self.update_engine_ui)

        ttk.Label(engine_frame, text="Base URL:", font=f_base).grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.base_url_var = tk.StringVar(value="https://api.deepseek.com")
        self.entry_base_url = ttk.Entry(engine_frame, textvariable=self.base_url_var, width=50, font=f_base)
        self.entry_base_url.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(engine_frame, text="模型名称:", font=f_base).grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.model_var = tk.StringVar(value="deepseek-chat")
        self.entry_model = ttk.Entry(engine_frame, textvariable=self.model_var, width=50, font=f_base)
        self.entry_model.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(engine_frame, text="API Key:", font=f_base).grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.api_key_var = tk.StringVar()
        self.entry_api_key = ttk.Entry(engine_frame, textvariable=self.api_key_var, show="*", width=50, font=f_base)
        self.entry_api_key.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        adv_frame = ttk.LabelFrame(self.root, text="第四步: 智能术语与并发控制")
        adv_frame.pack(padx=15, pady=5, fill="x")
        ttk.Label(adv_frame, text="人名白名单:", font=f_base).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.whitelist_var = tk.StringVar()
        ttk.Entry(adv_frame, textvariable=self.whitelist_var, width=45, font=f_base).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(adv_frame, text="并发协程数:", font=f_base).grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.workers_var = tk.IntVar(value=5)
        ttk.Spinbox(adv_frame, from_=1, to=15, textvariable=self.workers_var, width=5, font=f_base).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        self.force_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(adv_frame, text="强制重翻", variable=self.force_var).grid(row=0, column=2, padx=5, sticky="w")
        
        self.stat_label_var = tk.StringVar(value="【未扫描】点击估算分析 ->")
        ttk.Label(adv_frame, textvariable=self.stat_label_var, foreground="blue", font=f_bold).grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="w")
        ttk.Button(adv_frame, text="📊 极速估算 & 工作台", command=self.estimate_and_extract).grid(row=2, column=2, padx=5, pady=5)

        ctrl_frame = ttk.Frame(self.root)
        ctrl_frame.pack(padx=15, pady=10, fill="x")
        self.btn_run = ttk.Button(ctrl_frame, text="🚀 启动全量汉化", command=self.start_translation)
        self.btn_run.pack(side="left", expand=True, fill="x", padx=5, ipady=8)
        self.btn_patch = ttk.Button(ctrl_frame, text="🩺 单点补漏", command=self.scan_and_patch_leaks)
        self.btn_patch.pack(side="left", expand=True, fill="x", padx=5, ipady=8)
        
        # 【V15 新增】全局替换按钮
        self.btn_replace = ttk.Button(ctrl_frame, text="🧽 全局词汇替换", command=self.show_batch_replace_window)
        self.btn_replace.pack(side="left", expand=True, fill="x", padx=5, ipady=8)
        
        self.btn_pause = ttk.Button(ctrl_frame, text="⏸ 暂停/继续", command=self.toggle_pause, state=tk.DISABLED)
        self.btn_pause.pack(side="right", fill="x", padx=5, ipady=8)

        self.progress_file = ttk.Progressbar(self.root, mode="determinate")
        self.progress_file.pack(padx=15, pady=2, fill="x")
        self.monitor_var = tk.StringVar(value="等待任务启动...")
        ttk.Label(self.root, textvariable=self.monitor_var, font=f_base, foreground="green").pack(padx=15, pady=0, anchor="w")

        self.log_text = scrolledtext.ScrolledText(self.root, height=12, font=f_base)
        self.log_text.pack(padx=15, pady=5, fill="both", expand=True)

    def update_engine_ui(self, event=None):
        selection = self.engine_var.get()
        
        if "Google" in selection:
            state = "disabled"
            self.log("[UI] 已切换至 Google (免费) 引擎。")
        elif "Xiaomi" in selection:
            state = "normal"
            self.base_url_var.set("https://token-plan-cn.xiaomimimo.com/v1")
            self.model_var.set("mimo-v2.5-pro")  # 这里你可以换成小米官方让你使用的具体模型名字
            self.log("🔥 [UI] 已切换至 Xiaomi MiMo 专属通道，7亿 Token 火力全开！")
        else:
            state = "normal"
            self.base_url_var.set("https://api.deepseek.com")
            self.model_var.set("deepseek-chat")
            self.log("[UI] 已切换至通用 AI (API) 引擎。")
            
        self.entry_base_url.config(state=state)
        self.entry_model.config(state=state)
        self.entry_api_key.config(state=state)
    
    def run_cmd_with_xray_blocking(self, cmd_list: list, cwd: str = None, task_name: str = "底层任务"):
        """
        【V16 融合诊断】阻塞式进程透视镜 (带日志回收功能)
        """
        self.ui_queue.put({"type": "log", "content": f"🔍 [{task_name}] 启动透视镜，执行命令: {' '.join(cmd_list)}"})
        import subprocess
        full_log = []  # 收集完整的日志用于自愈分析
        try:
            process = subprocess.Popen(
                cmd_list,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='ignore',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            for line in process.stdout:
                clean_line = line.strip()
                if clean_line:
                    self.ui_queue.put({"type": "log", "content": f"    [Ren'Py 底层] {clean_line}"})
                    full_log.append(clean_line)
            
            process.wait()
            
            if process.returncode != 0:
                self.ui_queue.put({"type": "log", "content": f"❌ [{task_name}] 异常终止！崩溃状态码: {process.returncode}"})
                return False, "\n".join(full_log)  # 失败时返回 False 和完整报错
            else:
                self.ui_queue.put({"type": "log", "content": f"✅ [{task_name}] 完美执行完毕。"})
                return True, ""  # 成功时返回 True
                
        except Exception as e:
            self.ui_queue.put({"type": "log", "content": f"💀 [{task_name}] 发起致命错误: {str(e)}"})
            return False, str(e)

    def _process_ui_queue(self):
        try:
            logs_to_insert = []
            # 一次性掏空当前队列里的所有消息，避免阻塞
            while not self.ui_queue.empty():
                msg = self.ui_queue.get_nowait()
                mtype = msg.get("type")
                
                if mtype == "log":
                    logs_to_insert.append(msg["content"])
                elif mtype == "progress":
                    fname, percent = msg["fname"], msg["percent"]
                    if percent >= 100: self.active_tasks.pop(fname, None)
                    else: self.active_tasks[fname] = percent
                    self.update_monitor()
                elif mtype == "fail":
                    self.failed_sniper_lines.append(msg["item"])
                elif mtype == "finish":
                    self.btn_run.config(state=tk.NORMAL)
                    self.btn_patch.config(state=tk.NORMAL)
                    if msg["is_patch"] and self.failed_sniper_lines:
                        self.show_manual_rescue_window()
                    else:
                        messagebox.showinfo("完成", "翻译任务已全部结束。")
                        
            # 如果有日志，一次性批量插入 UI，彻底解决高频刷新造成的微卡
            if logs_to_insert:
                self.log_text.insert(tk.END, "\n".join(logs_to_insert) + "\n")
                self.log_text.see(tk.END)
                
        except Exception as e: 
            print(f"[UI队列异常] {e}")  
        finally:
            self.root.after(100, self._process_ui_queue)

    def log(self, msg):
        self.ui_queue.put({"type": "log", "content": msg})

    def browse_folder(self):
        p = filedialog.askdirectory()
        if p: self.path_var.set(os.path.normpath(p))

    def update_monitor(self):
        if not self.active_tasks:
            self.monitor_var.set("所有协程已空闲。")
            return
        status = " | ".join([f"{f}: {p}%" for f, p in self.active_tasks.items()])
        self.monitor_var.set(f"正在同步: {status}")

    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.btn_pause.config(text="▶ 继续翻译")
            self.log("⏸ [暂停] 已挂起异步任务队列。")
        else:
            self.pause_event.set()
            self.btn_pause.config(text="⏸ 暂停/继续")
            self.log("▶ [恢复] 任务队列已重新激活。")

    def update_eta_timer(self):
        """【V17 重构】独立于异步任务的 GUI 动态倒计时刷新器"""
        # 1. 任务结束时，恢复干净的标题栏并停止循环
        if getattr(self, 'is_translating', False) == False:
            self.root.title(f"Ren'Py 汉化大师 {APP_VERSION} ({APP_CODENAME})")
            return  
            
        # 2. 只有当扫描到需要翻译的句子时，才开始计算
        if getattr(self, 'total_lines_to_translate', 0) > 0:
            import time
            elapsed_time = time.time() - self.start_time
            
            # 核心：基于“已翻译句数”计算速度，拒绝断崖式跳动
            if self.completed_lines > 0:
                time_per_line = elapsed_time / self.completed_lines
                lines_left = self.total_lines_to_translate - self.completed_lines
                remaining_seconds = int(time_per_line * lines_left)
                
                m, s = divmod(remaining_seconds, 60)
                h, m = divmod(m, 60)
                time_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
            else:
                time_str = "速度测算中..."
                
            # 丝滑接管进度条，并增加 100% 封顶安全锁
            raw_percent = (self.completed_lines / self.total_lines_to_translate) * 100
            percent = min(raw_percent, 100.0) 
            self.progress_file['value'] = percent
            
            # 将进度实时写在软件最顶部的标题栏上
            self.root.title(f"Ren'Py 汉化大师 {APP_VERSION} - 总进度: {percent:.1f}% | 预计剩余: {time_str}")
        
        # 3. 强制 GUI 线程 1 秒后自我唤醒，实现秒表跳动效果
        self.root.after(1000, self.update_eta_timer)

    async def translate_single_file_async(self, engine, limiter, file_path, whitelist, is_patch_mode=False):
        fname = os.path.basename(file_path)
        # tasks 包含了该文件里所有的对话结构
        tasks = engine.parse_rpy_safely(file_path)
        
        to_translate = [t for t in tasks if t['needs_translation'] or self.force_var.get()]
        self.total_lines_to_translate += len(to_translate) # 【新增】动态累加全局总句数
        if not to_translate:
            return f"⏭ [跳过] {fname} (无新增文本)"

        if not os.path.exists(file_path + ".bak"): shutil.copy2(file_path, file_path + ".bak")
        
        lines = engine.safe_read_lines(file_path)
        batch_size = 1 if is_patch_mode else 10
        self.ui_queue.put({"type": "progress", "fname": fname, "percent": 0})
        
        for i in range(0, len(to_translate), batch_size):
            while not self.pause_event.is_set(): await asyncio.sleep(0.5)
            
            chunk = to_translate[i : i + batch_size]
            texts = [t['original_en'] for t in chunk]
            
            # --- 【V16 融合】构建“上帝视角”上下文语境 ---
            context_str = ""
            first_task = chunk[0]
            try:
                task_idx = tasks.index(first_task)
                # 往前提取最多 5 句已知的对话作为参考 (含已翻译好的历史文本)
                context_tasks = tasks[max(0, task_idx - 5) : task_idx]
                for ct in context_tasks:
                    zh_text = ct['cached_zh'] if ct['cached_zh'] else "(未翻译)"
                    context_str += f"原文: {ct['original_en']}\n译文: {zh_text}\n"
            except ValueError:
                pass
            # ---------------------------------------------
            
            # 把语境 context_str 传给底层引擎
            results = await engine.process_translation_pipeline(texts, whitelist, is_patch_mode, limiter, context_str)
            
            if results:
                for idx, res in enumerate(results):
                    target = chunk[idx]
                    lines[target['line_idx']] = f'{target["prefix"]}"{res}"{target["suffix"]}\n'
                    # 【关键】内存级状态更新：把刚翻好的中文塞回 tasks 列表。
                    # 这样同文件的下一个批次在往前追溯语境时，就能立刻看到这句新鲜热乎的中文！
                    target['cached_zh'] = res 
                
                tmp_file = file_path + ".tmp"
                with open(tmp_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                os.replace(tmp_file, file_path)
                self.completed_lines += len(chunk) # 【新增】给全局进度池增加已翻译句数

            else:
                if is_patch_mode:
                    for t in chunk: 
                        self.ui_queue.put({"type": "fail", "item": {'file': file_path, 'idx': t['line_idx'], 'en': t['original_en'], 'prefix': t['prefix'], 'suffix': t['suffix']}})

            percent = int(((i + len(chunk)) / len(to_translate)) * 100)
            self.ui_queue.put({"type": "progress", "fname": fname, "percent": percent})

        self.ui_queue.put({"type": "progress", "fname": fname, "percent": 100})
        return f"✅ [完成] {fname}"

    async def run_pipeline(self, files, whitelist, is_patch_mode=False):
        engine = RenpyV15CoreEngine(
            api_key=self.api_key_var.get(), 
            base_url=self.base_url_var.get(),
            model=self.model_var.get(),
            engine_type="Google" if "Google" in self.engine_var.get() else "AI"
        )
        
        from renpy_core_engine import AsyncRateLimiter
        limiter = AsyncRateLimiter(rpm=90, max_concurrency=self.workers_var.get())
        
        # 【V17 新增】初始化全局句数统计器并启动秒表
        self.total_lines_to_translate = 0
        self.completed_lines = 0
        self.is_translating = True
        import time
        self.start_time = time.time()
        self.root.after(0, self.update_eta_timer) # 激活独立 UI 刷新器
        
        try:
            tasks = [self.translate_single_file_async(engine, limiter, f, whitelist, is_patch_mode) for f in files]
            for future in asyncio.as_completed(tasks):
                try: self.log(await future)
                except Exception as e: self.log(f"❌ [异常] {str(e)}")
                
                # 注意：这里我们彻底删除了以前关于 elapsed_seconds 和 file_progress 的旧代码！
                # 因为它们现在全被 update_eta_timer 完美接管了。
        finally:
            engine.cache.force_save()
            self.is_translating = False # 【新增】翻译彻底结束，关闭秒表

        self.ui_queue.put({"type": "finish", "is_patch": is_patch_mode})

    def _launch_pipeline_thread(self, files, wl, is_patch):
        self.btn_run.config(state="disabled")
        self.btn_patch.config(state="disabled")
        self.btn_pause.config(state="normal")
        def run_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.run_pipeline(files, wl, is_patch))
            finally:
                loop.close()
        threading.Thread(target=run_thread, daemon=True).start()

    def start_translation(self):
        base_dir = self.path_var.get()
        tl_dir = os.path.join(base_dir, "game", "tl", "schinese")
        if not os.path.exists(tl_dir): return messagebox.showerror("错误", "未找到翻译文件夹。")
        files = [os.path.join(r, f) for r, d, fs in os.walk(tl_dir) for f in fs if f.endswith(".rpy")]
        wl = [w.strip() for w in self.whitelist_var.get().split(',') if w.strip()]
        self._launch_pipeline_thread(files, wl, is_patch=False)

    def scan_and_patch_leaks(self):
        self.failed_sniper_lines = []
        base_dir = self.path_var.get()
        tl_dir = os.path.join(base_dir, "game", "tl", "schinese")
        if not os.path.exists(tl_dir): return messagebox.showerror("错误", "未找到翻译文件夹。")
        files = [os.path.join(r, f) for r, d, fs in os.walk(tl_dir) for f in fs if f.endswith(".rpy")]
        wl = [w.strip() for w in self.whitelist_var.get().split(',') if w.strip()]
        self._launch_pipeline_thread(files, wl, is_patch=True)

    # 【V15 新增功能】全局安全精准替换器
    def show_batch_replace_window(self):
        base_dir = self.path_var.get()
        tl_dir = os.path.join(base_dir, "game", "tl", "schinese")
        if not os.path.exists(tl_dir): return messagebox.showerror("错误", "请先解包提取翻译环境。")
        
        win = tk.Toplevel(self.root)
        win.title("🧽 全局译文精准替换器")
        win.geometry("450x250")
        
        ttk.Label(win, text="本功能仅对已翻译的中文对话内部生效，\n绝对安全，不会破坏英文原文与代码结构。", justify="center", foreground="blue").pack(pady=15)
        
        f1 = ttk.Frame(win)
        f1.pack(pady=5)
        ttk.Label(f1, text="查找词:").pack(side="left", padx=5)
        old_var = tk.StringVar()
        ttk.Entry(f1, textvariable=old_var, width=25).pack(side="left", padx=5)
        
        f2 = ttk.Frame(win)
        f2.pack(pady=5)
        ttk.Label(f2, text="替换为:").pack(side="left", padx=5)
        new_var = tk.StringVar()
        ttk.Entry(f2, textvariable=new_var, width=25).pack(side="left", padx=5)
        
        btn_start = ttk.Button(win, text="🚀 扫描并安全替换全文本")
        
        def do_replace():
            old_w = old_var.get().strip()
            new_w = new_var.get().strip()
            if not old_w: return messagebox.showwarning("警告", "查找词不能为空。")
            
            btn_start.config(state="disabled") # 防止狂点导致并发冲突
            
            def _run():
                engine = RenpyV15CoreEngine()
                count = 0
                backed_up = set()
                self.log(f"[替换器] 开始全局扫描，目标: {old_w} -> {new_w} ...")
                
                for root_dir, _, files in os.walk(tl_dir):
                    for f in files:
                        if f.endswith(".rpy"):
                            fp = os.path.join(root_dir, f)
                            lines = engine.safe_read_lines(fp)
                            changed = False
                            
                            for i, line in enumerate(lines):
                                if line.lstrip().startswith('#'): continue
                                parsed = engine._parse_dialogue_line(line)
                                if parsed:
                                    prefix, diag, suffix = parsed
                                    if old_w in diag:
                                        # 修改前强制进行 .replace_bak 备份 (防灾机制)[cite: 4]
                                        if fp not in backed_up and not os.path.exists(fp + ".replace_bak"):
                                            import shutil
                                            shutil.copy2(fp, fp + ".replace_bak")
                                            backed_up.add(fp)
                                        
                                        new_diag = diag.replace(old_w, new_w)
                                        lines[i] = f'{prefix}"{new_diag}"{suffix}\n'
                                        changed = True
                                        count += diag.count(old_w)
                                        
                            if changed:
                                tmp = fp + ".tmp"
                                with open(tmp, 'w', encoding='utf-8') as f_out: f_out.writelines(lines)
                                os.replace(tmp, fp)
                                
                self.root.after(0, lambda: (
                    self.log(f"✅ [替换完成] 修正 {count} 处词汇，已自动生成备份。"),
                    messagebox.showinfo("完成", f"安全替换结束！\n共计在对话区修正了 {count} 处匹配项。"),
                    btn_start.config(state="normal"),
                    win.destroy()
                ))

            # 移入子线程，防止主界面冻结变白[cite: 4]
            threading.Thread(target=_run, daemon=True).start()

        btn_start.config(command=do_replace)
        btn_start.pack(pady=20, ipady=5)

    def estimate_and_extract(self):
        game_dir = self.path_var.get()
        tl_dir = os.path.join(game_dir, "game", "tl", "schinese")
        if not os.path.exists(tl_dir): return messagebox.showerror("错误", "找不到 tl/schinese 文件夹！")

        self.stat_label_var.set("⏳ 正在极速扫描并统计词频，请稍候...")
        # 已移除高危的 self.root.update() 避免递归卡死事件循环[cite: 4]

        def do_estimate():
            total_chars, total_lines, rpy_count = 0, 0, 0
            term_counter = Counter()
            defined_chars = set()
            noise_words = {"You", "Yeah", "Wow", "Hey", "The", "And", "But", "For", "Not", "Yes", "Now", "She", "Her", "His", "Him", "They", "Them", "What", "When", "Where", "How", "This", "That", "There", "Will", "With", "Just", "Your", "Very", "Well", "Some", "Are"}

            self.log("[估算] 启动后台扫描引擎...")
            temp_engine = RenpyV15CoreEngine()
            
            re_char_def = re.compile(r'Character\(\s*["\']([^"\']+)["\']')
            for root, _, files in os.walk(os.path.join(game_dir, "game")):
                if "tl" in root: continue
                for file in files:
                    if file.endswith(".rpy"):
                        try:
                            content = "\n".join(temp_engine.safe_read_lines(os.path.join(root, file)))
                            for c in re_char_def.findall(content):
                                if len(c) > 1 and not temp_engine._is_resource_or_code(c): defined_chars.add(c)
                        except: pass

            for root, _, files in os.walk(tl_dir):
                for file in files:
                    if file.endswith(".rpy"):
                        rpy_count += 1
                        parsed_data = temp_engine.parse_rpy_safely(os.path.join(root, file))
                        for item in parsed_data:
                            if item['needs_translation']:
                                en_text = item['original_en']
                                total_chars += len(en_text)
                                total_lines += 1
                                for w in re.findall(r'\b([A-Z][a-z]+)\b', en_text):
                                    if len(w) > 2 and w not in noise_words: term_counter[w] += 1

            cost_cny = ((total_chars * 0.8) / 1000000) * 1.5 
            res_info = f"共 {rpy_count} 个文件 | {total_lines} 句未翻译 | 预估 ￥{cost_cny:.2f}"
            
            data_list = [( "☑ 保护" if t in defined_chars else "☐ 忽略", t, term_counter[t], "代码定义" if t in defined_chars else "对话分析" ) for t in set(list(term_counter.keys()) + list(defined_chars))]
            data_list.sort(key=lambda x: x[2], reverse=True)
            
            self.root.after(0, lambda: self._show_estimate_window(res_info, data_list))

        threading.Thread(target=do_estimate, daemon=True).start()

    def _show_estimate_window(self, res_info, data_list):
        self.stat_label_var.set(res_info)
        if not data_list: return
        
        win = tk.Toplevel(self.root)
        win.title("V15.0 术语工作台")
        win.geometry("700x750")
        
        ttk.Label(win, text=res_info, font=("Microsoft YaHei", 12, "bold"), foreground="blue").pack(pady=10)
        ttk.Label(win, text="1. 选中行按『空格』切换状态  2. 只有标有 ☑ 的词会被保护", font=("Microsoft YaHei", 11)).pack(pady=5)
        
        style = ttk.Style(win)
        style.configure("Custom.Treeview", rowheight=30, font=("Microsoft YaHei", 10))
        style.configure("Custom.Treeview.Heading", font=("Microsoft YaHei", 12, "bold"))

        tree = ttk.Treeview(win, style="Custom.Treeview", columns=('status', 'term', 'freq', 'src'), show='headings', selectmode='browse')
        tree.heading('status', text='状态 (空格切换)'); tree.column('status', width=120, anchor='center')
        tree.heading('term', text='名词'); tree.column('term', width=220, anchor='w')
        tree.heading('freq', text='频次'); tree.column('freq', width=100, anchor='center')
        tree.heading('src', text='来源'); tree.column('src', width=120, anchor='center')
        
        scrollbar = ttk.Scrollbar(win, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill='both', expand=True, padx=20, pady=10)
        
        for row in data_list: tree.insert('', tk.END, values=row)
            
        def toggle(event=None):
            for i in tree.selection():
                v = tree.item(i, 'values')
                tree.item(i, values=("☐ 忽略" if v[0] == "☑ 保护" else "☑ 保护", v[1], v[2], v[3]))
        tree.bind('<space>', toggle)
        tree.bind('<Double-1>', toggle)
        
        btn_f = ttk.Frame(win)
        btn_f.pack(pady=10)
        ttk.Button(btn_f, text="☑ 全选", command=lambda: [tree.item(i, values=("☑ 保护",)+tree.item(i, 'values')[1:]) for i in tree.get_children()]).pack(side="left", padx=10)
        ttk.Button(btn_f, text="☐ 全不选", command=lambda: [tree.item(i, values=("☐ 忽略",)+tree.item(i, 'values')[1:]) for i in tree.get_children()]).pack(side="left", padx=10)
        
        def save():
            self.whitelist_var.set(", ".join([tree.item(i, 'values')[1] for i in tree.get_children() if tree.item(i, 'values')[0] == "☑ 保护"]))
            win.destroy()
        ttk.Button(win, text="💾 保存勾选项并返回", command=save).pack(pady=15, ipady=5)

    def rescue_game_environment(self):
        """【紧急抢救】一键恢复所有被误改名的官方 .rpa 和 .rpyc 文件"""
        base_dir = self.path_var.get()
        if not os.path.exists(base_dir): 
            return messagebox.showerror("错误", "请先选择游戏目录！")
            
        game_dir = os.path.join(base_dir, "game")
        if not messagebox.askyesno("警告", "此操作将把 game 目录下所有的 .rpa.bak 和 .rpyc.bak 强制恢复为原封包。\n\n仅在游戏报错 'could not find label start' 时使用！\n是否继续？"):
            return

        self.log("🚑 [紧急抢救] 正在全盘扫描被封印的官方文件...")
        count = 0
        
        # 开启子线程避免卡死主界面
        def _run_rescue():
            nonlocal count
            for root, dirs, files in os.walk(game_dir):
                for f in files:
                    if f.endswith(".rpa.bak") or f.endswith(".rpyc.bak"):
                        old_path = os.path.join(root, f)
                        # 切掉最后的 .bak (4个字符)
                        new_path = old_path[:-4] 
                        
                        try:
                            # 如果目标位置已经有同名文件（可能是解包残骸），先删掉给原包腾位置
                            if os.path.exists(new_path):
                                os.remove(new_path)
                            os.rename(old_path, new_path)
                            count += 1
                        except Exception as e:
                            self.log(f"⚠️ 恢复失败: {f} -> {e}")
                            
            self.root.after(0, lambda: (
                self.log(f"✅ [抢救成功] 游戏已复活！共恢复 {count} 个底层封包文件。"),
                messagebox.showinfo("抢救完成", f"已成功恢复 {count} 个官方包。\n请重新运行游戏测试！")
            ))
            
        threading.Thread(target=_run_rescue, daemon=True).start()

    def smart_deploy_environment(self):
        base_dir = self.path_var.get()
        if not os.path.exists(base_dir): return messagebox.showerror("错误", "请选择正确的游戏目录！")
        exes = [f for f in os.listdir(base_dir) if f.endswith('.exe') and 'python' not in f.lower() and 'renpy' not in f.lower()]
        if not exes: return messagebox.showerror("错误", "找不到游戏的 .exe 执行文件！")
        exe_path = os.path.join(base_dir, exes[0])
        game_dir = os.path.join(base_dir, "game")
        self.log(f"[指令] 锁定游戏进程: {exes[0]}")
        
        def deploy_pipeline():
            python_exe = sys.executable if sys.executable.endswith("python.exe") else "python"
            lib_dir = os.path.join(base_dir, "lib")
            if os.path.exists(lib_dir):
                for root, _, files in os.walk(lib_dir):
                    if 'python.exe' in (f.lower() for f in files):
                        python_exe = os.path.join(root, "python.exe"); break
            
            rpatool_py_local = resource_path(os.path.join("tools", "rpatool.py"))
            unrpyc_py_local = resource_path(os.path.join("tools", "unrpyc.py"))
            rpatool_dir, unrpyc_dir = os.path.join(base_dir, "rpatool_temp"), os.path.join(base_dir, "unrpyc_temp")
            
            try:
                rpa_files = glob.glob(os.path.join(game_dir, "**", "*.rpa"), recursive=True)
                if rpa_files:
                    self.log(f"🔔 [预警] 启动【RPA 粉碎协议】...")
                    rpatool_py = os.path.join(rpatool_dir, "rpatool-master", "rpatool")
                    if os.path.exists(rpatool_py_local):
                        rpatool_py = rpatool_py_local
                    elif not os.path.exists(rpatool_py):
                        resp = requests.get("https://github.com/Shizmob/rpatool/archive/refs/heads/master.zip", timeout=30)
                        zip_path = os.path.join(base_dir, "rpatool_master.zip")
                        with open(zip_path, "wb") as f: f.write(resp.content)
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref: zip_ref.extractall(rpatool_dir)
                        os.remove(zip_path)
                        
                    for rpa in rpa_files:
                        # 1. 捕获子进程的执行结果
                        result = subprocess.run([python_exe, rpatool_py, "-x", rpa, "-o", game_dir], creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0, timeout=300)
                        
                        # 2. 【V17 安全锁】只有解包工具明确返回 0 (执行成功) 时，才封印官方原包
                        if result.returncode == 0:
                            os.rename(rpa, rpa + ".bak")
                            self.log(f"✅ {os.path.basename(rpa)} 拆解成功。")
                        else:
                            self.log(f"⚠️ [防爆警告] {os.path.basename(rpa)} 拆解失败！已放弃修改原文件，保护游戏本体。")
                        
                rpyc_files = glob.glob(os.path.join(game_dir, "**", "*.rpyc"), recursive=True)
                targets = [f for f in rpyc_files if not os.path.exists(f[:-1]) and not os.path.basename(f).startswith('un')]
                if targets:
                    self.log(f"⚠️ [预警] 启动【幽灵脱壳】...")
                    unrpyc_py = os.path.join(unrpyc_dir, "unrpyc-master", "unrpyc.py")
                    if os.path.exists(unrpyc_py_local):
                        unrpyc_py = unrpyc_py_local
                    elif not os.path.exists(unrpyc_py):
                        resp = requests.get("https://github.com/CensoredUsername/unrpyc/archive/refs/heads/master.zip", timeout=30)
                        zip_path = os.path.join(base_dir, "unrpyc_master.zip")
                        with open(zip_path, "wb") as f: f.write(resp.content)
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref: zip_ref.extractall(unrpyc_dir)
                        os.remove(zip_path)
                        
                    for i in range(0, len(targets), 40):
                        subprocess.run([python_exe, unrpyc_py] + targets[i:i+40], creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0, timeout=120)
                        
                    # 【V17 安全锁】不盲目重命名，做“见尸确认”：只有看到成功脱壳生成的 .rpy 文件，才允许封印 .rpyc
                    for rpyc in targets:
                        expected_rpy = rpyc[:-1]  # 砍掉最后的 'c'，推测出明文文件名
                        if os.path.exists(expected_rpy):
                            try: os.rename(rpyc, rpyc + ".bak")
                            except: pass
                        else:
                            self.log(f"⚠️ [防爆警告] {os.path.basename(rpyc)} 脱壳失败 (未生成明文)，已保留官方原文件。")
                        
                self.log("⚙️ [部署] 正在生成翻译模板 (启动 V16.1 纳米级自愈手术)...")
                cmd_list = [exe_path, base_dir, "translate", "schinese"]
                
                max_retries = 20  
                consecutive_unrecognized = 0  # 连续无法识别的错误次数
                
                for attempt in range(max_retries):
                    success, error_log = self.run_cmd_with_xray_blocking(cmd_list, cwd=base_dir, task_name=f"生成模板(尝试 {attempt+1})")
                    
                    if success:
                        break  
                        
                    # --- 🚑 触发 V16.1 纳米级自愈手术 ---
                    import re
                    match = re.search(r'File\s+"([^"]+\.rpy)",\s+line\s+(\d+)', error_log)
                    if match:
                        consecutive_unrecognized = 0  # 识别成功，重置容错计数
                        err_file_rel = match.group(1)
                        err_line_num = int(match.group(2))
                        err_file_abs = os.path.join(base_dir, err_file_rel)
                        
                        if os.path.exists(err_file_abs):
                            self.log(f"🩹 [自愈系统] 发现反编译破损: {os.path.basename(err_file_abs)} 第 {err_line_num} 行。启动纳米级切除...")
                            try:
                                # 【V16.1 修复】复用引擎的自适应编码读取机制，完美兼容日系 cp932 游戏
                                temp_engine = RenpyV15CoreEngine()
                                lines = temp_engine.safe_read_lines(err_file_abs)
                                    
                                if 0 < err_line_num <= len(lines):
                                    original_line = lines[err_line_num - 1]
                                    indent_size = len(original_line) - len(original_line.lstrip())
                                    
                                    for i in range(err_line_num - 1, len(lines)):
                                        curr_line = lines[i]
                                        if not curr_line.strip():
                                            lines[i] = "# " + curr_line
                                            continue
                                            
                                        curr_indent = len(curr_line) - len(curr_line.lstrip())
                                        if i == err_line_num - 1 or curr_indent > indent_size:
                                            lines[i] = "# [V16手术切除] " + curr_line
                                        else:
                                            break  
                                            
                                    # 【V16.1 修复】写回时强制使用 utf-8-sig (Ren'Py 7+ 全面支持)
                                    tmp_path = err_file_abs + ".surgery_tmp"
                                    with open(tmp_path, 'w', encoding='utf-8-sig') as f:
                                        f.writelines(lines)
                                    os.replace(tmp_path, err_file_abs)
                                        
                                    self.log(f"💉 [自愈系统] 编码安全手术完成，毒瘤代码块已注释，引擎重新点火...")
                                    continue
                            except Exception as ex:
                                self.log(f"⚠️ [自愈系统] 手术失败: {ex}")
                    else:
                        consecutive_unrecognized += 1
                        self.log(f"⚠️ [自愈系统] 第 {attempt+1} 次：无法识别底层错误格式，跳过当前切除...")
                        if consecutive_unrecognized >= 3:
                            raise Exception("连续 3 次遇到无法识别的非语法级深层崩溃，中止自愈。")
                            
                else:
                    # for 循环的 else 分支：如果正常跑满了 20 次依然没有 break
                    raise Exception(f"已达到最大自愈次数 {max_retries}，底层可能已严重损毁。")
                
                if os.path.exists(os.path.join(base_dir, "game", "tl", "schinese")):
                    self.log("✅ [大功告成] 翻译环境已就绪。")
                    self.root.after(0, lambda: messagebox.showinfo("成功", "解包提取完成！"))
                
            except Exception as e: 
                self.log(f"❌ [崩溃] {e}")
                
            finally:
                self.log("🧹 [战场清理] 正在销毁临时明文源码，恢复游戏原版生态...")
                
                # 1. 销毁解包工具临时文件
                if os.path.exists(unrpyc_dir): shutil.rmtree(unrpyc_dir, ignore_errors=True)
                if os.path.exists(rpatool_dir): shutil.rmtree(rpatool_dir, ignore_errors=True)
                
                # 2. 精确制导：销毁脱壳产生的 .rpy 和手术产生的 .broken 废料
                try:
                    for root, dirs, files in os.walk(game_dir):
                        # 绝对安全锁：避开我们刚刚千辛万苦提取出来的翻译模板文件夹
                        if 'tl' in root.replace('\\', '/').split('/'):
                            continue
                            
                        for f in files:
                            file_path = os.path.join(root, f)
                            
                            # 情况A：如果是我们手术遗留的 .broken 废料，直接删
                            if f.endswith('.broken'):
                                try: os.remove(file_path)
                                except: pass
                                
                            # 情况B：如果是 .rpy 文件
                            elif f.endswith('.rpy'):
                                # 智能判定：只有当同目录下存在同名的 .rpyc 时，
                                # 才说明这个 .rpy 是我们刚才脱壳生成的临时产物，可以安全销毁！
                                rpyc_path = file_path + "c"
                                if os.path.exists(rpyc_path):
                                    try: os.remove(file_path)
                                    except: pass
                                    
                except Exception as e:
                    self.log(f"⚠️ [战场清理] 自动清理过程遇到微小阻碍，但不影响汉化: {e}")
                    
        # 启动整个部署流的子线程
        threading.Thread(target=deploy_pipeline, daemon=True).start()
        
    def configure_mixed_font(self, use_default=False):
        tl_dir = os.path.join(self.path_var.get(), "game", "tl", "schinese")
        if not os.path.exists(tl_dir): return messagebox.showerror("错误", "找不到 tl/schinese 文件夹，请先执行解包提取！")
        
        if use_default:
            f_path = resource_path(os.path.join("tools", "simhei.ttf"))
            if not os.path.exists(f_path): return messagebox.showerror("错误", "找不到内置字体包 simhei.ttf！")
            self.log("🔠 [字体] 检测到内置黑体，准备挂载...")
        else:
            f_path = filedialog.askopenfilename(filetypes=[("Font", "*.ttf *.otf *.ttc")])
            if not f_path: return
            self.log(f"🔠 [字体] 获取到自定义字体：{os.path.basename(f_path)}")

        target = "cn_font" + os.path.splitext(f_path)[1]
        shutil.copy2(f_path, os.path.join(tl_dir, target))
        
        code = f"""translate schinese python:
    mixed_font = FontGroup().add("DejaVuSans.ttf", 0x0000, 0x024F).add("tl/schinese/{target}", 0x0250, 0xFFFF)
    # --- 基础文本与界面 ---
    gui.system_font = mixed_font
    gui.text_font = mixed_font
    gui.name_text_font = mixed_font
    gui.interface_text_font = mixed_font
    gui.button_text_font = mixed_font
    gui.choice_button_text_font = mixed_font
    gui.quick_button_text_font = mixed_font
    gui.nvl_text_font = mixed_font
    gui.title_text_font = mixed_font
    gui.label_text_font = mixed_font
    # --- 历史记录专属 ---
    gui.history_text_font = mixed_font
    gui.history_name_text_font = mixed_font
    # --- 【新增】系统提示与确认弹窗专属 ---
    gui.notify_text_font = mixed_font
    gui.confirm_text_font = mixed_font

# ==========================================
# 强行夺取各大底层 Style 样式控制权
# ==========================================
translate schinese style default:
    font mixed_font
translate schinese style button_text:
    font mixed_font
translate schinese style choice_button_text:
    font mixed_font
translate schinese style quick_button_text:
    font mixed_font
translate schinese style navigation_button_text:
    font mixed_font
translate schinese style main_menu_text:
    font mixed_font
translate schinese style pref_label_text:
    font mixed_font
translate schinese style radio_button_text:
    font mixed_font
translate schinese style check_button_text:
    font mixed_font
translate schinese style history_text:
    font mixed_font
translate schinese style history_name_text:
    font mixed_font
# --- 【新增】强行覆盖快进与确认提示样式 ---
translate schinese style notify_text:
    font mixed_font
translate schinese style skip_text:
    font mixed_font
translate schinese style confirm_prompt_text:
    font mixed_font
"""
        with open(os.path.join(tl_dir, "custom_font_setup.rpy"), "w", encoding="utf-8") as f: f.write(code)
        self.log("✅ 字体注入完成 (已应用全量 UI 覆盖补丁，西文排版已保护)")

    def inject_language_switch(self):
        g_dir = os.path.join(self.path_var.get(), "game")
        tl_dir = os.path.join(g_dir, "tl", "schinese")
        font_path = "DejaVuSans.ttf" 
        if os.path.exists(tl_dir):
            fonts = glob.glob(os.path.join(tl_dir, "cn_font.*"))
            if fonts: font_path = "tl/schinese/" + os.path.basename(fonts[0])

        code = f"""# ==========================================
# 【V17.1 终极降维】三位一体语言控制模块 (修复生命周期)
# ==========================================

screen language_button_overlay():
    zorder 9999
    
    # 1. 初次启动强制中文：利用定时器在 UI 渲染完成的 0.01 秒后瞬间触发，完美避开引擎 init 启动期崩溃！
    if persistent._v17_auto_cn is None:
        timer 0.01 action [SetField(persistent, "_v17_auto_cn", True), Language("schinese")]

    # 2. 可拖拽的悬浮按钮面板
    draggroup:
        drag:
            drag_name "lang_btn"
            xpos 0.85 ypos 0.05
            draggable True
            frame:
                background Solid("#00000088") # 半透明黑底
                padding (10, 5)
                hbox:
                    spacing 15
                    textbutton "EN":
                        text_size 20
                        action Language(None)
                    textbutton "中文":
                        text_font "{font_path}"  
                        text_size 20
                        action Language("schinese")

# 3. 隐形全局快捷键监听 (高端玩家专属：F8 一键切换)
screen global_lang_hotkey():
    zorder 9999
    key "K_F8" action If(_preferences.language == "schinese", Language(None), Language("schinese"))

init python:
    config.overlay_screens.append("language_button_overlay")
    config.overlay_screens.append("global_lang_hotkey")
"""
        with open(os.path.join(g_dir, "language_switch_mod.rpy"), "w", encoding="utf-8") as f: 
            f.write(code)
            
        self.log("✅ 终极语言菜单注入成功！(附带：强制默认中文 + 拖拽防遮挡 + F8热键)")
        messagebox.showinfo("注入成功", "三位一体语言模块已就绪！\n\n1. 玩家打开游戏将默认显示中文。\n2. 游戏内可使用 F8 键一键切换。\n3. 游戏内右上角有可拖拽的切换面板。")

    def show_manual_rescue_window(self):
        win = tk.Toplevel(self.root)
        win.title("🚨 顽固死钉子人工收容所")
        win.geometry("800x600")
        
        def on_closing():
            if messagebox.askokcancel("警告", "你确定要关闭吗？未点击下方保存按钮的翻译数据将永久丢失！"):
                win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_closing)
        
        ttk.Label(win, text="以下句子因极端乱码或强硬道德审查，大模型已彻底崩溃拒翻。", font=("Microsoft YaHei", 11, "bold"), foreground="red").pack(pady=5)
        ttk.Label(win, text="这是实现 100% 汉化的最后防线，请手动输入译文并点击保存（留空则保持英文）。", font=("Microsoft YaHei", 10)).pack(pady=5)
        
        canvas = tk.Canvas(win)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")
        
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
        # 使用局部绑定，并在窗口销毁时自动清理，防止全局污染
        bind_id = win.bind("<MouseWheel>", _on_mousewheel, add="+")
        
        def cleanup(*_):
            try: win.unbind("<MouseWheel>", bind_id)
            except: pass
            
        # 窗口点 X 关闭时的行为
        def on_closing():
            if messagebox.askokcancel("警告", "你确定要关闭吗？未点击下方保存按钮的翻译数据将永久丢失！"):
                cleanup()
                win.destroy()
                
        win.protocol("WM_DELETE_WINDOW", on_closing)
        
        entries = []
        for item in self.failed_sniper_lines:
            frame = ttk.LabelFrame(scrollable_frame, text=os.path.basename(item['file']))
            frame.pack(fill="x", padx=10, pady=5)
            txt_en = tk.Text(frame, height=3, font=("Consolas", 10), background="#f0f0f0")
            txt_en.pack(fill="x", padx=5, pady=2)
            txt_en.insert(tk.END, item['en'])
            txt_en.config(state=tk.DISABLED)
            
            entry = ttk.Entry(frame, font=("Microsoft YaHei", 10))
            entry.pack(fill="x", padx=5, pady=5)
            entries.append((item, entry))
            
        def save_manual():
            file_updates = {}
            from renpy_core_engine import RenpyV15CoreEngine
            temp_engine = RenpyV15CoreEngine()
            
            for item, entry in entries:
                zh_text = entry.get().strip()
                if not zh_text: zh_text = item['en'] 
                
                if item['file'] not in file_updates:
                    file_updates[item['file']] = temp_engine.safe_read_lines(item['file'])
                
                lines = file_updates[item['file']]
                lines[item['idx']] = f"{item['prefix']}\"{zh_text}\"{item['suffix']}\n"
                
            for fp, lines in file_updates.items():
                tmp_file = fp + ".tmp"
                with open(tmp_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                os.replace(tmp_file, fp)
                    
            messagebox.showinfo("收容成功", "人工兜底完成，游戏代码已被安全强行写入，实现 100% 汉化！")
            cleanup()
            win.destroy()
            
        ttk.Button(win, text="💾 保存所有手动译文并强行覆盖至游戏", command=save_manual).pack(pady=10, ipady=5)

if __name__ == "__main__":
    root = tk.Tk()
    try:
        root.tk.call("source", "clam")
        ttk.Style().theme_use("clam")
    except: pass
    app = RenpyTranslatorV15(root)
    root.mainloop()