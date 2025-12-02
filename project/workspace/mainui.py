from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout

import qdarkstyle

from websockui import DataVisualizer


class MyWidow(QWidget):
    def __init__(self):
        super().__init__()

        self.websockui = DataVisualizer()

        self.mainlayout = QVBoxLayout()
        self.mainlayout.addWidget(self.websockui)

        self.setLayout(self.mainlayout)


def uiStyleSheet(app: QApplication):
    # 应用深色主题
    app.setStyleSheet(qdarkstyle.load_stylesheet())

    # 额外的样式修复，确保所有组件可见
    app.setStyleSheet(
        app.styleSheet()
        + """
        QDialog {
            background-color: #2E2E2E;
            color: #FFFFFF;
        }
        QLabel {
            color: #FFFFFF;
        }
        QMessageBox {
            background-color: #2E2E2E;
            color: #FFFFFF;
        }
        QMessageBox QPushButton {
            background-color: #3E3E3E;
            color: #FFFFFF;
            padding: 5px 15px;
        }
    """
    )


if __name__ == "__main__":
    app = QApplication([])
    uiStyleSheet(app)

    window = MyWidow()
    window.show()

    app.exec()
