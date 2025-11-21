from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QLineEdit


class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        btn = QPushButton("button", self)  # 如果没有布局，一定要传入self
        btn.setGeometry(100, 100, 100, 200)
        btn.setToolTip("this can be press")

        lb = QLabel("lable", self)
        lb.setGeometry(0, 0, 20, 30)

        line = QLineEdit("", self)
        line.setPlaceholderText("please edit something")


if __name__ == "__main__":
    app = QApplication([])
    window = MyWindow()
    window.show()
    app.exec()
