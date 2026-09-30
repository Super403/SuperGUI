"""右侧详情面板：图标、路径、标签、操作按钮、启动命令、Markdown 笔记、使用统计。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core import notes
from core.models import DEFAULT_SHELL, Entry


class CommandDialog(QDialog):
    """启动命令编辑对话框：命令文本 + 运行方式（cmd / powershell）。"""

    def __init__(self, command: str, shell_type: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑启动命令")
        self.setObjectName("CmdDialog")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        lay.addWidget(QLabel("命令（留空则使用默认：主程序 / 打开目录）"))
        self.cmd_edit = QLineEdit(command or "")
        self.cmd_edit.setPlaceholderText("例如：python oneforall.py --target domain.txt run")
        lay.addWidget(self.cmd_edit)

        row = QHBoxLayout()
        row.addWidget(QLabel("运行方式"))
        self.shell_combo = QComboBox()
        self.shell_combo.addItems(["cmd", "powershell"])
        self.shell_combo.setCurrentText(shell_type or DEFAULT_SHELL)
        row.addWidget(self.shell_combo, 1)
        lay.addLayout(row)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def result(self) -> tuple[str, str]:
        return self.cmd_edit.text().strip(), self.shell_combo.currentText()


class DetailPanel(QFrame):
    launchRequested = Signal(object)          # Entry
    openDirRequested = Signal(object)         # Entry
    pinToggled = Signal(object, bool)         # Entry, pinned
    commandEdited = Signal(object, str, str)  # Entry, command, shell_type
    tagsEdited = Signal(object, list)         # Entry, tags
    noteSaved = Signal(object)                # Entry

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DetailPanel")
        self.setFixedWidth(332)
        self._entry: Entry | None = None
        self._editing = False
        self._note_dirty = False     # 编辑器里有未保存改动
        self._loading_note = False   # set_entry 回填内容时抑制 textChanged

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)

        # 没选中条目时只显示这句提示
        self._empty = QLabel("点击左侧卡片\n查看详情与笔记")
        self._empty.setObjectName("DetailEmpty")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._root.addWidget(self._empty)

        self._body = QWidget()
        self._body.setVisible(False)
        body_lay = QVBoxLayout(self._body)
        body_lay.setContentsMargins(16, 14, 16, 14)
        body_lay.setSpacing(12)

        self._head = QLabel()
        self._head.setObjectName("DetailTitle")
        body_lay.addWidget(self._head)

        self._build_hero(body_lay)
        self._build_tag_row(body_lay)
        self._build_actions(body_lay)
        self._build_command_section(body_lay)
        self._build_note_section(body_lay)
        self._build_stats_section(body_lay)

        self._root.addWidget(self._body, 1)

    # ── 界面搭建 ──
    def _build_hero(self, lay: QVBoxLayout) -> None:
        """大图标 + 名称 + 完整路径。"""
        hero = QHBoxLayout()
        hero.setSpacing(13)
        self._icon = QLabel()
        self._icon.setFixedSize(52, 52)
        hero.addWidget(self._icon)

        text = QVBoxLayout()
        text.setSpacing(3)
        self._name = QLabel()
        self._name.setObjectName("DetailName")
        self._path = QLabel()
        self._path.setObjectName("DetailPath")
        self._path.setWordWrap(True)
        text.addWidget(self._name)
        text.addWidget(self._path)
        hero.addLayout(text, 1)
        lay.addLayout(hero)

    def _build_tag_row(self, lay: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setSpacing(6)
        self._tags = QLabel()
        self._tags.setObjectName("DetailTags")
        self._tags.setWordWrap(True)
        row.addWidget(self._tags, 1)
        row.addWidget(self._mini_btn("编辑", self._edit_tags))
        lay.addLayout(row)

    def _build_actions(self, lay: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)

        launch_btn = QPushButton("▶  启动")
        launch_btn.setObjectName("PrimaryBtn")
        launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        launch_btn.clicked.connect(
            lambda: self._entry and self.launchRequested.emit(self._entry))

        open_btn = QPushButton("打开目录")
        open_btn.setObjectName("GhostBtn")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(lambda: self.openDirRequested.emit(self._entry))

        self._pin_btn = QPushButton("固定")
        self._pin_btn.setObjectName("GhostBtn")
        self._pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pin_btn.clicked.connect(self._toggle_pin)

        row.addWidget(launch_btn, 2)  # 启动是主按钮，占两份宽
        row.addWidget(open_btn, 1)
        row.addWidget(self._pin_btn, 1)
        lay.addLayout(row)

    def _build_command_section(self, lay: QVBoxLayout) -> None:
        head = QHBoxLayout()
        head.addWidget(self._section_label("启动命令"))
        head.addStretch(1)
        head.addWidget(self._mini_btn("编辑", self._edit_command))
        lay.addLayout(head)

        self._cmd = QLabel()
        self._cmd.setObjectName("CmdBox")
        self._cmd.setWordWrap(True)
        self._cmd.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._cmd)

    def _build_note_section(self, lay: QVBoxLayout) -> None:
        """笔记：预览（Markdown 渲染）和编辑（纯文本）共用一个 QStackedWidget。

        原文一直在 _note_edit 里，预览页只是它的渲染结果，
        保存永远从 _note_edit 取，跟当前显示哪页无关。
        """
        head = QHBoxLayout()
        self._note_label = self._section_label("笔记")
        head.addWidget(self._note_label)
        head.addStretch(1)
        self._mode_btn = self._mini_btn("编辑", self._toggle_mode)
        head.addWidget(self._mode_btn)
        self._save_btn = self._mini_btn("保存", self._save_note)
        head.addWidget(self._save_btn)
        lay.addLayout(head)

        self._note_view = QTextBrowser()
        self._note_view.setObjectName("NoteView")
        self._note_view.setOpenExternalLinks(True)
        self._note_view.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self._note_edit = QPlainTextEdit()
        self._note_edit.setObjectName("NoteEdit")
        self._note_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._note_edit.textChanged.connect(self._on_note_changed)

        self._note_stack = QStackedWidget()
        self._note_stack.addWidget(self._note_view)
        self._note_stack.addWidget(self._note_edit)
        self._note_stack.setMinimumHeight(150)
        lay.addWidget(self._note_stack, 1)

    def _build_stats_section(self, lay: QVBoxLayout) -> None:
        lay.addWidget(self._section_label("使用统计"))
        row = QHBoxLayout()
        row.setSpacing(8)
        self._runs = self._stat_box(row, "启动次数")
        self._last = self._stat_box(row, "最近使用")
        lay.addLayout(row)

    # ── 小组件 ──
    @staticmethod
    def _mini_btn(text: str, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("MiniBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(slot)
        return btn

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("DetailSection")
        return lbl

    @staticmethod
    def _stat_box(parent_row: QHBoxLayout, key: str) -> QLabel:
        """统计小卡片，返回数值 label，set_entry 时回写。"""
        box = QFrame()
        box.setObjectName("StatMini")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(11, 8, 11, 8)
        lay.setSpacing(1)
        value = QLabel("0")
        value.setObjectName("StatMiniValue")
        label = QLabel(key)
        label.setObjectName("StatMiniKey")
        lay.addWidget(value)
        lay.addWidget(label)
        parent_row.addWidget(box)
        return value

    # ── 对外接口 ──
    def set_entry(self, entry: Entry | None, icon: QIcon | None,
                  stats: dict) -> None:
        """切换展示的条目，None 回空态。切条目时强制退出编辑态，免得串到下一个条目。"""
        self._entry = entry
        self._editing = False
        self._note_dirty = False   # 切条目前 MainWindow 已 confirm_leave()
        self._note_stack.setCurrentWidget(self._note_view)
        self._mode_btn.setText("编辑")
        if not entry:
            self._empty.setVisible(True)
            self._body.setVisible(False)
            return
        self._empty.setVisible(False)
        self._body.setVisible(True)

        self._head.setText(f"详情 · {entry.cat_name}")
        # 笔记只支持目录条目：文件条目禁用保存/编辑，标签也说清楚
        note_ok = entry.is_dir or entry.note_path is not None
        self._save_btn.setEnabled(note_ok)
        self._mode_btn.setEnabled(note_ok)
        if entry.note_path:
            self._note_label.setText(f"笔记 · {entry.note_path.name}")
        elif entry.is_dir:
            self._note_label.setText("笔记 · NOTE.md（保存时创建）")
        else:
            self._note_label.setText("笔记（仅目录条目支持）")
        if icon:
            self._icon.setPixmap(icon.pixmap(52, 52))
        self._name.setText(entry.name)
        self._path.setText(str(entry.path))
        self._tags.setText("  ".join(f"#{t}" for t in entry.tags) or "暂无标签")
        self._pin_btn.setText("取消固定" if entry.pinned else "固定")
        cmd, shell = entry.command, entry.shell_type
        self._cmd.setText(f"[{shell}] {cmd}" if cmd else "默认（主程序 / 打开目录）")

        content = notes.read_note(entry.note_path) if entry.note_path else ""
        if not content:
            content = notes.DEFAULT_TEMPLATE.format(name=entry.name, time="")
        self._loading_note = True
        self._note_edit.setPlainText(content)
        self._loading_note = False
        self._note_dirty = False
        self._note_view.setMarkdown(content)

        self._runs.setText(str(stats.get("runs", 0)))
        self._last.setText(stats.get("last_run") or "—")

    # ── 内部动作 ──
    def _toggle_pin(self) -> None:
        if self._entry:
            self.pinToggled.emit(self._entry, not self._entry.pinned)

    def _edit_command(self) -> None:
        if not self._entry:
            return
        dlg = CommandDialog(self._entry.command or "",
                            self._entry.shell_type or DEFAULT_SHELL, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cmd, shell = dlg.result()
            self.commandEdited.emit(self._entry, cmd, shell)

    def _edit_tags(self) -> None:
        if not self._entry:
            return
        text, ok = QInputDialog.getText(
            self, "编辑标签", "多个标签用逗号分隔：",
            text=",".join(self._entry.tags))
        if ok:
            # 兼容中文逗号，去空白、去空项
            tags = [t.strip() for t in text.replace("，", ",").split(",") if t.strip()]
            self.tagsEdited.emit(self._entry, tags)

    def _toggle_mode(self) -> None:
        self._editing = not self._editing
        if self._editing:
            self._note_stack.setCurrentWidget(self._note_edit)
            self._mode_btn.setText("预览")
        else:
            self._note_view.setMarkdown(self._note_edit.toPlainText())
            self._note_stack.setCurrentWidget(self._note_view)
            self._mode_btn.setText("编辑")

    def _on_note_changed(self) -> None:
        if not self._loading_note:
            self._note_dirty = True

    def has_unsaved_note(self) -> bool:
        """是否有未保存的笔记编辑（切条目前 / 退出前询问用）。"""
        return self._note_dirty and self._entry is not None and self._entry.is_dir

    def confirm_leave(self) -> bool:
        """离开当前条目前的确认；返回 False 表示用户取消本次操作。"""
        if not self.has_unsaved_note():
            return True
        box = QMessageBox(self)
        box.setWindowTitle("笔记未保存")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(f"「{self._entry.name}」的笔记尚未保存，是否保存？")
        save_btn = box.addButton("保存", QMessageBox.ButtonRole.AcceptRole)
        discard_btn = box.addButton("不保存", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save_btn:
            return self._save_note()
        if clicked is discard_btn:
            self._note_dirty = False
            return True
        return False

    def _save_note(self) -> bool:
        if not self._entry or not self._entry.is_dir:
            return False
        note_path = notes.ensure_note(self._entry.path, self._entry.name)
        content = self._note_edit.toPlainText()
        if not notes.save_note(note_path, content):
            QMessageBox.warning(self, "保存失败", f"无法写入: {note_path}")
            return False
        self._entry.note_path = note_path
        self._note_dirty = False
        self.noteSaved.emit(self._entry)
        return True
