"""
可折叠的 LabelFrame 组件
"""

import tkinter as tk


class CollapsibleFrame(tk.Frame):
    """可折叠的框架组件"""

    def __init__(self, parent, title="", bg="#1a1a2e", fg="#eee", **kwargs):
        super().__init__(parent, bg=bg, **kwargs)

        self.bg = bg
        self.fg = fg
        self.is_collapsed = False

        # 标题栏（可点击）
        self.title_frame = tk.Frame(self, bg=bg, cursor="hand2")
        self.title_frame.pack(fill=tk.X, pady=(0, 5))

        # 折叠指示器
        self.indicator = tk.Label(
            self.title_frame,
            text="▼",
            bg=bg,
            fg=fg,
            font=("JetBrains Mono", 10),
            cursor="hand2"
        )
        self.indicator.pack(side=tk.LEFT, padx=(0, 5))

        # 标题文本
        self.title_label = tk.Label(
            self.title_frame,
            text=title,
            bg=bg,
            fg=fg,
            font=("JetBrains Mono", 11, "bold"),
            cursor="hand2"
        )
        self.title_label.pack(side=tk.LEFT)

        # 内容框架
        self.content_frame = tk.Frame(self, bg=bg)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        # 绑定点击事件
        self.title_frame.bind("<Button-1>", lambda e: self.toggle())
        self.indicator.bind("<Button-1>", lambda e: self.toggle())
        self.title_label.bind("<Button-1>", lambda e: self.toggle())

    def toggle(self):
        """切换折叠状态"""
        if self.is_collapsed:
            self.expand()
        else:
            self.collapse()

    def collapse(self):
        """折叠"""
        self.is_collapsed = True
        self.indicator.config(text="▶")
        self.content_frame.pack_forget()

    def expand(self):
        """展开"""
        self.is_collapsed = False
        self.indicator.config(text="▼")
        self.content_frame.pack(fill=tk.BOTH, expand=True)

    def get_content_frame(self):
        """获取内容框架，用于添加子组件"""
        return self.content_frame
