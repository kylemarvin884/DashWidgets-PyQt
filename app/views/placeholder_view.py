"""
占位符视图
"""
from PySide6.QtWidgets import QFrame, QVBoxLayout
from qfluentwidgets import SubtitleLabel, BodyLabel


class PlaceholderView(QFrame):
    """占位符视图，用于视图未实现时显示"""

    def __init__(self, title: str = "功能开发中"):
        super().__init__(parent=None)
        self.setObjectName(title + "View")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.addStretch()

        # 创建标签，不传parent参数
        title_label = SubtitleLabel(title)
        desc_label = BodyLabel("此功能正在开发中，敬请期待...")

        layout.addWidget(title_label)
        layout.addWidget(desc_label)

        layout.addStretch()
        layout.setContentsMargins(64, 64, 64, 64)


