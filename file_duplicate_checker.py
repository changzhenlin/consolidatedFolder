import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from collections import Counter
import threading
import platform

class FileDuplicateChecker:
    # 应用程序信息
    APP_VERSION = "1.0.0"
    
    def __init__(self, root):
        self.root = root
        self.root.title(f"文件重复检查工具 v{self.APP_VERSION}")
        self.root.geometry("700x500")
        self.root.resizable(True, True)
        
        # 尝试设置窗口图标
        self._set_window_icon()
        
        # 设置中文字体支持
        self._setup_fonts()
        
        # 扫描控制变量
        self.scanning = False
        self.scan_thread = None
        
        # 确保应用程序正确退出
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # 创建主框架
        self.main_frame = ttk.Frame(root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建文件夹选择区域
        self.folder_frame = ttk.Frame(self.main_frame)
        self.folder_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.folder_label = ttk.Label(self.folder_frame, text="选择文件夹:", font=('SimHei', 10))
        self.folder_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.folder_path_var = tk.StringVar()
        self.folder_entry = ttk.Entry(self.folder_frame, textvariable=self.folder_path_var, width=50, font=('SimHei', 10))
        self.folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.browse_button = ttk.Button(self.folder_frame, text="浏览...", command=self.browse_folder)
        self.browse_button.pack(side=tk.RIGHT)
        
        # 创建扫描控制区域
        self.scan_control_frame = ttk.Frame(self.main_frame)
        self.scan_control_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 创建扫描按钮
        self.scan_button = ttk.Button(self.scan_control_frame, text="开始扫描", command=self.scan_files)
        self.scan_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 创建取消按钮
        self.cancel_button = ttk.Button(self.scan_control_frame, text="取消扫描", command=self.cancel_scan, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT)
        
        # 创建进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.scan_control_frame, variable=self.progress_var, length=300, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        
        # 添加键盘快捷键
        self.root.bind("<Return>", lambda event: self.scan_files())
        self.root.bind("<KP_Enter>", lambda event: self.scan_files())  # 小键盘的Enter键
        
        # 设置浏览按钮的快捷键
        self.browse_button.bind("<Return>", lambda event: self.browse_folder())
        self.browse_button.bind("<KP_Enter>", lambda event: self.browse_folder())
        
        # 创建结果显示区域
        self.result_frame = ttk.LabelFrame(self.main_frame, text="扫描结果")
        self.result_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # 创建结果树状视图
        columns = ("filename", "count", "locations")
        self.result_tree = ttk.Treeview(self.result_frame, columns=columns, show="headings")
        
        # 设置列宽和标题
        self.result_tree.heading("filename", text="文件名")
        self.result_tree.heading("count", text="重复次数")
        self.result_tree.heading("locations", text="位置")
        
        self.result_tree.column("filename", width=150, anchor=tk.W)
        self.result_tree.column("count", width=80, anchor=tk.CENTER)
        self.result_tree.column("locations", width=350, anchor=tk.W)
        
        # 添加垂直滚动条
        vscrollbar = ttk.Scrollbar(self.result_frame, orient=tk.VERTICAL, command=self.result_tree.yview)
        self.result_tree.configure(yscroll=vscrollbar.set)
        
        # 添加水平滚动条
        hscrollbar = ttk.Scrollbar(self.result_frame, orient=tk.HORIZONTAL, command=self.result_tree.xview)
        self.result_tree.configure(xscroll=hscrollbar.set)
        
        # 放置树状视图和滚动条
        self.result_tree.grid(row=0, column=0, sticky=tk.NSEW)
        vscrollbar.grid(row=0, column=1, sticky=tk.NS)
        hscrollbar.grid(row=1, column=0, sticky=tk.EW)
        
        # 配置网格权重，使树状视图能够随窗口大小调整
        self.result_frame.grid_rowconfigure(0, weight=1)
        self.result_frame.grid_columnconfigure(0, weight=1)
        
        # 添加双击事件绑定，用于显示详细信息
        self.result_tree.bind("\u003cDouble-1\u003e", self.show_file_details)
        
        # 添加右键菜单支持
        self.result_tree.bind("\u003cButton-3\u003e", self.show_context_menu)
        self._create_context_menu()
        
        # 添加排序功能
        self.sort_column = None
        self.sort_order = "ascending"
        for col in ("filename", "count", "locations"):
            self.result_tree.heading(col, text=self.result_tree.heading(col)["text"], 
                                    command=lambda _col=col: self.sort_by_column(_col))
        
        # 创建底部状态栏
        self.status_frame = ttk.Frame(self.main_frame)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))
        
        # 创建统计信息标签
        self.stats_var = tk.StringVar(value="准备就绪，请选择文件夹并点击扫描按钮")
        self.stats_label = ttk.Label(self.status_frame, textvariable=self.stats_var, font=('SimHei', 10))
        self.stats_label.pack(side=tk.LEFT, padx=(5, 10))
        
        # 创建版本信息标签
        self.version_label = ttk.Label(self.status_frame, text=f"v{self.APP_VERSION}", font=('SimHei', 8))
        self.version_label.pack(side=tk.RIGHT, padx=5)
        
        # 存储完整的文件路径信息，用于右键菜单和详细信息显示
        self.full_file_info = {}
        
        # 欢迎信息
        self._show_welcome_message()
    
    def _setup_fonts(self):
        """设置中文字体支持"""
        self.style = ttk.Style()
        
        # 根据操作系统调整字体设置
        system = platform.system()
        if system == "Windows":
            # Windows 系统通常支持 SimHei 或 Microsoft YaHei
            default_font = ('Microsoft YaHei UI', 9)
        elif system == "Darwin":  # macOS
            default_font = ('Heiti TC', 9)
        else:  # Linux 或其他系统
            default_font = ('WenQuanYi Micro Hei', 9)
        
        # 设置默认字体样式
        self.style.configure('.', font=default_font)
        
    def _set_window_icon(self):
        """尝试设置窗口图标"""
        # 在实际使用中，可以添加自定义图标
        # 这里只是一个示例，实际使用时需要提供图标文件路径
        try:
            # 这里可以添加图标设置代码，例如：
            # icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
            # if os.path.exists(icon_path):
            #     self.root.iconbitmap(icon_path)
            pass
        except Exception:
            # 如果图标设置失败，静默忽略
            pass
    
    def _show_welcome_message(self):
        """显示欢迎信息"""
        # 可以在这里添加欢迎信息或使用提示
        pass
    
    def _on_closing(self):
        """处理窗口关闭事件"""
        if self.scanning:
            if messagebox.askyesno("确认退出", "扫描正在进行中，确定要退出吗？"):
                self.scanning = False
                # 等待扫描线程结束
                if self.scan_thread and self.scan_thread.is_alive():
                    self.scan_thread.join(timeout=1.0)  # 等待最多1秒
                self.root.destroy()
        else:
            self.root.destroy()
    
    def browse_folder(self):
        """打开文件夹选择对话框"""
        try:
            # 设置对话框的初始目录为当前选择的目录
            initial_dir = self.folder_path_var.get()
            if not initial_dir or not os.path.isdir(initial_dir):
                initial_dir = os.path.expanduser("~")  # 使用用户主目录作为默认目录
                
            folder_path = filedialog.askdirectory(
                initialdir=initial_dir,
                title="选择要扫描的文件夹",
                mustexist=True  # 确保选择的是已存在的文件夹
            )
            
            if folder_path:
                self.folder_path_var.set(folder_path)
                # 自动聚焦到扫描按钮，方便用户按Enter键开始扫描
                self.scan_button.focus_set()
        except Exception as e:
            messagebox.showerror("错误", f"选择文件夹时发生错误: {str(e)}")
    
    def scan_files(self):
        """开始扫描过程，在单独的线程中执行以避免UI冻结"""
        folder_path = self.folder_path_var.get()
        
        if not folder_path or not os.path.isdir(folder_path):
            messagebox.showerror("错误", "请选择有效的文件夹路径")
            return
        
        # 防止重复点击
        self.scan_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.progress_var.set(0)
        
        # 清空结果树
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        
        # 更新状态
        self.stats_var.set("正在计算文件总数...")
        self.root.update()
        
        # 开始在单独线程中扫描
        self.scanning = True
        self.scan_thread = threading.Thread(target=self._scan_files_thread, args=(folder_path,))
        self.scan_thread.daemon = True  # 使线程在主程序退出时自动终止
        self.scan_thread.start()
        
        # 开始检查扫描进度
        self._check_scan_progress()
    
    def _count_total_files(self, folder_path):
        """计算文件夹中的文件总数"""
        total = 0
        try:
            for _, _, files in os.walk(folder_path):
                total += len(files)
                # 允许在计数过程中取消
                if not self.scanning:
                    return -1
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("错误", f"计算文件数量时出错: {str(e)}"))
            return -1
        return total
    
    def _scan_files_thread(self, folder_path):
        """在单独线程中执行的扫描逻辑"""
        try:
            # 先计算文件总数，用于进度显示
            total_files = self._count_total_files(folder_path)
            if total_files == -1 or not self.scanning:
                self.root.after(0, self._reset_scan_ui)
                return
            
            # 存储文件名和对应的路径
            file_dict = {}
            processed_files = 0
            
            # 递归扫描文件夹
            for root_dir, _, files in os.walk(folder_path):
                for filename in files:
                    # 检查是否取消扫描
                    if not self.scanning:
                        self.root.after(0, self._reset_scan_ui)
                        return
                    
                    # 处理文件
                    if filename in file_dict:
                        file_dict[filename].append(root_dir)
                    else:
                        file_dict[filename] = [root_dir]
                    
                    # 更新进度
                    processed_files += 1
                    progress = (processed_files / total_files) * 100
                    self.root.after(0, lambda p=progress: self.progress_var.set(p))
                    
                    # 每处理100个文件更新一次状态，避免UI过于频繁刷新
                    if processed_files % 100 == 0:
                        self.root.after(0, lambda pf=processed_files, tf=total_files: 
                                       self.stats_var.set(f"正在扫描文件... {pf}/{tf} ({int(pf/tf*100)}%)"))
            
            if not self.scanning:
                self.root.after(0, self._reset_scan_ui)
                return
            
            # 找出重复的文件名
            duplicate_files = {name: paths for name, paths in file_dict.items() if len(paths) > 1}
            
            # 按重复次数排序
            sorted_duplicates = sorted(duplicate_files.items(), key=lambda x: len(x[1]), reverse=True)
            
            # 在主线程中更新UI显示结果
            self.root.after(0, lambda duplicates=sorted_duplicates, total=total_files: 
                           self._display_results(duplicates, total))
            
        except PermissionError:
            self.root.after(0, lambda: messagebox.showerror("权限错误", "无法访问某些文件或文件夹，请检查权限后重试。"))
            self.root.after(0, lambda: self.stats_var.set("扫描失败：权限不足"))
            self.root.after(0, self._reset_scan_ui)
        except Exception as e:
            self.root.after(0, lambda err=str(e): messagebox.showerror("错误", f"扫描过程中发生错误: {err}"))
            self.root.after(0, lambda: self.stats_var.set("扫描失败，请重试"))
            self.root.after(0, self._reset_scan_ui)
    
    def _display_results(self, sorted_duplicates, total_files):
        """在主线程中显示扫描结果"""
        # 清空之前的文件信息
        self.full_file_info.clear()
        
        # 在结果树中显示重复文件
        for filename, paths in sorted_duplicates:
            # 限制显示的路径数量，避免UI过于拥挤
            display_paths = paths[:3]
            path_text = "; ".join(display_paths)
            if len(paths) > 3:
                path_text += f"; ...等{len(paths) - 3}个位置"
            
            # 插入结果并保存完整信息
            item_id = self.result_tree.insert("", tk.END, values=(filename, len(paths), path_text))
            self.full_file_info[item_id] = (filename, paths)
        
        # 更新统计信息
        self.stats_var.set(f"扫描完成。总共扫描了 {total_files} 个文件，发现 {len(sorted_duplicates)} 个重复的文件名。")
        
        # 重置UI状态
        self._reset_scan_ui()
    
    def _create_context_menu(self):
        """创建右键菜单"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="复制文件名", command=self.copy_filename)
        self.context_menu.add_command(label="查看所有位置", command=self.show_file_details)
        self.context_menu.add_command(label="复制所有位置", command=self.copy_all_locations)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="清空结果", command=self.clear_results)
    
    def show_context_menu(self, event):
        """显示右键菜单"""
        # 选中点击的项目
        item = self.result_tree.identify_row(event.y)
        if item:
            self.result_tree.selection_set(item)
            self.result_tree.focus(item)
            # 显示菜单
            self.context_menu.post(event.x_root, event.y_root)
    
    def show_file_details(self, event=None):
        """显示文件的详细信息，包括所有位置"""
        selected_items = self.result_tree.selection()
        if not selected_items:
            return
        
        item_id = selected_items[0]
        if item_id not in self.full_file_info:
            return
        
        filename, all_paths = self.full_file_info[item_id]
        
        # 创建新窗口显示详细信息
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"文件详情: {filename}")
        detail_window.geometry("600x400")
        detail_window.resizable(True, True)
        
        # 创建标签显示文件名
        ttk.Label(detail_window, text=f"文件名: {filename}", font=('SimHei', 10, 'bold')).pack(pady=(10, 5), padx=10, anchor=tk.W)
        ttk.Label(detail_window, text=f"出现次数: {len(all_paths)}", font=('SimHei', 10)).pack(pady=(0, 10), padx=10, anchor=tk.W)
        
        # 创建带滚动条的文本框显示所有路径
        text_frame = ttk.Frame(detail_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD, font=('SimHei', 9))
        
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 插入所有路径
        for i, path in enumerate(all_paths, 1):
            full_path = os.path.join(path, filename)
            text_widget.insert(tk.END, f"{i}. {full_path}\n")
        
        # 使文本框只读
        text_widget.config(state=tk.DISABLED)
    
    def copy_filename(self):
        """复制选中文件的文件名到剪贴板"""
        selected_items = self.result_tree.selection()
        if not selected_items:
            return
        
        item_id = selected_items[0]
        if item_id not in self.full_file_info:
            return
        
        filename, _ = self.full_file_info[item_id]
        self.root.clipboard_clear()
        self.root.clipboard_append(filename)
        self.stats_var.set(f"已复制文件名: {filename}")
    
    def copy_all_locations(self):
        """复制选中文件的所有位置到剪贴板"""
        selected_items = self.result_tree.selection()
        if not selected_items:
            return
        
        item_id = selected_items[0]
        if item_id not in self.full_file_info:
            return
        
        filename, all_paths = self.full_file_info[item_id]
        
        # 构建完整的文件路径
        full_paths = [os.path.join(path, filename) for path in all_paths]
        paths_text = "\n".join(full_paths)
        
        self.root.clipboard_clear()
        self.root.clipboard_append(paths_text)
        self.stats_var.set(f"已复制 {len(all_paths)} 个文件位置到剪贴板")
    
    def clear_results(self):
        """清空结果列表"""
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        self.full_file_info.clear()
        self.stats_var.set("结果已清空")
    
    def sort_by_column(self, col):
        """按指定列排序结果"""
        # 切换排序顺序
        if self.sort_column == col:
            self.sort_order = "descending" if self.sort_order == "ascending" else "ascending"
        else:
            self.sort_column = col
            self.sort_order = "ascending"
        
        # 获取所有项目
        items = [(self.result_tree.set(k, col), k) for k in self.result_tree.get_children('')]
        
        # 根据列类型进行排序
        if col == "count":  # 数字列
            items.sort(key=lambda t: int(t[0]), reverse=(self.sort_order == "descending"))
        else:  # 文本列
            items.sort(key=lambda t: t[0].lower(), reverse=(self.sort_order == "descending"))
        
        # 重新排列项目
        for i, (val, k) in enumerate(items):
            self.result_tree.move(k, '', i)
        
        # 更新标题，显示排序指示
        for c in ("filename", "count", "locations"):
            if c == col:
                arrow = "↓" if self.sort_order == "descending" else "↑"
                self.result_tree.heading(c, text=f"{self.result_tree.heading(c)['text']} {arrow}")
            else:
                # 移除其他列的排序指示
                original_text = self.result_tree.heading(c)["text"].strip()
                if original_text.endswith(" ↑") or original_text.endswith(" ↓"):
                    self.result_tree.heading(c, text=original_text[:-2])
    
    def _check_scan_progress(self):
        """检查扫描进度并更新UI"""
        if self.scanning and self.scan_thread.is_alive():
            self.root.after(100, self._check_scan_progress)  # 每100ms检查一次
    
    def cancel_scan(self):
        """取消正在进行的扫描"""
        self.scanning = False
        self.stats_var.set("正在取消扫描...")
        
    def _reset_scan_ui(self):
        """重置扫描相关的UI组件状态"""
        self.scanning = False
        self.scan_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        self.progress_var.set(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = FileDuplicateChecker(root)
    root.mainloop()