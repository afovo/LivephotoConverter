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
import json
from io import BytesIO
from pathlib import Path
import ctypes

class LivePhotoBackupTool:
    """LivePhoto备份与转换工具 - 支持LivePhoto和普通图片的备份与转换"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Live Photo备份工具")
        self.root.geometry("720x600")
        self.root.minsize(600, 500)  # 设置最小窗口大小
        
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
        #调用api设置成由应用程序缩放
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        #调用api获得当前的缩放因子
        ScaleFactor=ctypes.windll.shcore.GetScaleFactorForDevice(0)
        #设置缩放因子
        self.root.tk.call('tk', 'scaling', ScaleFactor/75)
        # 获取应用程序路径并设置依赖项路径
        self.app_path = self.get_app_path()
        self.dependencies_path = os.path.join(self.app_path, 'dependencies')
        self.ffmpeg_path = os.path.join(self.dependencies_path, 'ffmpeg.exe')
        self.ffprobe_path = os.path.join(self.dependencies_path, 'ffprobe.exe')
        self.ffplay_path = os.path.join(self.dependencies_path, 'ffplay.exe')
        
        # 正在处理的标志
        self.is_processing = False
        
        # 设置UI
        self.setup_ui()
        
        # 检查依赖
        self.check_ffmpeg()

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
        
        # 创建主容器并使用网格布局
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
        
        # 添加标题
        header = ttk.Label(main_frame, text="Live Photo 备份工具", style="Header.TLabel")
        header.pack(pady=(0, 20), anchor=tk.W)
        
        # 使用Frame封装内容区
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧设置区
        settings_frame = ttk.Frame(content_frame)
        settings_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # 右侧日志区
        log_frame = ttk.Frame(content_frame)
        log_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        # === 左侧设置区 ===
        # 文件夹选择区
        folder_frame = ttk.LabelFrame(settings_frame, text="文件夹选择", padding="10")
        folder_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 输入目录
        ttk.Label(folder_frame, text="输入目录:").grid(row=0, column=0, sticky=tk.W, pady=5)
        input_entry = ttk.Entry(folder_frame, textvariable=self.input_dir, width=30)
        input_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        input_button = ttk.Button(folder_frame, text="浏览...", command=self.browse_input_dir)
        input_button.grid(row=0, column=2, padx=5, pady=5)
        
        # 输出目录
        ttk.Label(folder_frame, text="输出目录:").grid(row=1, column=0, sticky=tk.W, pady=5)
        output_entry = ttk.Entry(folder_frame, textvariable=self.output_dir, width=30)
        output_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        output_button = ttk.Button(folder_frame, text="浏览...", command=self.browse_output_dir)
        output_button.grid(row=1, column=2, padx=5, pady=5)
        
        # 配置列权重以便Entry组件可以扩展
        folder_frame.columnconfigure(1, weight=1)
        
        # 转换设置区
        options_frame = ttk.LabelFrame(settings_frame, text="转换设置", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 输出格式
        ttk.Label(options_frame, text="LivePhoto输出格式:").grid(row=0, column=0, sticky=tk.W, pady=5)
        format_combo = ttk.Combobox(options_frame, textvariable=self.output_format, 
                                    values=["original", "mp4", "gif", "jpg"], 
                                    state="readonly", width=15)
        format_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        format_combo.current(0)  # 默认选择original
        
        # 保留元数据和目录结构选项
        preserve_meta_check = ttk.Checkbutton(options_frame, text="保留元数据", 
                                              variable=self.preserve_metadata)
        preserve_meta_check.grid(row=1, column=0, sticky=tk.W, pady=5)
        
        preserve_struct_check = ttk.Checkbutton(options_frame, text="保留目录结构", 
                                                variable=self.preserve_structure)
        preserve_struct_check.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # 进度区
        progress_frame = ttk.LabelFrame(settings_frame, text="进度", padding="10")
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.progress = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress.pack(fill=tk.X, pady=5)
        
        self.progress_label = ttk.Label(progress_frame, text="就绪")
        self.progress_label.pack(anchor=tk.W, pady=5)
        
        # 按钮区 (使用水平居中布局)
        button_frame = ttk.Frame(settings_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # 包装按钮到内部框架以允许居中
        inner_button_frame = ttk.Frame(button_frame)
        inner_button_frame.pack(anchor=tk.CENTER)
        
        self.start_button = ttk.Button(inner_button_frame, text="开始处理", 
                                       command=self.start_processing, 
                                       style="Accent.TButton", width=15)
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.start_button.config(state=tk.DISABLED)  # 初始禁用
        
        self.cancel_button = ttk.Button(inner_button_frame, text="取消", 
                                        command=self.cancel_processing, width=15)
        self.cancel_button.pack(side=tk.LEFT, padx=5)
        self.cancel_button.config(state=tk.DISABLED)
        
        # === 右侧日志区 ===
        log_label_frame = ttk.LabelFrame(log_frame, text="处理日志", padding="10")
        log_label_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_label_frame, wrap=tk.WORD, width=40, height=20, 
                               font=self.small_font, bg=self.bg_color, 
                               fg=self.text_color)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_label_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # 底部状态栏
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.status_label = ttk.Label(status_frame, text="准备就绪", 
                                     foreground=self.secondary_text_color,
                                     font=self.small_font)
        self.status_label.pack(side=tk.LEFT)
        
        # 添加版本信息到右侧
        version_label = ttk.Label(status_frame, text="v1.0", 
                                 foreground=self.secondary_text_color,
                                 font=self.small_font)
        version_label.pack(side=tk.RIGHT)
        
        # 创建菜单
        self.create_menu()
    
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
                
                # 检查ffprobe和ffplay
                if os.path.exists(self.ffprobe_path):
                    self.log("已找到本地FFprobe")
                else:
                    self.log("警告: 未找到本地FFprobe")
                
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
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"{timestamp} - {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
        # 同时更新状态栏
        self.status_label.config(text=message)
    
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
    
    def browse_output_dir(self):
        """选择输出目录"""
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.output_dir.set(directory)
            self.log(f"已设置输出目录: {directory}")
    
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
        
        # 设置处理状态
        self.is_processing = True
        self.update_button_states()
        
        # 开始处理线程
        thread = threading.Thread(target=self.processing_thread, args=(input_dir, output_dir))
        thread.daemon = True
        thread.start()
    
    def cancel_processing(self):
        """取消处理过程"""
        if self.is_processing:
            self.is_processing = False
            self.log("正在取消操作...")
            self.progress_label.config(text="正在取消...")
            self.update_button_states()
    
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
            
            # 处理文件
            processed_count = 0
            error_count = 0
            
            # 处理Live Photos
            for i, live_photo in enumerate(file_types['live_photos']):
                if not self.is_processing:
                    break
                
                try:
                    image_file = live_photo['image']
                    video_file = live_photo['video']
                    
                    self.progress_label.config(text=f"处理 Live Photo {i+1}/{len(file_types['live_photos'])}")
                    self.log(f"处理 Live Photo: {os.path.basename(image_file)}")
                    
                    # 确定目标路径
                    rel_path = os.path.relpath(os.path.dirname(image_file), input_dir) if self.preserve_structure.get() else ""
                    target_dir = os.path.join(output_dir, rel_path)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # 处理Live Photo
                    success = self.process_live_photo(image_file, video_file, target_dir)
                    if success:
                        processed_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    self.log(f"处理Live Photo时出错: {str(e)}")
                    error_count += 1
                
                self.progress["value"] += 1
                self.root.update_idletasks()
            
            # 处理.livp文件
            for i, livp_file in enumerate(file_types['livp_files']):
                if not self.is_processing:
                    break
                
                try:
                    self.progress_label.config(text=f"处理 .livp文件 {i+1}/{len(file_types['livp_files'])}")
                    self.log(f"处理 .livp文件: {os.path.basename(livp_file)}")
                    
                    # 确定目标路径
                    rel_path = os.path.relpath(os.path.dirname(livp_file), input_dir) if self.preserve_structure.get() else ""
                    target_dir = os.path.join(output_dir, rel_path)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # 处理.livp文件
                    success = self.process_livp_file(livp_file, target_dir)
                    if success:
                        processed_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    self.log(f"处理.livp文件时出错: {str(e)}")
                    error_count += 1
                
                self.progress["value"] += 1
                self.root.update_idletasks()
            
            # 处理普通图片
            for i, image_file in enumerate(file_types['images']):
                if not self.is_processing:
                    break
                
                try:
                    self.progress_label.config(text=f"处理图片 {i+1}/{len(file_types['images'])}")
                    
                    # 确定目标路径
                    rel_path = os.path.relpath(os.path.dirname(image_file), input_dir) if self.preserve_structure.get() else ""
                    target_dir = os.path.join(output_dir, rel_path)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # 复制图片文件
                    target_file = os.path.join(target_dir, os.path.basename(image_file))
                    shutil.copy2(image_file, target_file)
                    processed_count += 1
                except Exception as e:
                    self.log(f"复制图片时出错: {str(e)}")
                    error_count += 1
                
                self.progress["value"] += 1
                self.root.update_idletasks()
            
            # 处理其他文件
            for i, other_file in enumerate(file_types['others']):
                if not self.is_processing:
                    break
                
                try:
                    self.progress_label.config(text=f"处理其他文件 {i+1}/{len(file_types['others'])}")
                    
                    # 确定目标路径
                    rel_path = os.path.relpath(os.path.dirname(other_file), input_dir) if self.preserve_structure.get() else ""
                    target_dir = os.path.join(output_dir, rel_path)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # 复制文件
                    target_file = os.path.join(target_dir, os.path.basename(other_file))
                    shutil.copy2(other_file, target_file)
                    processed_count += 1
                except Exception as e:
                    self.log(f"复制文件时出错: {str(e)}")
                    error_count += 1
                
                self.progress["value"] += 1
                self.root.update_idletasks()
            
            # 完成处理
            if not self.is_processing:
                self.log(f"操作已取消。已处理 {processed_count} 个文件，{error_count} 个错误。")
            else:
                self.log(f"处理完成！已处理 {processed_count} 个文件，{error_count} 个错误。")
                messagebox.showinfo("完成", f"已处理 {processed_count} 个文件，{error_count} 个错误。")
        
        except Exception as e:
            self.log(f"处理过程中出错: {str(e)}")
            messagebox.showerror("错误", f"处理过程中出错: {str(e)}")
        
        finally:
            self.is_processing = False
            self.progress_label.config(text="就绪")
            self.update_button_states()
    
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
            'livp_files': [],  # .livp文件路径列表
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
        self.log(f"正在解析 .livp 文件: {os.path.basename(livp_path)}")
        
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
                            self.log(f"在.livp文件中未找到必要的组件，将复制原始文件")
                            target_file = os.path.join(target_dir, os.path.basename(livp_path))
                            shutil.copy2(livp_path, target_file)
                            return True
            
            except zipfile.BadZipFile:
                # 如果不是ZIP格式，复制原始文件
                self.log(".livp文件不是有效的ZIP格式，将复制原始文件")
                target_file = os.path.join(target_dir, os.path.basename(livp_path))
                shutil.copy2(livp_path, target_file)
                return True
                
        except Exception as e:
            self.log(f"处理.livp文件时出错: {str(e)}")
            return False
        
        finally:
            # 清理临时文件
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    def convert_to_mp4(self, video_path, output_file):
        """将视频文件转换为MP4格式"""
        try:
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
                self.log(f"转换MP4失败: {result.stderr}")
                return False
            
            return True
        
        except Exception as e:
            self.log(f"转换MP4时出错: {str(e)}")
            return False
    
    def convert_to_gif(self, video_path, output_file):
        """将视频文件转换为GIF格式"""
        try:
            cmd = [
                self.ffmpeg_path, "-i", video_path,
                "-vf", "fps=10,scale=480:-1:flags=lanczos", 
                "-y", output_file
            ]
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            
            if result.returncode != 0:
                self.log(f"转换GIF失败: {result.stderr}")
                return False
            
            return True
        
        except Exception as e:
            self.log(f"转换GIF时出错: {str(e)}")
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
                    self.log(f"转换HEIC失败: {result.stderr}")
                    return False
                
                return True
            
            except Exception as e2:
                self.log(f"转换HEIC时出错: {str(e2)}")
                return False
    
    def show_help(self):
        """显示使用说明"""
        help_text = """Live Photo备份工具使用说明:

功能:
1. 备份并可选转换Live Photos
2. 支持标准的Live Photo文件对（图片+视频）
3. 支持.livp格式文件
4. 备份普通图片文件（.jpg, .png, .gif等）
5. 可选保留子文件夹结构

使用方法:
1. 选择源文件夹（包含需要备份的照片）
2. 选择输出目录
3. 选择Live Photo的输出格式:
   - original: 保持原始格式
   - mp4: 将动态部分转为MP4
   - gif: 将动态部分转为GIF
   - jpg: 仅保留静态图片部分
4. 选择是否保留元数据和目录结构
5. 点击"开始处理"按钮

注意:
- 建议保留目录结构以避免文件重名覆盖
- 处理大量文件时可能需要较长时间"""
        
        help_window = tk.Toplevel(self.root)
        help_window.title("使用说明")
        help_window.geometry("550x450")
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

版本: 1.0

功能:
- 备份和转换苹果Live Photos
- 支持.livp文件和标准Live Photos
- 保留照片元数据
- 备份普通图片文件
- 保留子文件夹结构

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