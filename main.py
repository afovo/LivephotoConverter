import os
import sys
import shutil
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import subprocess
import threading
import time
from PIL import Image, ImageTk
import re
import zipfile
import tempfile
import ctypes
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import multiprocessing

# 尝试导入HEIC支持
try:
    from PIL import Image
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass  # 如果没有安装pillow_heif，则使用备用方法

class LivePhotoBackupTool:
    """LivePhoto备份与转换工具 - 支持LivePhoto和普通图片的备份与转换"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Live Photo备份工具")
        self.root.geometry("960x680")
        self.root.minsize(800, 600)  # 设置最小窗口大小
        
        # 设置应用主题色
        self.bg_color = "#F5F5F7"  # 苹果风格浅灰背景
        self.accent_color = "#0071E3"  # 苹果风格蓝色强调色
        self.text_color = "#1D1D1F"  # 主文本颜色
        self.secondary_text_color = "#86868B"  # 次要文本颜色
        
        # 设置界面字体
        self.font_family = "Arial" if sys.platform == "win32" else "SF Pro Display"
        self.header_font = (self.font_family, 16, "bold")
        self.subheader_font = (self.font_family, 12)
        self.normal_font = (self.font_family, 10)
        self.small_font = (self.font_family, 9)
        
        # 配置变量
        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.output_format = tk.StringVar(value="mp4")
        self.preserve_metadata = tk.BooleanVar(value=True)
        self.preserve_structure = tk.BooleanVar(value=True)
        self.thread_count = tk.IntVar(value=multiprocessing.cpu_count())
        self.use_gpu = tk.BooleanVar(value=False)
        
        # 高DPI支持
        if sys.platform == "win32":
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
                ScaleFactor = ctypes.windll.shcore.GetScaleFactorForDevice(0)
                self.root.tk.call('tk', 'scaling', ScaleFactor/75)
            except:
                pass
            
        # 获取应用程序路径并设置依赖项路径
        self.app_path = self.get_app_path()
        self.dependencies_path = os.path.join(self.app_path, 'dependencies')
        self.ffmpeg_path = os.path.join(self.dependencies_path, 'ffmpeg.exe')
        self.ffprobe_path = os.path.join(self.dependencies_path, 'ffprobe.exe')
        self.ffplay_path = os.path.join(self.dependencies_path, 'ffplay.exe')
        
        # 正在处理的标志和队列
        self.is_processing = False
        self.cancel_flag = threading.Event()
        self.file_queue = queue.Queue()
        self.preview_queue = queue.Queue()
        
        # 预览相关
        self.current_preview_file = None
        self.preview_image = None
        self.thumbnail_size = (300, 300)
        
        # 设置UI
        self.setup_ui()
        
        # 检查依赖
        self.check_ffmpeg()
        
        # 设置文件夹浏览线程
        self.folder_scan_thread = None
        self.folder_tree_data = {}

    def get_app_path(self):
        """获取应用程序路径"""
        if getattr(sys, 'frozen', False):
            # 打包后的环境
            return os.path.dirname(sys.executable)
        else:
            # 开发环境
            return os.path.dirname(os.path.abspath(__file__))
    
    def setup_ui(self):
        """设置用户界面"""
        # 配置根窗口
        self.root.configure(bg=self.bg_color)
        
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 配置样式
        style = ttk.Style()
        style.configure("TFrame", background=self.bg_color)
        style.configure("TLabel", background=self.bg_color, foreground=self.text_color, font=self.normal_font)
        style.configure("Header.TLabel", font=self.header_font, foreground=self.text_color)
        style.configure("Subheader.TLabel", font=self.subheader_font, foreground=self.text_color)
        style.configure("TButton", font=self.normal_font)
        style.configure("Accent.TButton", background=self.accent_color)
        style.configure("TCheckbutton", background=self.bg_color, font=self.normal_font)
        style.configure("Treeview", font=self.normal_font, rowheight=24)
        style.configure("Treeview.Heading", font=self.normal_font)
        
        # 添加标题
        header = ttk.Label(main_frame, text="Live Photo 备份工具", style="Header.TLabel")
        header.pack(pady=(0, 20), anchor=tk.W)
        
        # 创建上半部分框架
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 创建左侧面板（文件夹树和设置）
        left_panel = ttk.Frame(top_frame, width=350)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        left_panel.pack_propagate(False)  # 防止框架被子部件缩小
        
        # 创建右侧面板（预览和信息）
        right_panel = ttk.Frame(top_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 添加左侧的文件夹设置区域
        self.create_folder_settings(left_panel)
        
        # 添加左侧的文件夹树视图
        self.create_folder_tree(left_panel)
        
        # 添加右侧的图片预览区域
        self.create_preview_area(right_panel)
        
        # 添加底部区域（包含转换设置、进度条和按钮）
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 添加转换设置区域
        self.create_conversion_settings(bottom_frame)
        
        # 添加进度区域
        self.create_progress_area(bottom_frame)
        
        # 添加日志区域
        self.create_log_area(main_frame)
        
        # 添加底部状态栏
        self.create_status_bar(main_frame)
        
        # 创建菜单
        self.create_menu()
    
    def create_folder_settings(self, parent):
        """创建文件夹设置区域"""
        folder_frame = ttk.LabelFrame(parent, text="文件夹选择", padding="10")
        folder_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 输入目录
        ttk.Label(folder_frame, text="输入目录:").grid(row=0, column=0, sticky=tk.W, pady=5)
        input_entry = ttk.Entry(folder_frame, textvariable=self.input_dir)
        input_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        input_button = ttk.Button(folder_frame, text="浏览...", command=self.browse_input_dir)
        input_button.grid(row=0, column=2, padx=5, pady=5)
        
        # 输出目录
        ttk.Label(folder_frame, text="输出目录:").grid(row=1, column=0, sticky=tk.W, pady=5)
        output_entry = ttk.Entry(folder_frame, textvariable=self.output_dir)
        output_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        output_button = ttk.Button(folder_frame, text="浏览...", command=self.browse_output_dir)
        output_button.grid(row=1, column=2, padx=5, pady=5)
        
        # 配置列权重
        folder_frame.columnconfigure(1, weight=1)
    
    def create_folder_tree(self, parent):
        """创建文件夹树视图"""
        tree_frame = ttk.LabelFrame(parent, text="文件夹结构", padding="10")
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建树状视图和滚动条
        self.folder_tree = ttk.Treeview(tree_frame, selectmode='browse')
        self.folder_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.folder_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.folder_tree.config(yscrollcommand=scrollbar.set)
        
        # 设置列
        self.folder_tree["columns"] = ("files_count",)
        self.folder_tree.column("#0", width=180, minwidth=150)
        self.folder_tree.column("files_count", width=80, minwidth=50, anchor=tk.CENTER)
        
        self.folder_tree.heading("#0", text="文件夹")
        self.folder_tree.heading("files_count", text="文件数量")
        
        # 绑定事件
        self.folder_tree.bind("<<TreeviewSelect>>", self.on_folder_selected)
    
    def create_preview_area(self, parent):
        """创建预览区域"""
        preview_frame = ttk.LabelFrame(parent, text="文件预览", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 创建左侧预览图和右侧文件列表的布局
        preview_content = ttk.Frame(preview_frame)
        preview_content.pack(fill=tk.BOTH, expand=True)
        
        # 左侧预览图
        self.preview_panel = ttk.Label(preview_content, background="#EEEEEE")
        self.preview_panel.pack(side=tk.LEFT, padx=(0, 10), fill=tk.BOTH, expand=True)
        
        # 右侧文件列表
        files_frame = ttk.Frame(preview_content)
        files_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        # 文件列表标题
        ttk.Label(files_frame, text="文件列表:").pack(anchor=tk.W, pady=(0, 5))
        
        # 文件列表和滚动条
        files_list_frame = ttk.Frame(files_frame)
        files_list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.files_listbox = tk.Listbox(files_list_frame, background="#FFFFFF", 
                                        font=self.normal_font, activestyle='none',
                                        highlightthickness=1, highlightbackground="#CCCCCC")
        self.files_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(files_list_frame, orient=tk.VERTICAL, command=self.files_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.files_listbox.config(yscrollcommand=scrollbar.set)
        
        # 绑定事件
        self.files_listbox.bind('<<ListboxSelect>>', self.on_file_selected)
        
        # 文件信息区域
        info_frame = ttk.Frame(preview_frame)
        info_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.file_info_label = ttk.Label(info_frame, text="", wraplength=450, 
                                         foreground=self.secondary_text_color)
        self.file_info_label.pack(anchor=tk.W)
    
    def create_conversion_settings(self, parent):
        """创建转换设置区域"""
        options_frame = ttk.LabelFrame(parent, text="转换设置", padding="10")
        options_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # 创建内部框架以便更好地组织
        options_content = ttk.Frame(options_frame)
        options_content.pack(fill=tk.BOTH, expand=True)
        
        # 输出格式
        format_frame = ttk.Frame(options_content)
        format_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        ttk.Label(format_frame, text="LivePhoto输出格式:").pack(anchor=tk.W, pady=(0, 5))
        format_combo = ttk.Combobox(format_frame, textvariable=self.output_format, 
                                   values=["original", "mp4", "gif", "jpg"], 
                                   state="readonly", width=15)
        format_combo.pack(anchor=tk.W)
        format_combo.current(1)  # 默认选择mp4
        
        # 保留选项
        preserve_frame = ttk.Frame(options_content)
        preserve_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 10))
        
        ttk.Label(preserve_frame, text="保留选项:").pack(anchor=tk.W, pady=(0, 5))
        preserve_meta_check = ttk.Checkbutton(preserve_frame, text="保留元数据", 
                                             variable=self.preserve_metadata)
        preserve_meta_check.pack(anchor=tk.W)
        
        preserve_struct_check = ttk.Checkbutton(preserve_frame, text="保留目录结构", 
                                               variable=self.preserve_structure)
        preserve_struct_check.pack(anchor=tk.W)
        
        # 性能设置
        perf_frame = ttk.Frame(options_content)
        perf_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        ttk.Label(perf_frame, text="性能设置:").pack(anchor=tk.W, pady=(0, 5))
        
        thread_frame = ttk.Frame(perf_frame)
        thread_frame.pack(anchor=tk.W, fill=tk.X)
        
        ttk.Label(thread_frame, text="线程数:").pack(side=tk.LEFT)
        thread_spinbox = ttk.Spinbox(thread_frame, from_=1, to=multiprocessing.cpu_count()*2, 
                                    textvariable=self.thread_count, width=5)
        thread_spinbox.pack(side=tk.LEFT, padx=(5, 0))
        
        gpu_check = ttk.Checkbutton(perf_frame, text="使用GPU加速(如果可用)", 
                                   variable=self.use_gpu)
        gpu_check.pack(anchor=tk.W)
    
    def create_progress_area(self, parent):
        """创建进度区域"""
        progress_frame = ttk.LabelFrame(parent, text="进度", padding="10")
        progress_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 进度条
        self.progress = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress.pack(fill=tk.X, pady=(0, 5))
        
        # 进度标签
        self.progress_label = ttk.Label(progress_frame, text="就绪")
        self.progress_label.pack(anchor=tk.W, pady=(0, 10))
        
        # 按钮区
        button_frame = ttk.Frame(progress_frame)
        button_frame.pack(fill=tk.X)
        
        self.start_button = ttk.Button(button_frame, text="开始处理", 
                                      command=self.start_processing, 
                                      style="Accent.TButton", width=15)
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))
        self.start_button.config(state=tk.DISABLED)  # 初始禁用
        
        self.cancel_button = ttk.Button(button_frame, text="取消", 
                                       command=self.cancel_processing, width=15)
        self.cancel_button.pack(side=tk.LEFT)
        self.cancel_button.config(state=tk.DISABLED)
    
    def create_log_area(self, parent):
        """创建日志区域"""
        log_frame = ttk.LabelFrame(parent, text="处理日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建日志文本框和滚动条
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_container, wrap=tk.WORD, height=8, 
                              font=self.small_font, bg=self.bg_color, 
                              fg=self.text_color)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
    
    def create_status_bar(self, parent):
        """创建状态栏"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.status_label = ttk.Label(status_frame, text="准备就绪", 
                                    foreground=self.secondary_text_color,
                                    font=self.small_font)
        self.status_label.pack(side=tk.LEFT)
        
        # 添加版本信息到右侧
        version_label = ttk.Label(status_frame, text="v1.1", 
                                foreground=self.secondary_text_color,
                                font=self.small_font)
        version_label.pack(side=tk.RIGHT)
    
    def create_menu(self):
        """创建应用程序菜单"""
        menubar = tk.Menu(self.root)
        
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="选择输入目录", command=self.browse_input_dir)
        file_menu.add_command(label="选择输出目录", command=self.browse_output_dir)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        menubar.add_cascade(label="文件", menu=file_menu)
        
        # 工具菜单
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="检查依赖", command=self.check_ffmpeg)
        tools_menu.add_command(label="清空日志", command=self.clear_log)
        tools_menu.add_separator()
        tools_menu.add_command(label="刷新文件夹树", command=self.refresh_folder_tree)
        menubar.add_cascade(label="工具", menu=tools_menu)
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="使用说明", command=self.show_help)
        help_menu.add_command(label="关于", command=self.show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)
        
        self.root.config(menu=menubar)
    
    def check_ffmpeg(self):
        """检查ffmpeg是否可用"""
        self.log("检查FFmpeg依赖...")
        
        try:
            # 优先检查本地依赖目录中的ffmpeg
            if os.path.exists(self.ffmpeg_path):
                result = subprocess.run([self.ffmpeg_path, "-version"], 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE, 
                                     text=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                
                ffmpeg_version = re.search(r"ffmpeg version ([^\s]+)", result.stdout)
                if ffmpeg_version:
                    self.log(f"已找到本地FFmpeg: {ffmpeg_version.group(1)}")
                else:
                    self.log(f"已找到本地FFmpeg")
                
                # 检查GPU支持
                gpu_support = re.search(r"--enable-nvenc|--enable-cuda|--enable-cuvid", result.stdout)
                if gpu_support:
                    self.log("FFmpeg具有GPU加速支持")
                    self.use_gpu.set(True)
                else:
                    self.log("FFmpeg不支持GPU加速")
                    self.use_gpu.set(False)
                
                # 确保启用开始处理按钮（如果已设置输入目录）
                if self.input_dir.get():
                    self.update_button_states()
                
                return True
                
            else:
                # 如果本地依赖目录中没有ffmpeg，尝试使用系统安装的版本
                self.log("本地FFmpeg未找到，尝试使用系统FFmpeg...")
                result = subprocess.run(["ffmpeg", "-version"], 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE, 
                                     text=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                
                ffmpeg_version = re.search(r"ffmpeg version ([^\s]+)", result.stdout)
                if ffmpeg_version:
                    self.log(f"已找到系统FFmpeg: {ffmpeg_version.group(1)}")
                else:
                    self.log(f"已找到系统FFmpeg")
                
                # 检查GPU支持
                gpu_support = re.search(r"--enable-nvenc|--enable-cuda|--enable-cuvid", result.stdout)
                if gpu_support:
                    self.log("FFmpeg具有GPU加速支持")
                    self.use_gpu.set(True)
                else:
                    self.log("FFmpeg不支持GPU加速")
                    self.use_gpu.set(False)
                
                # 使用系统FFmpeg
                self.ffmpeg_path = "ffmpeg"
                self.ffprobe_path = "ffprobe"
                
                # 确保启用开始处理按钮（如果已设置输入目录）
                if self.input_dir.get():
                    self.update_button_states()
                
                return True
                
        except FileNotFoundError:
            self.log("错误: 未找到FFmpeg。如需处理LivePhoto视频部分，请确保安装FFmpeg。")
            messagebox.showwarning("缺少依赖项", 
                              "未找到FFmpeg。仍可处理普通图片文件，但无法处理LivePhoto的视频部分。\n\n"
                              "如需完整功能，请安装FFmpeg或确保应用程序目录下的dependencies文件夹中包含ffmpeg.exe。")
            return False
        except Exception as e:
            self.log(f"检查FFmpeg时出错: {str(e)}")
            return False
    
    def log(self, message):
        """添加消息到日志区域"""
        try:
            timestamp = time.strftime("%H:%M:%S")
            self.log_text.insert(tk.END, f"{timestamp} - {message}\n")
            self.log_text.see(tk.END)
            
            # 同时更新状态栏
            self.status_label.config(text=message)
            
            # 更新界面
            self.root.update_idletasks()
        except:
            # 防止在对象销毁后调用
            pass
    
    def clear_log(self):
        """清空日志区域"""
        self.log_text.delete(1.0, tk.END)
        self.log("日志已清空")
    
    def update_button_states(self):
        """更新按钮状态"""
        if self.is_processing:
            self.start_button.config(state=tk.DISABLED)
            self.cancel_button.config(state=tk.NORMAL)
        else:
            if self.input_dir.get():
                self.start_button.config(state=tk.NORMAL)
            else:
                self.start_button.config(state=tk.DISABLED)
            self.cancel_button.config(state=tk.DISABLED)
    
    def browse_input_dir(self):
        """选择输入目录"""
        directory = filedialog.askdirectory(title="选择源文件夹")
        if directory:
            self.input_dir.set(directory)
            self.log(f"已设置输入目录: {directory}")
            
            # 如果输出目录为空，默认设置为输入目录的父目录下的"Backup"子文件夹
            if not self.output_dir.get():
                parent_dir = os.path.dirname(directory)
                folder_name = os.path.basename(directory)
                default_output = os.path.join(parent_dir, f"{folder_name}_Backup")
                self.output_dir.set(default_output)
            
            # 更新按钮状态
            self.update_button_states()
            
            # 清空文件夹树并开始扫描
            self.clear_folder_tree()
            self.start_folder_scan()
    
    def browse_output_dir(self):
        """选择输出目录"""
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.output_dir.set(directory)
            self.log(f"已设置输出目录: {directory}")
    
    def clear_folder_tree(self):
        """清空文件夹树"""
        for item in self.folder_tree.get_children():
            self.folder_tree.delete(item)
        
        # 清空文件列表
        self.files_listbox.delete(0, tk.END)
        
        # 清空预览
        self.clear_preview()
    
    def clear_preview(self):
        """清空预览"""
        self.preview_panel.config(image="")
        self.preview_panel.image = None
        self.current_preview_file = None
        self.file_info_label.config(text="")
    
    def start_folder_scan(self):
        """开始文件夹扫描线程"""
        if self.folder_scan_thread and self.folder_scan_thread.is_alive():
            return
        
        input_dir = self.input_dir.get()
        if not input_dir or not os.path.exists(input_dir):
            return
        
        self.log(f"正在扫描文件夹: {input_dir}")
        self.folder_tree_data = {}
        
        # 启动扫描线程
        self.folder_scan_thread = threading.Thread(target=self.scan_folder_structure, args=(input_dir,))
        self.folder_scan_thread.daemon = True
        self.folder_scan_thread.start()
    
    def scan_folder_structure(self, root_dir):
        """扫描文件夹结构并填充文件夹树"""
        try:
            # 添加根目录
            folder_name = os.path.basename(root_dir)
            self.root.after(0, lambda: self.folder_tree.insert("", "end", folder_name, text=folder_name, values=("扫描中...")))
            
            # 递归扫描子目录
            for root, dirs, files in os.walk(root_dir):
                rel_path = os.path.relpath(root, os.path.dirname(root_dir))
                if rel_path == ".":
                    rel_path = folder_name
                
                # 计算此目录中的文件
                file_list = []
                live_photos = self.detect_live_photos(root, files)
                
                # 添加LivePhotos到文件列表
                for lp in live_photos:
                    file_list.append({
                        'path': lp['image'],
                        'type': 'livephoto',
                        'pair': lp['video']
                    })
                
                # 添加其他图片文件
                image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.heic'}
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in image_extensions:
                        file_path = os.path.join(root, file)
                        # 检查该文件是否已经作为LivePhoto的一部分
                        is_part_of_livephoto = False
                        for lp in live_photos:
                            if file_path == lp['image']:
                                is_part_of_livephoto = True
                                break
                        
                        if not is_part_of_livephoto:
                            file_list.append({
                                'path': file_path,
                                'type': 'image'
                            })
                
                # 添加.livp文件
                for file in files:
                    if file.lower().endswith('.livp'):
                        file_list.append({
                            'path': os.path.join(root, file),
                            'type': 'livp'
                        })
                
                # 保存文件列表到文件夹树数据
                self.folder_tree_data[rel_path] = file_list
                
                # 更新UI
                parent = ""
                parts = rel_path.split(os.sep)
                
                # 构建树的层次结构
                for i, part in enumerate(parts):
                    if i == 0:
                        current_path = part
                        parent = ""
                    else:
                        current_path = os.path.join(parts[0], *parts[1:i+1])
                        parent = os.path.join(parts[0], *parts[1:i])
                    
                    # 检查节点是否已存在
                    if not self.folder_tree.exists(current_path):
                        # 如果是当前处理的文件夹，添加正确的文件计数
                        if i == len(parts) - 1:
                            file_count = len(file_list)
                            self.root.after(0, lambda p=parent, c=current_path, n=part, fc=file_count: 
                                          self.folder_tree.insert(p, "end", c, text=n, values=(fc,)))
                        else:
                            # 对于中间文件夹，先用占位符添加
                            self.root.after(0, lambda p=parent, c=current_path, n=part: 
                                          self.folder_tree.insert(p, "end", c, text=n, values=("...")))
            
            # 完成扫描后更新根目录的文件计数
            total_files = sum(len(files) for files in self.folder_tree_data.values())
            self.root.after(0, lambda: self.folder_tree.item(folder_name, values=(total_files,)))
            
            # 日志更新
            self.root.after(0, lambda: self.log(f"扫描完成，共找到 {total_files} 个文件"))
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"扫描文件夹结构时出错: {str(e)}"))
    
    def detect_live_photos(self, directory, files):
        """在目录中检测Live Photos（图片+视频对）"""
        live_photos = []
        
        # 收集所有图片和视频文件
        image_files = []
        video_files = []
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.heic'}
        video_extensions = {'.mov', '.mp4'}
        
        for file in files:
            file_path = os.path.join(directory, file)
            ext = os.path.splitext(file)[1].lower()
            
            if ext in image_extensions:
                image_files.append(file_path)
            elif ext in video_extensions:
                video_files.append(file_path)
        
        # 配对Live Photos
        for image_path in image_files:
            base_name = os.path.splitext(image_path)[0]
            dir_name = os.path.dirname(image_path)
            file_name = os.path.basename(image_path)
            name_no_ext = os.path.splitext(file_name)[0]
            
            # 检查常规配对
            possible_videos = [
                base_name + ".mov",
                base_name + ".MOV",
            ]
            
            # 检查特殊命名格式 (iPhone Live Photos)
            if name_no_ext.startswith("IMG_") and not name_no_ext.startswith("IMG_E"):
                e_name = "IMG_E" + name_no_ext[4:] + ".MOV"
                possible_videos.append(os.path.join(dir_name, e_name))
            
            # 或者反过来
            if name_no_ext.startswith("IMG_E"):
                regular_name = "IMG_" + name_no_ext[5:] + ".MOV"
                possible_videos.append(os.path.join(dir_name, regular_name))
            
            # 查找匹配的视频文件
            for video_path in possible_videos:
                if video_path in video_files:
                    # 找到Live Photo
                    live_photos.append({
                        'image': image_path,
                        'video': video_path
                    })
                    break
                    
        return live_photos
    
    def on_folder_selected(self, event):
        """当在文件夹树中选择一个文件夹时触发"""
        selected_id = self.folder_tree.focus()
        if not selected_id:
            return
            
        # 清空文件列表和预览
        self.files_listbox.delete(0, tk.END)
        self.clear_preview()
        
        # 获取选中文件夹的文件列表
        if selected_id in self.folder_tree_data:
            files = self.folder_tree_data[selected_id]
            
            # 填充文件列表
            for i, file_info in enumerate(files):
                file_path = file_info['path']
                file_type = file_info['type']
                file_name = os.path.basename(file_path)
                
                # 为不同类型的文件添加图标前缀
                if file_type == 'livephoto':
                    display_name = "🎞️ " + file_name
                elif file_type == 'livp':
                    display_name = "📱 " + file_name
                else:
                    display_name = "🖼️ " + file_name
                
                self.files_listbox.insert(tk.END, display_name)
            
            # 如果有文件，选中第一个并显示预览
            if self.files_listbox.size() > 0:
                self.files_listbox.selection_set(0)
                self.on_file_selected(None)
    
    def on_file_selected(self, event):
        """当在文件列表中选择一个文件时触发"""
        if self.files_listbox.curselection():
            index = self.files_listbox.curselection()[0]
            selected_id = self.folder_tree.focus()
            
            if selected_id in self.folder_tree_data and index < len(self.folder_tree_data[selected_id]):
                file_info = self.folder_tree_data[selected_id][index]
                file_path = file_info['path']
                
                # 异步加载预览
                self.load_preview(file_info)
    
    def load_preview(self, file_info):
        """加载文件预览"""
        # 防止重复加载相同文件
        if self.current_preview_file == file_info['path']:
            return
            
        self.current_preview_file = file_info['path']
        file_path = file_info['path']
        file_type = file_info['type']
        
        # 显示文件信息
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / 1024  # KB
        
        info_text = f"文件: {file_name}\n"
        info_text += f"类型: {self.get_file_type_display(file_type)}\n"
        info_text += f"大小: {file_size:.1f} KB"
        
        if file_type == 'livephoto' and 'pair' in file_info:
            video_path = file_info['pair']
            video_name = os.path.basename(video_path)
            video_size = os.path.getsize(video_path) / 1024  # KB
            info_text += f"\n视频: {video_name}\n"
            info_text += f"视频大小: {video_size:.1f} KB"
        
        self.file_info_label.config(text=info_text)
        
        # 启动线程加载预览图像
        threading.Thread(target=self.generate_preview, args=(file_info,), daemon=True).start()
    
    def get_file_type_display(self, file_type):
        """获取文件类型的显示名称"""
        if file_type == 'livephoto':
            return "Live Photo"
        elif file_type == 'livp':
            return "Live Photo (LIVP格式)"
        elif file_type == 'image':
            return "普通图片"
        else:
            return "未知类型"
    
    def generate_preview(self, file_info):
        """生成文件预览"""
        try:
            file_path = file_info['path']
            file_type = file_info['type']
            
            # 创建缩略图
            if file_type == 'livephoto' or file_type == 'image':
                # 处理HEIC文件
                if file_path.lower().endswith('.heic'):
                    try:
                        # 使用临时文件转换HEIC为预览
                        temp_jpg = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
                        temp_jpg.close()
                        
                        # 先尝试使用PIL
                        try:
                            img = Image.open(file_path)
                            img.thumbnail(self.thumbnail_size)
                            img.save(temp_jpg.name, "JPEG")
                            img = Image.open(temp_jpg.name)
                        except:
                            # 如果PIL失败，使用ffmpeg
                            cmd = [
                                self.ffmpeg_path, "-i", file_path,
                                "-vf", f"scale={self.thumbnail_size[0]}:{self.thumbnail_size[1]}:force_original_aspect_ratio=decrease",
                                "-y", temp_jpg.name
                            ]
                            
                            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         text=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                            
                            img = Image.open(temp_jpg.name)
                        
                        photo = ImageTk.PhotoImage(img)
                        
                        # 更新UI
                        self.root.after(0, lambda: self.update_preview(photo))
                        
                        # 清理临时文件
                        try:
                            os.unlink(temp_jpg.name)
                        except:
                            pass
                            
                    except Exception as e:
                        self.root.after(0, lambda: self.log(f"HEIC预览生成失败: {str(e)}"))
                        self.root.after(0, lambda: self.show_default_preview("HEIC格式文件"))
                
                # 处理普通图片
                else:
                    try:
                        img = Image.open(file_path)
                        img.thumbnail(self.thumbnail_size)
                        photo = ImageTk.PhotoImage(img)
                        
                        # 更新UI
                        self.root.after(0, lambda: self.update_preview(photo))
                    except:
                        self.root.after(0, lambda: self.show_default_preview("图片预览失败"))
                
            elif file_type == 'livp':
                # 尝试从.livp中提取图片预览
                try:
                    temp_dir = tempfile.mkdtemp(prefix="livp_preview_")
                    try:
                        with zipfile.ZipFile(file_path, 'r') as zip_ref:
                            # 查找图片文件
                            image_file = None
                            for file in zip_ref.namelist():
                                if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                                    image_file = file
                                    break
                                elif file.lower().endswith('.heic'):
                                    # 如果只找到HEIC，也使用它
                                    image_file = file
                                    break
                            
                            if image_file:
                                # 提取图片到临时目录
                                extracted_path = os.path.join(temp_dir, os.path.basename(image_file))
                                with zip_ref.open(image_file) as source, open(extracted_path, 'wb') as target:
                                    shutil.copyfileobj(source, target)
                                
                                # 如果是HEIC格式，需要转换
                                if extracted_path.lower().endswith('.heic'):
                                    temp_jpg = os.path.join(temp_dir, "preview.jpg")
                                    try:
                                        # 尝试用PIL转换
                                        img = Image.open(extracted_path)
                                        img.save(temp_jpg, "JPEG")
                                        extracted_path = temp_jpg
                                    except:
                                        # 如果PIL失败，使用ffmpeg
                                        cmd = [
                                            self.ffmpeg_path, "-i", extracted_path,
                                            "-y", temp_jpg
                                        ]
                                        
                                        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                     text=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                                        
                                        extracted_path = temp_jpg
                                
                                # 创建缩略图
                                img = Image.open(extracted_path)
                                img.thumbnail(self.thumbnail_size)
                                photo = ImageTk.PhotoImage(img)
                                
                                # 更新UI
                                self.root.after(0, lambda: self.update_preview(photo))
                                return
                    finally:
                        # 清理临时目录
                        shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    self.root.after(0, lambda: self.log(f"LIVP预览生成失败: {str(e)}"))
                
                # 如果无法提取预览，显示默认图标
                self.root.after(0, lambda: self.show_default_preview("LIVP文件"))
                
            else:
                # 其他文件类型显示默认图标
                self.root.after(0, lambda: self.show_default_preview("未知文件类型"))
                
        except Exception as e:
            self.root.after(0, lambda: self.log(f"生成预览时出错: {str(e)}"))
            self.root.after(0, lambda: self.show_default_preview("预览生成失败"))
    
    def update_preview(self, photo):
        """更新预览面板的图像"""
        self.preview_panel.config(image=photo)
        self.preview_panel.image = photo  # 保持引用以防止垃圾回收
    
    def show_default_preview(self, message):
        """显示默认预览信息"""
        # 创建带有文本的图像
        img = Image.new('RGB', self.thumbnail_size, color=(240, 240, 240))
        photo = ImageTk.PhotoImage(img)
        self.update_preview(photo)
        
        # 更新信息标签添加消息
        current_text = self.file_info_label.cget("text")
        self.file_info_label.config(text=f"{current_text}\n\n{message}")
    
    def refresh_folder_tree(self):
        """刷新文件夹树"""
        input_dir = self.input_dir.get()
        if not input_dir:
            messagebox.showinfo("提示", "请先选择输入目录")
            return
            
        self.clear_folder_tree()
        self.start_folder_scan()
    
    def start_processing(self):
        """开始处理流程"""
        input_dir = self.input_dir.get()
        output_dir = self.output_dir.get()
        
        if not input_dir:
            messagebox.showwarning("未选择输入目录", "请选择源文件夹。")
            return
        
        if not output_dir:
            messagebox.showwarning("未选择输出目录", "请选择输出目录。")
            return
        
        # 如果输出目录不存在，则创建
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建输出目录: {str(e)}")
                return
        
        # 设置处理状态和取消标志
        self.is_processing = True
        self.cancel_flag.clear()
        self.update_button_states()
        
        # 开始处理线程
        thread = threading.Thread(target=self.processing_thread, args=(input_dir, output_dir))
        thread.daemon = True
        thread.start()
    
    def cancel_processing(self):
        """取消处理过程"""
        if self.is_processing:
            self.cancel_flag.set()
            self.log("正在取消操作...")
            self.progress_label.config(text="正在取消...")
    
    def processing_thread(self, input_dir, output_dir):
        """在单独的线程中执行处理"""
        try:
            # 查找所有文件
            self.log("正在扫描文件...")
            
            # 扫描所有文件
            all_files = self.scan_all_files(input_dir)
            
            # 分类文件
            file_types = self.classify_files(all_files)
            
            total_files = len(all_files)
            self.log(f"找到 {total_files} 个文件")
            
            if file_types['live_photos']:
                self.log(f"其中包含 {len(file_types['live_photos'])} 组Live Photos")
            if file_types['livp_files']:
                self.log(f"其中包含 {len(file_types['livp_files'])} 个.livp文件")
            if file_types['images']:
                self.log(f"其中包含 {len(file_types['images'])} 个普通图片")
            if file_types['others']:
                self.log(f"其中包含 {len(file_types['others'])} 个其他文件")
            
            # 设置进度条
            self.progress["maximum"] = total_files
            self.progress["value"] = 0
            
            # 创建处理队列
            task_queue = []
            
            # 添加Live Photos处理任务
            for live_photo in file_types['live_photos']:
                task_queue.append({
                    'type': 'livephoto',
                    'data': live_photo,
                    'input_dir': input_dir
                })
            
            # 添加.livp文件处理任务
            for livp_file in file_types['livp_files']:
                task_queue.append({
                    'type': 'livp',
                    'data': livp_file,
                    'input_dir': input_dir
                })
            
            # 添加普通图片处理任务
            for image_file in file_types['images']:
                task_queue.append({
                    'type': 'image',
                    'data': image_file,
                    'input_dir': input_dir
                })
            
            # 添加其他文件处理任务
            for other_file in file_types['others']:
                task_queue.append({
                    'type': 'other',
                    'data': other_file,
                    'input_dir': input_dir
                })
            
            # 使用线程池处理文件
            max_workers = self.thread_count.get()
            processed_count = 0
            error_count = 0
            result_queue = queue.Queue()
            
            self.log(f"使用 {max_workers} 个线程进行处理")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_task = {}
                for task in task_queue:
                    if self.cancel_flag.is_set():
                        break
                    
                    future = executor.submit(
                        self.process_file_task, 
                        task['type'], 
                        task['data'], 
                        task['input_dir'], 
                        output_dir
                    )
                    future_to_task[future] = task
                
                # 处理完成的任务
                for i, future in enumerate(as_completed(future_to_task)):
                    if self.cancel_flag.is_set():
                        break
                    
                    task = future_to_task[future]
                    try:
                        result = future.result()
                        if result['success']:
                            processed_count += 1
                        else:
                            error_count += 1
                            self.log(f"处理失败: {result['message']}")
                    except Exception as e:
                        error_count += 1
                        self.log(f"处理任务时出错: {str(e)}")
                    
                    # 更新进度
                    self.progress["value"] = i + 1
                    progress_percent = ((i + 1) / len(task_queue)) * 100
                    self.progress_label.config(text=f"处理中... {i+1}/{len(task_queue)} ({progress_percent:.1f}%)")
                    self.root.update_idletasks()
            
            # 完成处理
            if self.cancel_flag.is_set():
                # 在取消时保持当前进度，但更新文本
                self.progress_label.config(text=f"已取消 - 处理了 {processed_count}/{len(task_queue)} 个文件")
                self.log(f"操作已取消。已处理 {processed_count} 个文件，{error_count} 个错误。")
            else:
                # 正常完成时设置进度条达到100%
                self.progress["value"] = self.progress["maximum"]
                self.progress_label.config(text=f"处理完成 {len(task_queue)}/{len(task_queue)} (100%)")
                self.root.update_idletasks()
                self.log(f"处理完成！已处理 {processed_count} 个文件，{error_count} 个错误。")
                messagebox.showinfo("完成", f"已处理 {processed_count} 个文件，{error_count} 个错误。")
        
        except Exception as e:
            self.log(f"处理过程中出错: {str(e)}")
            messagebox.showerror("错误", f"处理过程中出错: {str(e)}")
        
        finally:
            self.is_processing = False
            self.progress_label.config(text="就绪")
            self.update_button_states()
    
    def process_file_task(self, file_type, file_data, input_dir, output_dir):
        """处理单个文件任务（在线程池中执行）"""
        try:
            if self.cancel_flag.is_set():
                return {'success': False, 'message': "操作已取消"}
            
            if file_type == 'livephoto':
                # 处理Live Photo
                image_file = file_data['image']
                video_file = file_data['video']
                
                # 确定目标路径
                rel_path = os.path.relpath(os.path.dirname(image_file), input_dir) if self.preserve_structure.get() else ""
                target_dir = os.path.join(output_dir, rel_path)
                os.makedirs(target_dir, exist_ok=True)
                
                # 处理Live Photo
                success = self.process_live_photo(image_file, video_file, target_dir)
                if success:
                    return {'success': True}
                else:
                    return {'success': False, 'message': f"处理Live Photo失败: {os.path.basename(image_file)}"}
            
            elif file_type == 'livp':
                # 处理.livp文件
                livp_file = file_data
                
                # 确定目标路径
                rel_path = os.path.relpath(os.path.dirname(livp_file), input_dir) if self.preserve_structure.get() else ""
                target_dir = os.path.join(output_dir, rel_path)
                os.makedirs(target_dir, exist_ok=True)
                
                # 处理.livp文件
                success = self.process_livp_file(livp_file, target_dir)
                if success:
                    return {'success': True}
                else:
                    return {'success': False, 'message': f"处理.livp文件失败: {os.path.basename(livp_file)}"}
            
            elif file_type == 'image':
                # 处理普通图片
                image_file = file_data
                
                # 确定目标路径
                rel_path = os.path.relpath(os.path.dirname(image_file), input_dir) if self.preserve_structure.get() else ""
                target_dir = os.path.join(output_dir, rel_path)
                os.makedirs(target_dir, exist_ok=True)
                
                # 复制图片文件
                target_file = os.path.join(target_dir, os.path.basename(image_file))
                shutil.copy2(image_file, target_file)
                return {'success': True}
            
            elif file_type == 'other':
                # 处理其他文件
                other_file = file_data
                
                # 确定目标路径
                rel_path = os.path.relpath(os.path.dirname(other_file), input_dir) if self.preserve_structure.get() else ""
                target_dir = os.path.join(output_dir, rel_path)
                os.makedirs(target_dir, exist_ok=True)
                
                # 复制文件
                target_file = os.path.join(target_dir, os.path.basename(other_file))
                shutil.copy2(other_file, target_file)
                return {'success': True}
            
            return {'success': False, 'message': f"未知文件类型: {file_type}"}
            
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def scan_all_files(self, directory):
        """递归扫描目录中的所有文件"""
        all_files = []
        
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                all_files.append(file_path)
        
        return all_files
    
    def classify_files(self, files):
        """将文件分为Live Photos、.livp文件、普通图片和其他文件"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.heic'}
        video_extensions = {'.mov', '.mp4'}
        
        # 初始化结果分类
        result = {
            'live_photos': [],  # 包含图片和视频路径的字典列表
            'livp_files': [],   # .livp文件路径列表
            'images': [],       # 普通图片路径列表
            'others': []        # 其他文件路径列表
        }
        
        # 先收集所有图片和视频文件
        images = []
        videos = []
        
        for file_path in files:
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext == '.livp':
                result['livp_files'].append(file_path)
            elif ext in image_extensions:
                images.append(file_path)
            elif ext in video_extensions:
                videos.append(file_path)
            else:
                result['others'].append(file_path)
        
        # 配对Live Photos
        matched_images = set()
        
        for image_path in images:
            base_name = os.path.splitext(image_path)[0]
            dir_name = os.path.dirname(image_path)
            file_name = os.path.basename(image_path)
            name_no_ext = os.path.splitext(file_name)[0]
            
            # 检查常规配对
            possible_videos = [
                base_name + ".mov",
                base_name + ".MOV",
            ]
            
            # 检查特殊命名格式
            if name_no_ext.startswith("IMG_") and not name_no_ext.startswith("IMG_E"):
                e_name = "IMG_E" + name_no_ext[4:] + ".MOV"
                possible_videos.append(os.path.join(dir_name, e_name))
            
            # 或者反过来
            if name_no_ext.startswith("IMG_E"):
                regular_name = "IMG_" + name_no_ext[5:] + ".MOV"
                possible_videos.append(os.path.join(dir_name, regular_name))
            
            # 查找匹配的视频文件
            matched_video = None
            for video_path in possible_videos:
                if video_path in videos:
                    matched_video = video_path
                    break
            
            if matched_video:
                # 找到Live Photo
                result['live_photos'].append({
                    'image': image_path,
                    'video': matched_video
                })
                matched_images.add(image_path)
            else:
                # 普通图片
                result['images'].append(image_path)
        
        # 添加未匹配的视频到其他文件
        for video_path in videos:
            # 检查这个视频是否已经被用于Live Photo
            is_matched = False
            for live_photo in result['live_photos']:
                if live_photo['video'] == video_path:
                    is_matched = True
                    break
            
            if not is_matched:
                result['others'].append(video_path)
        
        return result
    
    def process_live_photo(self, image_file, video_file, target_dir):
        """处理单个Live Photo"""
        try:
            output_format = self.output_format.get()
            filename = os.path.basename(image_file)
            name_no_ext = os.path.splitext(filename)[0]
            
            if output_format == "original":
                # 仅复制原始文件
                target_image = os.path.join(target_dir, filename)
                target_video = os.path.join(target_dir, os.path.basename(video_file))
                
                shutil.copy2(image_file, target_image)
                shutil.copy2(video_file, target_video)
                
                return True
            
            elif output_format == "mp4":
                # 转换为MP4
                target_file = os.path.join(target_dir, f"{name_no_ext}.mp4")
                return self.convert_to_mp4(video_file, target_file)
            
            elif output_format == "gif":
                # 转换为GIF
                target_file = os.path.join(target_dir, f"{name_no_ext}.gif")
                return self.convert_to_gif(video_file, target_file)
            
            elif output_format == "jpg":
                # 仅保存静态图像
                target_file = os.path.join(target_dir, f"{name_no_ext}.jpg")
                
                # 如果原图是HEIC，需要转换为JPG
                if image_file.lower().endswith('.heic'):
                    return self.convert_heic_to_jpg(image_file, target_file)
                else:
                    shutil.copy2(image_file, target_file)
                    return True
            
            return False
        
        except Exception as e:
            self.log(f"处理 Live Photo 时出错: {str(e)}")
            return False
    
    def process_livp_file(self, livp_path, target_dir):
        """处理.livp文件，提取并处理其内容"""
        try:
            # 创建临时目录
            temp_dir = tempfile.mkdtemp(prefix="livp_")
            
            try:
                # 尝试以ZIP格式打开.livp文件
                with zipfile.ZipFile(livp_path, 'r') as zip_ref:
                    # 列出.livp内的所有文件
                    files = zip_ref.namelist()
                    
                    # 查找关键文件
                    image_file = None
                    video_file = None
                    metadata_file = None
                    
                    for file in files:
                        lower_file = file.lower()
                        if lower_file.endswith(('.jpg', '.jpeg', '.heic', '.png')):
                            image_file = file
                        elif lower_file.endswith('.mov'):
                            video_file = file
                        elif lower_file == 'metadata.json' or lower_file.endswith('.json'):
                            metadata_file = file
                    
                    # 提取找到的文件
                    if image_file:
                        image_path = os.path.join(temp_dir, os.path.basename(image_file))
                        with zip_ref.open(image_file) as source, open(image_path, 'wb') as target:
                            shutil.copyfileobj(source, target)
                    
                    if video_file:
                        video_path = os.path.join(temp_dir, os.path.basename(video_file))
                        with zip_ref.open(video_file) as source, open(video_path, 'wb') as target:
                            shutil.copyfileobj(source, target)
                    
                    # 如果找到了图片和视频，则按照Live Photo处理
                    if image_file and video_file:
                        name_no_ext = os.path.splitext(os.path.basename(livp_path))[0]
                        output_format = self.output_format.get()
                        
                        if output_format == "original":
                            # 复制原始.livp文件
                            target_file = os.path.join(target_dir, os.path.basename(livp_path))
                            shutil.copy2(livp_path, target_file)
                            
                        else:
                            # 按照指定格式处理
                            self.process_live_photo(image_path, video_path, target_dir)
                        
                        return True
                    else:
                        # 如果只找到了图片
                        if image_file:
                            target_file = os.path.join(target_dir, os.path.basename(image_file))
                            shutil.copy2(image_path, target_file)
                            return True
                        else:
                            # 无法提取内容，只复制原始文件
                            target_file = os.path.join(target_dir, os.path.basename(livp_path))
                            shutil.copy2(livp_path, target_file)
                            return True
            
            except zipfile.BadZipFile:
                # 如果不是ZIP格式，复制原始文件
                target_file = os.path.join(target_dir, os.path.basename(livp_path))
                shutil.copy2(livp_path, target_file)
                return True
                
        except Exception as e:
            return False
        
        finally:
            # 清理临时文件
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    def convert_to_mp4(self, video_path, output_file):
        """将视频文件转换为MP4格式"""
        try:
            # 构建基本命令
            cmd = [
                self.ffmpeg_path, "-i", video_path,
                "-c:v", "libx264", "-crf", "23", 
                "-preset", "medium", "-c:a", "aac", 
                "-movflags", "+faststart"
            ]
            
            # 如果启用GPU加速，添加相应参数
            if self.use_gpu.get():
                # 尝试使用NVIDIA GPU加速
                cmd = [
                    self.ffmpeg_path, "-i", video_path,
                    "-c:v", "h264_nvenc", "-preset", "medium", 
                    "-c:a", "aac", "-movflags", "+faststart"
                ]
            
            # 添加输出文件
            cmd.extend(["-y", output_file])
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            
            if result.returncode != 0:
                # 如果GPU加速失败，尝试回退到CPU
                if self.use_gpu.get():
                    cmd = [
                        self.ffmpeg_path, "-i", video_path,
                        "-c:v", "libx264", "-crf", "23", 
                        "-preset", "medium", "-c:a", "aac", 
                        "-movflags", "+faststart", 
                        "-y", output_file
                    ]
                    
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         text=True,
                                         creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                    
                    if result.returncode != 0:
                        return False
                else:
                    return False
            
            return True
        
        except Exception as e:
            return False
    
    def convert_to_gif(self, video_path, output_file):
        """将视频文件转换为GIF格式"""
        try:
            # 使用较高质量设置创建GIF
            cmd = [
                self.ffmpeg_path, "-i", video_path,
                "-vf", "fps=10,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse", 
                "-y", output_file
            ]
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            
            if result.returncode != 0:
                return False
            
            return True
        
        except Exception as e:
            return False
    
    def convert_heic_to_jpg(self, heic_path, jpg_path):
        """将HEIC文件转换为JPG格式"""
        try:
            # 尝试使用PIL/Pillow转换
            img = Image.open(heic_path)
            img.save(jpg_path, "JPEG", quality=95)
            return True
        
        except Exception as e:
            try:
                # 如果PIL失败，尝试使用ffmpeg
                cmd = [
                    self.ffmpeg_path, "-i", heic_path,
                    "-q:v", "2", 
                    "-y", jpg_path
                ]
                
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                
                if result.returncode != 0:
                    # 如果ffmpeg也失败，记录错误但不抛出异常
                    return False
                
                return True
            
            except Exception as e2:
                # 如果所有方法都失败，记录错误
                return False
                
    def load_preview_heic(self, file_path):
        """专门处理HEIC文件的预览"""
        try:
            # 创建临时JPG文件
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_jpg_path = temp_file.name
            
            # 尝试使用PIL转换HEIC到JPG
            try:
                img = Image.open(file_path)
                img.thumbnail(self.thumbnail_size)
                img.save(temp_jpg_path, "JPEG", quality=90)
                
                # 加载JPG预览
                preview_img = Image.open(temp_jpg_path)
                photo = ImageTk.PhotoImage(preview_img)
                
                # 清理临时文件
                try:
                    os.unlink(temp_jpg_path)
                except:
                    pass
                
                return photo
                
            except Exception as e:
                # PIL失败，尝试ffmpeg
                cmd = [
                    self.ffmpeg_path, "-i", file_path,
                    "-vf", f"scale={self.thumbnail_size[0]}:{self.thumbnail_size[1]}:force_original_aspect_ratio=decrease",
                    "-y", temp_jpg_path
                ]
                
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                
                if result.returncode == 0 and os.path.exists(temp_jpg_path):
                    # 加载JPG预览
                    preview_img = Image.open(temp_jpg_path)
                    photo = ImageTk.PhotoImage(preview_img)
                    
                    # 清理临时文件
                    try:
                        os.unlink(temp_jpg_path)
                    except:
                        pass
                    
                    return photo
                else:
                    # 清理临时文件
                    try:
                        os.unlink(temp_jpg_path)
                    except:
                        pass
                    
                    return None
                    
        except Exception as e:
            return None
    
    def show_help(self):
        """显示使用说明"""
        help_text = """Live Photo备份工具使用说明:

功能:
1. 备份并可选转换Live Photos
2. 支持标准的Live Photo文件对（图片+视频）
3. 支持.livp格式文件
4. 备份普通图片文件（.jpg, .png, .gif等）
5. 可选保留子文件夹结构
6. 多线程并行处理，支持GPU加速
7. 文件夹结构预览
8. 文件预览功能

使用方法:
1. 选择源文件夹（包含需要备份的照片）
2. 选择输出目录
3. 选择Live Photo的输出格式:
   - original: 保持原始格式
   - mp4: 将动态部分转为MP4
   - gif: 将动态部分转为GIF
   - jpg: 仅保留静态图片部分
4. 设置处理选项和性能参数
5. 点击"开始处理"按钮

性能选项:
- 线程数: 设置并行处理的线程数量，通常设置为CPU核心数
- GPU加速: 如果系统支持，可启用GPU加速视频转码

注意:
- 建议保留目录结构以避免文件重名覆盖
- 处理大量文件时可能需要较长时间"""
        
        help_window = tk.Toplevel(self.root)
        help_window.title("使用说明")
        help_window.geometry("600x500")
        help_window.minsize(500, 400)
        help_window.configure(bg=self.bg_color)
        help_window.grab_set()  # 使帮助窗口成为模态窗口
        
        # 内边距容器
        padding_frame = ttk.Frame(help_window, padding="20")
        padding_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(padding_frame, text="Live Photo备份工具使用说明", 
                             font=self.header_font, foreground=self.text_color)
        title_label.pack(pady=(0, 15), anchor=tk.W)
        
        # 帮助文本
        text = tk.Text(padding_frame, wrap=tk.WORD, font=self.normal_font,
                      bg=self.bg_color, fg=self.text_color,
                      borderwidth=0, highlightthickness=0)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, help_text)
        text.config(state=tk.DISABLED)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(text, orient=tk.VERTICAL, command=text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.config(yscrollcommand=scrollbar.set)
        
        # 关闭按钮
        close_button = ttk.Button(padding_frame, text="关闭", 
                                command=help_window.destroy, width=15)
        close_button.pack(pady=(15, 0))
    
    def show_about(self):
        """显示关于对话框"""
        about_text = """Live Photo备份工具

版本: 1.1

功能:
- 备份和转换苹果Live Photos
- 支持.livp文件和标准Live Photos
- 保留照片元数据
- 备份普通图片文件
- 保留子文件夹结构
- 文件夹结构预览
- 文件预览功能
- 多线程并行处理
- GPU加速支持

© 2025 保留所有权利"""
        
        messagebox.showinfo("关于", about_text)


def main():
    # 创建应用程序根窗口
    root = tk.Tk()
    root.title("Live Photo备份工具")
    
    # 设置应用程序图标
    try:
        # 尝试设置窗口图标（如果有）
        if sys.platform == "win32":
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
    except:
        pass
    
    # 创建应用程序实例
    app = LivePhotoBackupTool(root)
    # 启动事件循环
    root.mainloop()


if __name__ == "__main__":
    main()