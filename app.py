#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import datetime
import subprocess
import configparser
import traceback
import logging
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText, ScrolledFrame
from ttkbootstrap.dialogs.dialogs import Messagebox

logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_config(config_path, encoding='utf-8'):
    try:
        if not os.path.exists(config_path):
            logging.error(f"配置文件不存在: {config_path}")
            messagebox.showerror("错误", f"配置文件不存在: {config_path}")
            return None
            
        config = configparser.ConfigParser()
        config.read(filenames=config_path, encoding=encoding)
        return config
    except Exception as e:
        logging.error(f"加载配置文件失败: {config_path}, 错误: {str(e)}")
        messagebox.showerror("错误", f"加载配置文件失败: {str(e)}")
        return None

def get_root_path():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_path = os.path.dirname(current_dir)
        return current_dir, root_path
    except Exception as e:
        logging.error(f"获取根目录路径失败: {str(e)}")
        messagebox.showerror("错误", f"获取根目录路径失败: {str(e)}")
        return None, None

now = datetime.datetime.now()
time = now.strftime('%H:%M:%S')
current_time = now.strftime('%Y-%m-%d %H:%M:%S %A')

print(f" [+] {time} 调试信息: 格式化时间{current_time}")

directory, rootPath = get_root_path()
if directory is None or rootPath is None:
    sys.exit(1)

output_path = os.path.join(directory, 'Output')
style_config_path = os.path.join(directory, "config", "config.ini")
command_config_path = os.path.join(directory, "config", "command.ini")

config_style = load_config(style_config_path)
if config_style is None:
    sys.exit(1)

conf = load_config(command_config_path)
if conf is None:
    sys.exit(1)

try:
    toolFunlist = config_style.get("tool", "funList")
    toolFunlist = json.loads(toolFunlist)
except Exception as e:
    logging.error(f"解析工具列表失败: {str(e)}")
    messagebox.showerror("错误", f"解析工具列表失败: {str(e)}")
    sys.exit(1)

print("""

  █████████                                              █████     ███    ██   ██████
 ███░░░░░███                                          ███░░░░░███░░███  ░░███ ░░███ 
░███    ░░░  █████ ████ ████████   ██████  ████████  ███     ░░░  ░███   ░███  ░███ 
░░█████████ ░░███ ░███ ░░███░░███ ███░░███░░███░░███░███          ░███   ░███  ░███ 
 ░░░░░░░░███ ░███ ░███  ░███ ░███░███████  ░███ ░░░ ░███    █████ ░███   ░███  ░███ 
 ███    ░███ ░███ ░███  ░███ ░███░███░░░   ░███     ░░███  ░░███  ░███   ░███  ░███ 
░░█████████  ░░████████ ░███████ ░░██████  █████     ░░█████████  ░░████████   █████   V 2.0.1
 ░░░░░░░░░    ░░░░░░░░  ░███░░░   ░░░░░░  ░░░░░       ░░░░░░░░░    ░░░░░░░░   ░░░░░    BY:Super403
                        ░███                                                        
                        █████                                                       
                       ░░░░░ 
""")

root = ttk.Window(title = config_style["app"]["title"] + " —— " + current_time, themename = str(config_style["app"]["theme"]))
root.iconbitmap('./config/favicon.ico')

screenheight = root.winfo_screenheight()
screenwidth = root.winfo_screenwidth()

size_w = config_style["app"]["size_w"]
size_h = config_style["app"]["size_h"]

center_w = int((screenwidth - int(size_w)) / 2)
center_h = int((screenheight - int(size_h)) / 2)
root.geometry(f'{size_w}x{size_h}+{center_w}+{center_h}')

app_size_w = int(config_style["app"]["size_w"])
app_size_h = int(config_style["app"]["size_h"])
average = int(config_style["app"]["average"])
tool_aver = int(config_style["app"]["tool_aver"])
note_aver = int(config_style["app"]["note_aver"])

print(f" [+] {time} 调试信息: 电脑屏幕的尺寸分别是，宽{screenwidth} + 高{screenheight}")
print(f" [+] {time} 调试信息: 位置参数信息：宽{size_w} ,高{size_h},左边距{center_w},上边距{center_h},")
print(f" [+] {time} 调试信息: 工具框架的宽是:{int(app_size_w/average*tool_aver)}")
print(f" [+] {time} 调试信息: 笔记框架的宽是:{int(app_size_w/average*note_aver)}")

class APP(ttk.Frame):

    def update_time(self):
        now = datetime.datetime.now()
        current_time = now.strftime('%Y-%m-%d %H:%M:%S %A')
        self.master.title(config_style["app"]["title"] + " —— " + current_time)
        self.master.after(1000, self.update_time)

    def gui_tools(self):
        try:
            python = sys.executable
            logging.info("正在重启应用程序...")
            os.execl(python, python, *sys.argv)
        except Exception as e:
            logging.error(f"重启应用程序失败: {str(e)}")
            messagebox.showerror("错误", f"重启应用程序失败: {str(e)}")

    def open_output_folder(self):
        os.makedirs(output_path, exist_ok=True)
        os.startfile(output_path)

    def show_Project(self):
        messagebox.showinfo(title= "项目地址", message="http://github.com/super403/SuperGUI")

    def show_about(self):
        messagebox.showinfo(title="关于", message="作者: super403  当前版本: 2.0.1")

    def show_GJX(self):
        os.system(f"start {rootPath}")

    def show_process_image(self):
        top = tk.Toplevel()
        top.title("标准渗透规范")
        try:
            img = Image.open('./config/web.png')
            desired_width = 800
            width, height = img.size
            ratio = height / width
            desired_height = int(desired_width * ratio)

            img = img.resize((desired_width, desired_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            scroll_frame = ttk.Frame(top)
            scroll_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)

            canvas = tk.Canvas(scroll_frame, bd=0, highlightthickness=0)
            scrollbar_y = ttk.Scrollbar(scroll_frame, orient=VERTICAL, command=canvas.yview)
            scrollbar_x = ttk.Scrollbar(scroll_frame, orient=HORIZONTAL, command=canvas.xview)

            canvas.configure(xscrollcommand=scrollbar_x.set, yscrollcommand=scrollbar_y.set)
            
            scrollbar_y.pack(side=RIGHT, fill=Y)
            scrollbar_x.pack(side=BOTTOM, fill=X)
            canvas.pack(side=LEFT, fill=BOTH, expand=True)

            inner_frame = ttk.Frame(canvas)
            canvas.create_window((0, 0), window=inner_frame, anchor=NW)

            label = ttk.Label(inner_frame, image=photo)
            label.image = photo
            label.pack(padx=5, pady=5)

            inner_frame.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))

            window_width = desired_width + 40
            window_height = min(desired_height + 80, 900)
            
            screen_width = top.winfo_screenwidth()
            screen_height = top.winfo_screenheight()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            top.geometry(f"{window_width}x{window_height}+{x}+{y}")

            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

            close_button = ttk.Button(top, text="关闭", command=top.destroy)
            close_button.pack(pady=5)
            
        except Exception as e:
            messagebox.showerror("错误", f"无法加载图片：{str(e)}")
            top.destroy()

    def open_domain(self):
        self.open_target_file('domain.txt')
        
    def open_subdomain(self):
        self.open_target_file('subdomain.txt')
        
    def open_ip(self):
        self.open_target_file('ip.txt')
        
    def open_url_file(self):
        self.open_target_file('url.txt')

    def open_target_file(self, file_name):
        try:
            top = tk.Toplevel()
            top.title(f"目标配置 - {file_name}")
            
            window_width = 800
            window_height = 600
            screen_width = top.winfo_screenwidth()
            screen_height = top.winfo_screenheight()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            top.geometry(f"{window_width}x{window_height}+{x}+{y}")

            button_frame = ttk.Frame(top)
            button_frame.pack(fill=X, padx=10, pady=5)
            
            text_widget = ScrolledText(top, width=90, height=30)
            text_widget.pack(padx=10, pady=5, fill=BOTH, expand=True)
            
            file_path = os.path.join('target', file_name)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                text_widget.insert('1.0', content)
            else:
                text_widget.insert('1.0', f'文件 {file_name} 不存在，将在保存时创建。')
        
            def save_content():
                content = text_widget.get('1.0', tk.END)
                os.makedirs('target', exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("成功", f"{file_name} 保存成功！")

            def remove_duplicates():
                content = text_widget.get('1.0', tk.END).strip().split('\n')
                unique_lines = list(set(line.strip() for line in content if line.strip()))
                text_widget.delete('1.0', tk.END)
                text_widget.insert('1.0', '\n'.join(unique_lines))
                save_content()
                messagebox.showinfo("成功", "已完成去重并保存！")

            def sort_content():
                content = text_widget.get('1.0', tk.END).strip().split('\n')
                sorted_lines = sorted(line.strip() for line in content if line.strip())
                text_widget.delete('1.0', tk.END)
                text_widget.insert('1.0', '\n'.join(sorted_lines))
                save_content()
                messagebox.showinfo("成功", "已完成排序并保存！")

            def open_folder():
                folder_path = os.path.abspath('target')
                os.makedirs(folder_path, exist_ok=True)
                os.startfile(folder_path)

            save_button = ttk.Button(
                button_frame,
                text="💾 保存",
                command=save_content,
                bootstyle="success-outline"
            )
            save_button.pack(side=LEFT, padx=5)
            
            remove_dup_button = ttk.Button(
                button_frame,
                text="🔄 去重",
                command=remove_duplicates,
                bootstyle="info-outline"
            )
            remove_dup_button.pack(side=LEFT, padx=5)
            
            sort_button = ttk.Button(
                button_frame,
                text="📊 排序",
                command=sort_content,
                bootstyle="warning-outline"
            )
            sort_button.pack(side=LEFT, padx=5)
            
            folder_button = ttk.Button(
                button_frame,
                text="📂 打开目录",
                command=open_folder,
                bootstyle="primary-outline"
            )
            folder_button.pack(side=LEFT, padx=5)

        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件：{str(e)}")

    def open_weapon_config(self):
        try:
            if os.path.exists(command_config_path):
                top = tk.Toplevel()
                top.title("武器化设置")
                
                window_width = 800
                window_height = 600
                screen_width = top.winfo_screenwidth()
                screen_height = top.winfo_screenheight()
                x = (screen_width - window_width) // 2
                y = (screen_height - window_height) // 2
                top.geometry(f"{window_width}x{window_height}+{x}+{y}")
                
                button_frame = ttk.Frame(top)
                button_frame.pack(fill=X, padx=10, pady=5)
                
                text_widget = ScrolledText(top, width=90, height=30)
                text_widget.pack(padx=10, pady=5, fill=BOTH, expand=True)
                
                with open(command_config_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                text_widget.insert('1.0', content)
                
                def save_content():
                    content = text_widget.get('1.0', tk.END)
                    with open(command_config_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    messagebox.showinfo("成功", "武器化配置保存成功！")
                
                save_button = ttk.Button(
                    button_frame,
                    text="💾 保存",
                    command=save_content,
                    bootstyle="success-outline"
                )
                save_button.pack(side=LEFT, padx=5)
                
            else:
                messagebox.showerror("错误", "武器化配置文件不存在！")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开武器化配置文件：{str(e)}")

    def open_theme_config(self):
        try:
            if os.path.exists(style_config_path):
                top = tk.Toplevel()
                top.title("主题配置")
                
                window_width = 800
                window_height = 600
                screen_width = top.winfo_screenwidth()
                screen_height = top.winfo_screenheight()
                x = (screen_width - window_width) // 2
                y = (screen_height - window_height) // 2
                top.geometry(f"{window_width}x{window_height}+{x}+{y}")
                
                button_frame = ttk.Frame(top)
                button_frame.pack(fill=X, padx=10, pady=5)
                
                text_widget = ScrolledText(top, width=90, height=30)
                text_widget.pack(padx=10, pady=5, fill=BOTH, expand=True)
                
                with open(style_config_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                text_widget.insert('1.0', content)
                
                def save_content():
                    content = text_widget.get('1.0', tk.END)
                    with open(style_config_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    messagebox.showinfo("成功", "主题配置保存成功！\n重启程序后生效")
                
                save_button = ttk.Button(
                    button_frame,
                    text="💾 保存",
                    command=save_content,
                    bootstyle="success-outline"
                )
                save_button.pack(side=LEFT, padx=5)
                
                restart_button = ttk.Button(
                    button_frame,
                    text="🔄 重启应用",
                    command=self.gui_tools,
                    bootstyle="warning-outline"
                )
                restart_button.pack(side=LEFT, padx=5)
            
            else:
                messagebox.showerror("错误", "主题配置文件不存在！")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开主题配置文件：{str(e)}")

    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.update_time()
        self.toolsDic = self.toolsDir()
        self.main()

    def main(self):
        self.menu_bar = tk.Menu(root)
        root.config(menu=self.menu_bar)

        self.target_menu = tk.Menu(self.menu_bar)
        self.target_menu.add_command(label="域名", command=self.open_domain)
        self.target_menu.add_command(label="子域名", command=self.open_subdomain)
        self.target_menu.add_command(label="IP", command=self.open_ip)
        self.target_menu.add_command(label="网站", command=self.open_url_file)
        self.target_menu.add_separator()
        self.target_menu.add_command(label="工具存储路径", command=self.show_GJX)
        self.target_menu.add_command(label="武器化设置", command=self.open_weapon_config)
        self.target_menu.add_command(label="刷新GUI", command=self.gui_tools)
        self.menu_bar.add_cascade(label="目标配置", menu=self.target_menu)

        self.process_menu = tk.Menu(self.menu_bar)
        self.process_menu.add_command(label="查看流程图", command=self.show_process_image)
        self.menu_bar.add_cascade(label="渗透流程", menu=self.process_menu)

        self.output_menu = tk.Menu(self.menu_bar)
        self.output_menu.add_command(label="打开结果文件夹", command=self.open_output_folder)
        self.menu_bar.add_cascade(label="扫描结果", menu=self.output_menu)

        self.about_menu = tk.Menu(self.menu_bar)
        self.about_menu.add_command(label="作者", command=self.show_about)
        self.about_menu.add_command(label="项目地址", command=self.show_Project)
        self.about_menu.add_command(label="主题配置", command=self.open_theme_config)
        self.menu_bar.add_cascade(label="关于", menu=self.about_menu)

        self.toolFra = ttk.LabelFrame(self, text = config_style["tool"]["title"], bootstyle = config_style["tool"]["theme"], width = int(app_size_w / average * tool_aver), height = app_size_h, labelanchor = NW, padding = 7, border = 10)
        self.toolFra.pack(side = "left", fill = BOTH, ipadx = 7, ipady = 10, padx = 10, pady = 20)
        
        self.toolFrame = ScrolledFrame(self.toolFra, autohide = True, width = int(app_size_w / average * tool_aver), height = app_size_h + 500, bootstyle = config_style["tool"]["scrolled"])
        self.toolFrame.pack(fill = BOTH, anchor = NW)

        self.noteFrame = ttk.LabelFrame(self, text = config_style["note"]["title"], bootstyle = config_style["note"]["theme"], width = int(app_size_w / average * note_aver), height = app_size_h, labelanchor = NW, padding = 7, border = 10)
        self.noteFrame.pack(side = "left", ipadx = 7, ipady = 10, padx = 10, pady = 20)

        self.noteFrame_up = ttk.Frame(self.noteFrame, bootstyle = config_style["note"]["theme_up"])
        self.noteFrame_up.pack(side = "top", fill = "x", ipadx = 7, ipady = 10)

        self.noteFrameTxtSaveBtn = ttk.Button(self.noteFrame_up, text = "📝 保存笔记", bootstyle = "success-outline", cursor = "hand2")
        self.noteFrameTxtSaveBtn.pack(anchor = W, padx = 5, pady = 2, ipadx = 10, side = "left", ipady = 5)

        self.noteFrameStartBtn = ttk.Button(self.noteFrame_up, text = "📂 打开目录", bootstyle = "info-outline", cursor = "hand2")
        self.noteFrameStartBtn.pack(anchor = W, side = "left", padx = 5, pady = 2, ipadx = 10, ipady = 5)

        self.noteFrameOpenDirBtn = ttk.Button(self.noteFrame_up, text = "▶️ 启动工具", bootstyle = "primary-outline", cursor = "hand2")
        self.noteFrameOpenDirBtn.pack(anchor = W, side = "left", padx = 5, pady = 2, ipadx = 10, ipady = 5)

        self.noteFrame_down = ttk.LabelFrame(self.noteFrame, text = config_style["note"]["txt_title"], style = config_style["note"]["noteFrameDownStyle"], padding = 5)
        self.noteFrame_down.pack(fill = BOTH, padx = 3, pady = 3)

        self.txtCount = ScrolledText(self.noteFrame_down, width = int(app_size_w / average * note_aver), height = app_size_h, bootstyle = config_style["note"]["scrolledTextBootstyle"], autohide = True)
        self.txtCount.pack(fill = BOTH, side = BOTTOM, anchor = NW)
        self.toolFrameFun()

    def toolsDir(self, type_mark=toolFunlist[0][1]):
        tools_dict = {}
        tool_type_root_dir = rootPath
        
        tool_type_dir = sorted([
            i  
            for i in os.listdir(tool_type_root_dir)  
            if os.path.isdir(os.path.join(tool_type_root_dir, i))  
            and i.count(type_mark) == 1  
        ])
        
        for toolType in tool_type_dir:
            tools = sorted([
                i  
                for i in os.listdir(os.path.join(tool_type_root_dir, toolType))  
                if os.path.isdir(os.path.join(tool_type_root_dir, toolType, i)) 
            ])
            tools_dict[toolType] = tools  
            
        return tools_dict

    def toolFrameFun(self):
        for i in range(int(config_style["tool"]["toolColumn"])):
            self.Btnfr1 = ttk.Button(
                self.toolFrame, 
                text=toolFunlist[i][0],  
                width=config_style["tool"]["columnWidth"], 
                bootstyle=config_style["tool"]["funBtnBootstyle"],  
                command=lambda arg=toolFunlist[i][1]: self.toolFunBtn(arg)
            ).grid(pady=2, row=0, column=i)  

        r = 1
        for k in self.toolsDic.keys():
            self.btnToolType = ttk.Button(
                self.toolFrame,
                text=k,
                bootstyle=config_style["tool"]["typeBtnBootstyle"],
                command=lambda a=k: [self.openToolTypeNote(a), self.toolTypeTitle(a)]
            )
            self.btnToolType.grid(row=r, column=0, columnspan=int(config_style["tool"]["toolColumn"]), sticky=W)

            self.btnToolType.bind("<Double-Button-1>", lambda event, arg0=k: self.openTypeDir(arg0))

            r += 1
            c = 0

            for i in self.toolsDic[k]:
                if c == int(config_style["tool"]["toolColumn"]):
                    r += 1
                    c = 0
                self.btnTools = ttk.Button(
                    self.toolFrame,
                    bootstyle=config_style["tool"]["toolBtnBootstyle"],
                    text=i,
                    command=lambda a=k, b=i: [self.openToolNote(a, b), self.toolTitle(a, b)]
                )
                self.btnTools.grid(row=r, column=c, sticky=N+S+W, pady=2)

                self.btnTools.bind("<Double-Button-1>", lambda event, arg1=k, arg2=i: self.openToolDir(arg1, arg2))
                self.btnTools.bind("<ButtonPress-3>", lambda event, arg1=k, arg2=i: self.openToolCmd(arg1, arg2))

                c += 1
            r += 1

    def toolTypeTitle(self, typedir):
        for widget in self.noteFrame_up.winfo_children():
            widget.destroy()

        self.noteFrameTxtSaveBtn = ttk.Button(
            self.noteFrame_up,
            text="📝 保存笔记",
            bootstyle="success-outline",
            cursor="hand2",
            command=lambda a=typedir: self.saveTypeNote(a)
        )
        self.noteFrameTxtSaveBtn.pack(anchor=W, side="left", padx=5, pady=2, ipadx=10, ipady=5)

        self.noteFrameStartBtn = ttk.Button(
            self.noteFrame_up,
            text="📂 打开目录",
            bootstyle="info-outline",
            cursor="hand2",
            command=lambda arg0=typedir: self.openTypeDir(arg0)
        )
        self.noteFrameStartBtn.pack(anchor=W, side="left", padx=5, pady=2, ipadx=10, ipady=5)

    def toolTitle(self, typedir, tool):
        for widget in self.noteFrame_up.winfo_children():
            widget.destroy()

        self.noteFrameTxtSaveBtn = ttk.Button(
            self.noteFrame_up,
            text="📝 保存笔记",
            bootstyle="success-outline",
            cursor="hand2",
            command=lambda a=typedir, b=tool: self.saveToolNote(a, b)
        )
        self.noteFrameTxtSaveBtn.pack(anchor=W, side="left", padx=5, pady=2, ipadx=10, ipady=5)

        self.noteFrameStartBtn = ttk.Button(
            self.noteFrame_up,
            text="📂 打开目录",
            bootstyle="info-outline",
            cursor="hand2",
            command=lambda arg1=typedir, arg2=tool: self.openToolDir(arg1, arg2)
        )
        self.noteFrameStartBtn.pack(anchor=W, side="left", padx=5, pady=2, ipadx=10, ipady=5)

        self.noteFrameOpenDirBtn = ttk.Button(
            self.noteFrame_up,
            text="▶️ 启动工具",
            bootstyle="primary-outline",
            cursor="hand2",
            command=lambda arg1=typedir, arg2=tool: self.openToolCmd(arg1, arg2)
        )
        self.noteFrameOpenDirBtn.pack(anchor=W, side="left", padx=5, pady=2, ipadx=10, ipady=5)

    def saveTypeNote(self, typedir):
        notePath = os.path.join(rootPath, typedir, config_style["app"]["txt_mark"])
        content = self.txtCount.get(1.0, END)
        with open(notePath, "w", encoding='utf-8') as f:
            f.write(content)

    def saveToolNote(self, typedir, tool):
        notePath = os.path.join(rootPath, typedir, tool, config_style["app"]["txt_mark"])
        content = self.txtCount.get(1.0, END)
        with open(notePath, "w", encoding='utf-8') as f:
            f.write(content)

    def openToolNote(self, typedir, tool):
        notePath = os.path.join(rootPath, typedir, tool, config_style["app"]["txt_mark"])
        self.noteFrame_down["text"] = f"-- {os.path.join(rootPath, typedir, tool)} --"
        
        if os.path.exists(notePath):
            with open(notePath, encoding='utf-8') as f:
                self.txtCount.delete('1.0', END)
                self.txtCount.insert(END, f.read())
        else:
            Messagebox.ok(
                message="\n\t你还没有创建笔记，已自动创建初始化信息。\t\n",
                title='OpenNote'
            )
            infoMsg = f"-----你还没有创建笔记-----{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}-----"
            self.txtCount.delete('1.0', END)
            self.txtCount.insert(END, infoMsg)
            with open(notePath, "w", encoding='utf-8') as f:
                f.write(infoMsg)

    def openToolTypeNote(self, typedir):
        notePath = os.path.join(rootPath, typedir, config_style["app"]["txt_mark"])
        self.noteFrame_down["text"] = f"-- {os.path.join(rootPath, typedir)} --"

        if os.path.exists(notePath):
            with open(notePath, encoding='utf-8') as f:
                self.txtCount.delete('1.0', END)
                self.txtCount.insert(END, f.read())
        else:
            Messagebox.ok(
                message="\n\t你还没有创建笔记，已自动创建初始化信息。\t\n",
                title='OpenNote'
            )
            infoMsg = f"-----你还没有创建笔记-----{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}-----"
            self.txtCount.delete('1.0', END)
            self.txtCount.insert(END, infoMsg)
            with open(notePath, "w", encoding='utf-8') as f:
                f.write(infoMsg)

    def openTypeDir(self, typedir):
        os.startfile(os.path.join(rootPath, typedir))

    def openToolDir(self, typedir, tool):
        os.startfile(os.path.join(rootPath, typedir, tool))

    def openToolCmd(self, typedir, tool):
        try:
            original_dir = os.getcwd()
            tool_dir = os.path.join(rootPath, typedir, tool)
            
            if not os.path.exists(tool_dir):
                raise FileNotFoundError(f"工具目录不存在: {tool_dir}")
            
            os.chdir(tool_dir)
            logging.info(f"切换到工具目录: {tool_dir}")
            
            if tool in conf.sections():
                if "type" in conf.options(tool):
                    shell_type = conf.get(tool, "type")
                    logging.info(f"工具 {tool} 使用 {shell_type} shell")

                    if "command" in conf.options(tool):
                        command = conf.get(tool, "command")
                        logging.info(f"执行命令: {command}")
                        try:
                            subprocess.Popen(
                                f'start powershell -NoExit "{command}"',
                                shell=True,
                                creationflags=subprocess.CREATE_NEW_CONSOLE
                            )
                        except subprocess.SubprocessError as e:
                            raise RuntimeError(f"命令执行失败: {str(e)}")
                    else:
                        subprocess.Popen(
                            f'start powershell -NoExit ',
                            shell=True,
                            creationflags=subprocess.CREATE_NEW_CONSOLE
                        )
                else:
                    command = conf.get(tool, "command")
                    logging.info(f"执行命令: {command}")
                    try:
                        subprocess.Popen(
                            command,
                            shell=True,
                            creationflags=subprocess.CREATE_NEW_CONSOLE
                        )
                    except subprocess.SubprocessError as e:
                        raise RuntimeError(f"命令执行失败: {str(e)}")
            else:
                logging.info(f"使用默认CMD启动工具: {tool}")
                subprocess.Popen(
                    f'start cmd /k "title {tool}"',
                    shell=True,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
        except Exception as e:
            logging.error(f"启动工具失败: {str(e)}\n{traceback.format_exc()}")
            messagebox.showerror("错误", f"启动工具失败: {str(e)}")
        finally:
            os.chdir(original_dir)
            logging.info(f"返回原始目录: {original_dir}")

    def toolFunBtn(self, typeMark):
        self.toolsDic = self.toolsDir(typeMark)
        for widget in self.toolFrame.winfo_children():
            widget.destroy()
        self.toolFrameFun()

if __name__ == "__main__":
    try:
        logging.info("启动应用程序...")
        app = APP(master=root)
        root.mainloop()
    except Exception as e:
        logging.error(f"应用程序异常退出: {str(e)}\n{traceback.format_exc()}")
        messagebox.showerror("错误", f"应用程序异常退出: {str(e)}")
        sys.exit(1)
    finally:
        logging.info("应用程序关闭")