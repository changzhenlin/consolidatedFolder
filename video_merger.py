import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import threading
import platform
import tempfile
import re
import json

class VideoMerger:
    # 应用程序信息
    APP_VERSION = "1.0.0"
    
    def __init__(self, root):
        self.root = root
        self.root.title(f"视频合并工具 v{self.APP_VERSION}")
        self.root.geometry("750x500")
        self.root.resizable(True, True)
        
        # 尝试设置窗口图标
        self._set_window_icon()
        
        # 设置中文字体支持
        self._setup_fonts()
        
        # 合并控制变量
        self.processing = False
        self.merge_thread = None
        self.selected_files = []
        self.ffmpeg_process = None
        self.temp_files = []
        # 添加新的状态变量
        self.ffmpeg_version = "未检测到"
        self.total_duration = 0
        self.ffmpeg_available = False
        self.progress_details_var = tk.StringVar(value="准备就绪")
        self.file_info_var = tk.StringVar(value="文件数量: 0 | 总时长: 00:00:00 | 总大小: 0.00 MB")
        self.ffmpeg_status_var = tk.StringVar(value="ffmpeg: 检测中...")
        
        # 确保应用程序正确退出
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # 创建主框架
        self.main_frame = ttk.Frame(root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建文件选择区域
        self.file_control_frame = ttk.Frame(self.main_frame)
        self.file_control_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.add_button = ttk.Button(self.file_control_frame, text="添加视频", command=self.add_videos)
        self.add_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.remove_button = ttk.Button(self.file_control_frame, text="移除选中", command=self.remove_selected, state=tk.DISABLED)
        self.remove_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.move_up_button = ttk.Button(self.file_control_frame, text="上移", command=self.move_selected_up, state=tk.DISABLED)
        self.move_up_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.move_down_button = ttk.Button(self.file_control_frame, text="下移", command=self.move_selected_down, state=tk.DISABLED)
        self.move_down_button.pack(side=tk.LEFT)
        
        # 创建文件列表区域
        self.file_list_frame = ttk.LabelFrame(self.main_frame, text="视频文件列表")
        self.file_list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # 创建文件列表树状视图
        columns = ("name", "path", "duration")
        self.file_tree = ttk.Treeview(self.file_list_frame, columns=columns, show="headings")
        
        # 设置列宽和标题
        self.file_tree.heading("name", text="文件名")
        self.file_tree.heading("path", text="路径")
        self.file_tree.heading("duration", text="时长")
        
        self.file_tree.column("name", width=150, anchor=tk.W)
        self.file_tree.column("path", width=400, anchor=tk.W)
        self.file_tree.column("duration", width=100, anchor=tk.CENTER)
        
        # 添加垂直滚动条
        vscrollbar = ttk.Scrollbar(self.file_list_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscroll=vscrollbar.set)
        
        # 添加水平滚动条
        hscrollbar = ttk.Scrollbar(self.file_list_frame, orient=tk.HORIZONTAL, command=self.file_tree.xview)
        self.file_tree.configure(xscroll=hscrollbar.set)
        
        # 放置树状视图和滚动条
        self.file_tree.grid(row=0, column=0, sticky=tk.NSEW)
        vscrollbar.grid(row=0, column=1, sticky=tk.NS)
        hscrollbar.grid(row=1, column=0, sticky=tk.EW)
        
        # 配置网格权重，使树状视图能够随窗口大小调整
        self.file_list_frame.grid_rowconfigure(0, weight=1)
        self.file_list_frame.grid_columnconfigure(0, weight=1)
        
        # 绑定选择事件，更新按钮状态
        self.file_tree.bind("<<TreeviewSelect>>", self._on_file_select)
        
        # 添加右键菜单支持
        self.file_tree.bind("<Button-3>", self.show_context_menu)
        self._create_context_menu()
        
        # 添加拖放支持
        self.file_tree.bind("<Button-1>", self._on_item_click)
        self.file_tree.bind("<B1-Motion>", self._on_item_drag)
        self.drag_item = None
        
        # 添加键盘快捷键
        self.root.bind("<Delete>", lambda event: self.remove_selected())
        self.root.bind("<Up>", lambda event: self.move_selected_up())
        self.root.bind("<Down>", lambda event: self.move_selected_down())
        
        # 创建合并控制区域
        self.merge_control_frame = ttk.Frame(self.main_frame)
        self.merge_control_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.output_label = ttk.Label(self.merge_control_frame, text="输出文件:")
        self.output_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.output_path_var = tk.StringVar()
        self.output_entry = ttk.Entry(self.merge_control_frame, textvariable=self.output_path_var, width=50)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.browse_output_button = ttk.Button(self.merge_control_frame, text="浏览...", command=self.browse_output)
        self.browse_output_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 创建进度条区域
        self.progress_frame = ttk.LabelFrame(self.main_frame, text="处理进度")
        self.progress_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, length=500, mode='determinate')
        self.progress_bar.pack(fill=tk.X, expand=True, pady=(10, 5), padx=10)
        
        # 进度详情标签
        self.progress_details_label = ttk.Label(self.progress_frame, textvariable=self.progress_details_var, anchor="w")
        self.progress_details_label.pack(fill=tk.X, pady=(0, 10), padx=10)
        
        # 创建执行按钮区域
        self.action_frame = ttk.Frame(self.main_frame)
        self.action_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.merge_button = ttk.Button(self.action_frame, text="开始合并", command=self.start_merge, state=tk.DISABLED)
        self.merge_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.cancel_button = ttk.Button(self.action_frame, text="取消", command=self.cancel_merge, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT)
        
        # 文件列表信息区域
        self.file_info_frame = ttk.Frame(self.main_frame)
        self.file_info_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.file_info_label = ttk.Label(self.file_info_frame, textvariable=self.file_info_var, anchor="w")
        self.file_info_label.pack(fill=tk.X, padx=5)
        
        # 创建底部状态栏
        self.status_frame = ttk.Frame(self.main_frame, relief=tk.SUNKEN, padding=(5, 2))
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))
        
        # 创建ffmpeg状态标签
        self.ffmpeg_status_label = ttk.Label(self.status_frame, textvariable=self.ffmpeg_status_var, anchor="w", font=self._get_small_font())
        self.ffmpeg_status_label.pack(side=tk.LEFT, padx=(5, 20))
        
        # 创建状态信息标签
        self.status_var = tk.StringVar(value="准备就绪，请添加视频文件")
        self.status_label = ttk.Label(self.status_frame, textvariable=self.status_var, anchor="w", font=self._get_small_font())
        self.status_label.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        
        # 创建版本信息标签
        self.version_label = ttk.Label(self.status_frame, text=f"v{self.APP_VERSION}", font=self._get_small_font())
        self.version_label.pack(side=tk.RIGHT, padx=5)
        
        # 欢迎信息
        self._show_welcome_message()
        
        # 检查ffmpeg是否可用
        self._check_ffmpeg_available()
    
    def _setup_fonts(self):
        """设置中文字体支持"""
        self.style = ttk.Style()
        
        # 根据操作系统调整字体设置
        system = platform.system()
        if system == "Windows":
            # Windows 系统通常支持 SimHei 或 Microsoft YaHei
            self.default_font = ('Microsoft YaHei UI', 9)
            self.small_font = ('Microsoft YaHei UI', 8)
        elif system == "Darwin":  # macOS
            self.default_font = ('Heiti TC', 9)
            self.small_font = ('Heiti TC', 8)
        else:  # Linux 或其他系统
            self.default_font = ('WenQuanYi Micro Hei', 9)
            self.small_font = ('WenQuanYi Micro Hei', 8)
        
        # 设置默认字体样式
        self.style.configure('.', font=self.default_font)
        
        return {'default': self.default_font, 'small': self.small_font}
    
    def _get_small_font(self):
        """获取小字体设置"""
        if hasattr(self, 'small_font'):
            return self.small_font
        # 如果小字体未初始化，则调用_setup_fonts
        fonts = self._setup_fonts()
        return fonts['small']
        
    def _format_duration(self, seconds):
        """将秒数格式化为时:分:秒"""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _set_window_icon(self):
        """尝试设置窗口图标"""
        # 在实际使用中，可以添加自定义图标
        # 这里只是一个示例，实际使用时需要提供图标文件路径
        try:
            # 这里可以添加图标设置代码
            pass
        except Exception:
            # 如果图标设置失败，静默忽略
            pass
    
    def _show_welcome_message(self):
        """显示欢迎信息"""
        pass
    
    def _on_closing(self):
        """处理窗口关闭事件"""
        if self.processing:
            if messagebox.askyesno("确认退出", "合并正在进行中，确定要退出吗？"):
                self.processing = False
                # 等待处理线程结束
                if self.merge_thread and self.merge_thread.is_alive():
                    self.merge_thread.join(timeout=1.0)  # 等待最多1秒
                self.root.destroy()
        else:
            self.root.destroy()
    
    def _check_ffmpeg_available(self):
        """检查系统是否安装了ffmpeg并获取版本信息"""
        try:
            # 尝试运行ffmpeg -version命令
            result = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True)
            self.ffmpeg_available = True
            
            # 提取ffmpeg版本信息
            version_line = result.stdout.split('\n')[0]
            version_match = re.search(r'ffmpeg version (\S+)', version_line)
            if version_match:
                self.ffmpeg_version = version_match.group(1)
                self.ffmpeg_status_var.set(f"ffmpeg: v{self.ffmpeg_version}")
            else:
                self.ffmpeg_status_var.set(f"ffmpeg: 已安装")
        except (subprocess.SubprocessError, FileNotFoundError):
            self.ffmpeg_available = False
            self.ffmpeg_status_var.set("ffmpeg: 未检测到")
            self.status_var.set("警告: 未找到ffmpeg，请安装ffmpeg以使用视频合并功能")
            messagebox.showwarning("ffmpeg未安装", "请下载并安装ffmpeg，将其添加到系统PATH中以使用视频合并功能。\n\n可从 https://ffmpeg.org/download.html 下载")
    
    def _on_file_select(self, event=None):
        """处理文件选择事件，更新按钮状态"""
        selected_items = self.file_tree.selection()
        has_selection = len(selected_items) > 0
        
        self.remove_button.config(state=tk.NORMAL if has_selection else tk.DISABLED)
        self.move_up_button.config(state=tk.NORMAL if has_selection else tk.DISABLED)
        self.move_down_button.config(state=tk.NORMAL if has_selection else tk.DISABLED)
        
        # 检查是否有文件添加，更新合并按钮状态
        self._update_merge_button_state()
    
    def _update_merge_button_state(self):
        """更新合并按钮状态"""
        # 降低按钮启用条件，只要有至少一个文件且ffmpeg可用就启用
        has_files = len(self.selected_files) >= 1
        is_available = self.ffmpeg_available
        
        self.merge_button.config(state=tk.NORMAL if (has_files and is_available) else tk.DISABLED)
    
    def _create_context_menu(self):
        """创建右键菜单"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="添加视频", command=self.add_videos)
        self.context_menu.add_command(label="移除选中", command=self.remove_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="上移", command=self.move_selected_up)
        self.context_menu.add_command(label="下移", command=self.move_selected_down)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="清空列表", command=self.clear_file_list)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="按文件名排序", command=self.sort_files_by_name)
    
    def show_context_menu(self, event):
        """显示右键菜单"""
        # 选中点击的项目
        item = self.file_tree.identify_row(event.y)
        if item:
            self.file_tree.selection_set(item)
            self.file_tree.focus(item)
        
        # 更新菜单状态
        has_selection = len(self.file_tree.selection()) > 0
        self.context_menu.entryconfig("移除选中", state=tk.NORMAL if has_selection else tk.DISABLED)
        self.context_menu.entryconfig("上移", state=tk.NORMAL if has_selection else tk.DISABLED)
        self.context_menu.entryconfig("下移", state=tk.NORMAL if has_selection else tk.DISABLED)
        
        # 显示菜单
        self.context_menu.post(event.x_root, event.y_root)
    
    def _on_item_click(self, event):
        """处理项目点击事件，用于拖放"""
        item = self.file_tree.identify_row(event.y)
        if item:
            self.drag_item = item
    
    def _on_item_drag(self, event):
        """处理项目拖动事件"""
        if not self.drag_item:
            return
        
        # 获取目标位置
        target_item = self.file_tree.identify_row(event.y)
        if target_item and target_item != self.drag_item:
            # 获取索引
            drag_index = int(self.drag_item)
            target_index = int(target_item)
            
            # 移动项目
            file_to_move = self.selected_files.pop(drag_index)
            # 调整目标索引，因为我们已经移除了一个项目
            if target_index > drag_index:
                target_index -= 1
            self.selected_files.insert(target_index, file_to_move)
            
            # 更新列表
            self._update_file_list()
            
            # 更新拖动项
            self.drag_item = str(target_index)
            self.file_tree.selection_set(self.drag_item)
            self.file_tree.focus(self.drag_item)
    
    def clear_file_list(self):
        """清空文件列表"""
        if not self.selected_files:
            return
        
        if messagebox.askyesno("确认", "确定要清空所有文件吗？"):
            self.selected_files.clear()
            self._update_file_list()
            self.status_var.set("文件列表已清空")
    
    def sort_files_by_name(self):
        """按文件名排序文件列表"""
        if len(self.selected_files) <= 1:
            return
        
        # 使用自然排序，这样数字会按顺序排列
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split('(\\d+)', os.path.basename(s))]
        
        self.selected_files.sort(key=natural_sort_key)
        self._update_file_list()
        self.status_var.set("文件已按名称排序")
    
    def add_videos(self):
        """添加视频文件"""
        # 支持的视频文件格式
        video_extensions = [".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".m4v"]
        file_types = [("视频文件", ";".join(["*" + ext for ext in video_extensions]))]
        
        try:
            # 设置对话框的初始目录
            initial_dir = os.path.expanduser("~")  # 使用用户主目录作为默认目录
            if self.selected_files:
                initial_dir = os.path.dirname(self.selected_files[-1])
            
            file_paths = filedialog.askopenfilenames(
                initialdir=initial_dir,
                title="选择要合并的视频文件",
                filetypes=file_types
            )
            
            if file_paths:
                # 添加新文件，避免重复
                new_files = []
                for file_path in file_paths:
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
                        new_files.append(file_path)
                
                # 更新文件列表显示
                self._update_file_list()
                
                # 如果是第一次添加文件，自动设置输出路径
                if not self.output_path_var.get() and self.selected_files:
                    dir_path = os.path.dirname(self.selected_files[0])
                    base_name = os.path.basename(self.selected_files[0]).split('.')[0]
                    output_path = os.path.join(dir_path, f"{base_name}_merged.mp4")
                    self.output_path_var.set(output_path)
                
                self.status_var.set(f"已添加 {len(new_files)} 个视频文件")
                
        except Exception as e:
            messagebox.showerror("错误", f"添加文件时发生错误: {str(e)}")
    
    def remove_selected(self):
        """移除选中的文件"""
        selected_items = self.file_tree.selection()
        if not selected_items:
            return
        
        # 按索引降序排序，避免删除时索引变化
        selected_indices = sorted([int(item) for item in selected_items], reverse=True)
        
        # 从列表中删除文件
        for index in selected_indices:
            if 0 <= index < len(self.selected_files):
                del self.selected_files[index]
        
        # 更新文件列表显示
        self._update_file_list()
        self.status_var.set(f"已移除 {len(selected_indices)} 个视频文件")
    
    def move_selected_up(self):
        """将选中的文件上移"""
        selected_items = self.file_tree.selection()
        if not selected_items:
            return
        
        # 支持多选中移
        # 先排序选中的索引
        selected_indices = sorted([int(item) for item in selected_items])
        
        # 检查是否可以移动
        if selected_indices[0] == 0:
            return  # 已经是第一个，无法上移
        
        # 创建新的文件列表
        new_files = []
        i = 0
        moved = False
        
        while i < len(self.selected_files):
            if not moved and i == selected_indices[0] - 1:
                # 先添加要移动的文件
                for idx in selected_indices:
                    new_files.append(self.selected_files[idx])
                moved = True
            elif i not in selected_indices:
                new_files.append(self.selected_files[i])
            i += 1
        
        # 更新文件列表
        self.selected_files = new_files
        self._update_file_list()
        
        # 重新选中移动后的项目
        new_selected = [str(selected_indices[0] - 1 + j) for j in range(len(selected_indices))]
        self.file_tree.selection_set(new_selected)
        self.file_tree.focus(new_selected[0])
    
    def move_selected_down(self):
        """将选中的文件下移"""
        selected_items = self.file_tree.selection()
        if not selected_items:
            return
        
        # 支持多选下移
        # 先排序选中的索引
        selected_indices = sorted([int(item) for item in selected_items], reverse=True)
        
        # 检查是否可以移动
        if selected_indices[0] == len(self.selected_files) - 1:
            return  # 已经是最后一个，无法下移
        
        # 创建新的文件列表
        new_files = []
        i = len(self.selected_files) - 1
        moved = False
        
        while i >= 0:
            if not moved and i == selected_indices[0] + 1:
                # 先添加要移动的文件
                for idx in reversed(selected_indices):
                    new_files.insert(0, self.selected_files[idx])
                moved = True
            elif i not in selected_indices:
                new_files.insert(0, self.selected_files[i])
            i -= 1
        
        # 更新文件列表
        self.selected_files = new_files
        self._update_file_list()
        
        # 重新选中移动后的项目
        new_selected = [str(selected_indices[0] + 1 - j) for j in range(len(selected_indices))]
        self.file_tree.selection_set(new_selected)
        self.file_tree.focus(new_selected[0])
    
    def _update_file_list(self):
        """更新文件列表显示并计算总信息"""
        # 清空当前列表
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        # 重置总信息
        total_duration = 0
        total_size = 0
        valid_files = 0
        
        # 添加文件到列表
        for i, file_path in enumerate(self.selected_files):
            filename = os.path.basename(file_path)
            dir_path = os.path.dirname(file_path)
            file_size = os.path.getsize(file_path)
            total_size += file_size
            
            # 尝试获取视频时长
            try:
                duration_seconds = self._get_video_duration_seconds(file_path)
                if isinstance(duration_seconds, float):
                    duration_str = self._format_duration(duration_seconds)
                    total_duration += duration_seconds
                    valid_files += 1
                else:
                    duration_str = duration_seconds
            except Exception:
                duration_str = "未知"
            
            # 使用索引作为item的ID，方便后续操作
            self.file_tree.insert("", tk.END, iid=str(i), values=(filename, dir_path, duration_str))
        
        # 更新文件列表信息
        total_duration_str = self._format_duration(total_duration)
        total_size_str = self._format_size(total_size)
        self.file_info_var.set(f"文件数量: {len(self.selected_files)} | 总时长: {total_duration_str} | 总大小: {total_size_str}")
        self.total_duration = total_duration
        
        # 更新按钮状态
        self._update_merge_button_state()

    def _get_video_duration(self, file_path):
        """使用ffmpeg获取视频文件时长（格式化显示）"""
        duration_seconds = self._get_video_duration_seconds(file_path)
        if isinstance(duration_seconds, float):
            return self._format_duration(duration_seconds)
        return duration_seconds
        
    def _get_video_duration_seconds(self, file_path):
        """使用ffprobe获取视频时长（秒数）"""
        if not self.ffmpeg_available:
            return "未知"
        
        try:
            # 先尝试使用JSON格式
            cmd = [
                'ffprobe', 
                '-v', 'error', 
                '-show_entries', 'format=duration', 
                '-of', 'json', 
                file_path
            ]
            
            # 处理Windows路径问题
            if platform.system() == "Windows":
                file_path = file_path.replace('\\', '\\\\')
                cmd[-1] = file_path
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            try:
                data = json.loads(result.stdout)
                return float(data['format']['duration'])
            except (json.JSONDecodeError, KeyError):
                # 如果JSON解析失败，回退到原始方法
                cmd_old = [
                    'ffprobe', 
                    '-v', 'error', 
                    '-show_entries', 'format=duration', 
                    '-of', 'default=noprint_wrappers=1:nokey=1', 
                    file_path
                ]
                result = subprocess.run(cmd_old, capture_output=True, text=True, check=False)
                return float(result.stdout.strip())
        except Exception:
            return "未知"
    
    def _check_video_compatibility(self):
        """检查视频文件的兼容性"""
        if len(self.selected_files) < 2:
            return True, ""
        
        if not self.ffmpeg_available:
            return False, "未安装ffmpeg，无法检查视频兼容性"
        
        # 检查第一个视频的编码和分辨率
        first_video_info = self._get_video_info(self.selected_files[0])
        if not first_video_info:
            return False, f"无法读取第一个视频文件的信息: {self.selected_files[0]}"
        
        # 检查后续视频是否兼容
        incompatible_files = []
        for i, file_path in enumerate(self.selected_files[1:], 1):
            video_info = self._get_video_info(file_path)
            if not video_info:
                return False, f"无法读取视频文件的信息: {file_path}"
            
            # 检查编码和分辨率是否匹配
            if (video_info['codec_name'] != first_video_info['codec_name'] or
                video_info['width'] != first_video_info['width'] or
                video_info['height'] != first_video_info['height'] or
                video_info['pix_fmt'] != first_video_info['pix_fmt']):
                incompatible_files.append((i + 1, os.path.basename(file_path)))
        
        if incompatible_files:
            message = "以下视频文件与第一个视频不兼容（编码或分辨率不同）:\n"
            for idx, filename in incompatible_files:
                message += f"{idx}. {filename}\n"
            message += "\n建议: 确保所有视频使用相同的编码器和分辨率，否则合并可能失败或产生异常结果。\n继续合并吗？"
            return False, message
        
        return True, ""
    
    def _get_video_info(self, file_path):
        """获取视频文件的基本信息"""
        try:
            # 使用ffprobe获取视频流信息
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,width,height,pix_fmt",
                "-of", "json",
                file_path
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=False
            )
            
            if result.returncode == 0:
                import json
                try:
                    data = json.loads(result.stdout)
                    if 'streams' in data and data['streams']:
                        stream = data['streams'][0]
                        return {
                            'codec_name': stream.get('codec_name', ''),
                            'width': stream.get('width', 0),
                            'height': stream.get('height', 0),
                            'pix_fmt': stream.get('pix_fmt', '')
                        }
                except json.JSONDecodeError:
                    pass
            return None
        except Exception:
            return None
    
    def browse_output(self):
        """选择输出文件路径"""
        try:
            # 设置对话框的初始目录
            initial_dir = os.path.expanduser("~")  # 使用用户主目录作为默认目录
            initial_file = "merged_video.mp4"
            
            if self.selected_files:
                initial_dir = os.path.dirname(self.selected_files[0])
                base_name = os.path.basename(self.selected_files[0]).split('.')[0]
                initial_file = f"{base_name}_merged.mp4"
            
            # 打开文件保存对话框
            file_path = filedialog.asksaveasfilename(
                initialdir=initial_dir,
                title="保存合并后的视频",
                defaultextension=".mp4",
                filetypes=[("MP4视频", "*.mp4"), ("所有文件", "*")]
            )
            
            if file_path:
                self.output_path_var.set(file_path)
                self._update_merge_button_state()
                
        except Exception as e:
            messagebox.showerror("错误", f"选择输出文件时发生错误: {str(e)}")
    
    def start_merge(self):
        """开始合并视频"""
        # 设置进度条为0
        self.progress_var.set(0)
        self.progress_details_var.set("开始准备合并...")
        
        # 禁用相关按钮
        self.merge_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.add_button.config(state=tk.DISABLED)
        self.remove_button.config(state=tk.DISABLED)
        self.move_up_button.config(state=tk.DISABLED)
        self.move_down_button.config(state=tk.DISABLED)
        self.browse_output_button.config(state=tk.DISABLED)
        
        # 检查基本条件
        if not self.selected_files or len(self.selected_files) < 2:
            messagebox.showerror("错误", "请至少选择两个视频文件")
            self._reset_ui()
            return
        
        output_path = self.output_path_var.get()
        if not output_path:
            messagebox.showerror("错误", "请设置输出文件路径")
            self._reset_ui()
            return
        
        if not self.ffmpeg_available:
            messagebox.showerror("错误", "未找到ffmpeg，请安装ffmpeg以使用视频合并功能")
            self._reset_ui()
            return
        
        # 检查视频兼容性
        is_compatible, message = self._check_video_compatibility()
        if not is_compatible:
            if message.startswith("无法读取"):
                messagebox.showerror("错误", message)
                self._reset_ui()
                return
            else:
                # 如果只是警告，让用户决定是否继续
                if not messagebox.askyesno("兼容性警告", message):
                    self._reset_ui()
                    return
        
        # 检查输出文件目录是否存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                self.progress_details_var.set(f"创建输出目录: {output_dir}")
            except Exception as e:
                messagebox.showerror("错误", f"无法创建输出目录: {str(e)}")
                self._reset_ui()
                return
        
        # 更新状态
        self.status_var.set("准备合并视频...")
        self.root.update()
        
        # 开始在单独线程中合并
        self.processing = True
        self.merge_thread = threading.Thread(target=self._merge_videos_thread, args=(self.selected_files, output_path))
        self.merge_thread.daemon = True  # 使线程在主程序退出时自动终止
        self.merge_thread.start()
        
        # 开始检查处理进度
        self._check_merge_progress()
    
    def _merge_videos_thread(self, input_files, output_path):
        """在单独线程中执行的视频合并逻辑"""
        temp_files = []  # 用于跟踪需要清理的临时文件
        
        try:
            # 创建临时文件列表，用于ffmpeg的concat命令
            with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as list_file:
                list_file_path = list_file.name
                temp_files.append(list_file_path)
                
                # 处理文件路径，确保ffmpeg能正确识别
                for file_path in input_files:
                    # Windows下需要特殊处理文件路径中的反斜杠
                    if platform.system() == "Windows":
                        # 将反斜杠替换为双反斜杠，ffmpeg在Windows下需要这样处理
                        escaped_path = file_path.replace('\\', '\\\\')
                    else:
                        escaped_path = file_path
                    
                    # 注意ffmpeg的文件路径需要用引号包围，特别是当路径包含空格时
                    list_file.write(f"file '{escaped_path}'\n")
            
            # 更新状态
            self.root.after(0, lambda: self.status_var.set("正在合并视频..."))
            
            # 构建ffmpeg命令
            # 使用concat协议进行视频合并
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file_path,
                "-c", "copy",  # 直接复制流，不重新编码
                "-y",  # 覆盖已存在的文件
                output_path
            ]
            
            # 执行ffmpeg命令
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1  # 行缓冲
            )
            
            # 读取输出，更新进度
            error_output = []
            for line in process.stderr:
                error_output.append(line)
                
                if not self.processing:
                    try:
                        process.terminate()
                        try:
                            process.wait(timeout=2.0)  # 等待进程终止
                        except subprocess.TimeoutExpired:
                            process.kill()  # 强制终止
                    except:
                        pass
                    break
            
            # 等待进程完成
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except:
                    pass
            
            # 检查是否取消
            if not self.processing:
                self.root.after(0, lambda: self.status_var.set("合并已取消"))
                # 如果文件已创建，删除它
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except:
                        pass
                self.root.after(0, self._reset_ui)
                return
            
            # 检查执行结果
            if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                # 检查输出文件大小是否合理
                total_input_size = sum(os.path.getsize(f) for f in input_files)
                output_size = os.path.getsize(output_path)
                
                # 如果输出文件大小明显小于输入文件总大小，发出警告
                if output_size < total_input_size * 0.8:  # 如果小于80%
                    warning_msg = f"视频合并完成，但输出文件大小({self._format_size(output_size)})明显小于输入文件总大小({self._format_size(total_input_size)})。可能存在问题。"
                    self.root.after(0, lambda: self.status_var.set(warning_msg))
                    self.root.after(0, lambda: messagebox.showwarning("警告", f"视频合并完成！\n\n输出文件: {output_path}\n\n{warning_msg}"))
                else:
                    self.root.after(0, lambda: self.status_var.set(f"视频合并成功: {output_path}"))
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"视频合并成功！\n\n输出文件: {output_path}"))
            else:
                # 构建详细的错误信息
                error_msg = f"视频合并失败，错误代码: {process.returncode}\n\n"
                if len(error_output) > 10:
                    # 只显示最后10行错误信息
                    error_msg += "错误详情: " + ''.join(error_output[-10:])
                else:
                    error_msg += "错误详情: " + ''.join(error_output)
                
                self.root.after(0, lambda msg=error_msg: self.status_var.set(f"合并失败: {str(process.returncode)}"))
                self.root.after(0, lambda msg=error_msg: messagebox.showerror("错误", msg))
                
                # 清理可能的不完整文件
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except:
                        pass
            
        except PermissionError as e:
            error_msg = f"权限错误: 无法访问文件或创建临时文件。请检查权限。\n{str(e)}"
            self.root.after(0, lambda: self.status_var.set("合并失败: 权限错误"))
            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        except FileNotFoundError as e:
            error_msg = f"文件未找到: {str(e)}"
            self.root.after(0, lambda: self.status_var.set("合并失败: 文件未找到"))
            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        except Exception as e:
            error_msg = f"合并过程中发生错误: {str(e)}"
            self.root.after(0, lambda: self.status_var.set("合并失败: 未知错误"))
            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        finally:
            # 清理临时文件
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except:
                    pass
            
            # 重置UI
            self.root.after(0, self._reset_ui)
    
    def _format_size(self, size_bytes):
        """格式化文件大小显示"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
        
    def _format_duration(self, seconds):
        """将秒数转换为时分秒格式"""
        if isinstance(seconds, str):
            return seconds
            
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
        
    def _update_merge_button_state(self):
        """更新合并按钮状态"""
        if len(self.selected_files) > 1 and self.output_path_var.get() and self.ffmpeg_available and not self.processing:
            self.merge_button.config(state=tk.NORMAL)
        else:
            self.merge_button.config(state=tk.DISABLED)
    
    def _check_merge_progress(self):
        """检查合并进度并更新UI"""
        if self.processing and self.merge_thread.is_alive():
            # 获取当前正在处理的输出文件路径
            output_path = self.output_path_var.get()
            if os.path.exists(output_path):
                try:
                    # 计算源文件总大小，用于估算进度
                    total_source_size = sum(os.path.getsize(file_path) for file_path in self.selected_files if os.path.exists(file_path))
                    current_size = os.path.getsize(output_path)
                    
                    # 计算进度百分比
                    if total_source_size > 0:
                        # 使用源文件总大小作为参考计算进度
                        progress_percentage = min(99, (current_size / total_source_size) * 100)
                        self.progress_var.set(progress_percentage)
                        
                        # 更新进度详情
                        size_info = f"当前大小: {self._format_size(current_size)} / 预计: {self._format_size(total_source_size)}"
                        percentage_info = f"进度: {progress_percentage:.1f}%"
                        self.progress_details_var.set(f"{size_info} | {percentage_info}")
                except Exception:
                    # 如果获取文件大小失败，回退到假进度
                    current_progress = self.progress_var.get()
                    if current_progress < 90:  # 不设置到100%，留一些空间给最终处理
                        self.progress_var.set(current_progress + 0.5)
                        self.progress_details_var.set(f"正在合并视频... (进度: {min(90, current_progress + 0.5):.1f}%)")
            else:
                # 文件尚未创建，使用假进度
                current_progress = self.progress_var.get()
                if current_progress < 10:  # 初始阶段进度慢一点
                    self.progress_var.set(current_progress + 0.1)
                    self.progress_details_var.set(f"正在准备合并... (进度: {current_progress + 0.1:.1f}%)")
            
            # 继续检查
            self.root.after(500, self._check_merge_progress)
        elif self.processing:
            # 处理完成，设置进度为100%
            self.progress_var.set(100)
            self.progress_details_var.set("合并完成！")
    
    def cancel_merge(self):
        """取消合并操作"""
        self.processing = False
        self.status_var.set("正在取消合并...")
    
    def _reset_ui(self):
        """重置UI状态"""
        self.processing = False
        self.merge_thread = None
        self.merge_button.config(state=tk.NORMAL if (len(self.selected_files) > 1 and self.output_path_var.get() and self.ffmpeg_available) else tk.DISABLED)
        self.cancel_button.config(state=tk.DISABLED)
        self.add_button.config(state=tk.NORMAL)
        self._on_file_select()  # 更新其他按钮状态
        self.browse_output_button.config(state=tk.NORMAL)
        self.progress_var.set(0)
        self.progress_details_var.set("准备就绪")
        
        # 更新状态信息
        if self.selected_files:
            self.status_var.set(f"已加载 {len(self.selected_files)} 个视频文件")
        else:
            self.status_var.set("准备就绪，请添加视频文件")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoMerger(root)
    root.mainloop()