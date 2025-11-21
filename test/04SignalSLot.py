from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout


class MyWindow(QWidget):
    def __init__(self):
        super().__init__()

        mainlayout = QVBoxLayout()

        btn = QPushButton("button")
        btn.clicked.connect(self.hello)
        # clicked是信号，connect绑定槽，槽是self.hello（相当于回调函数）

        mainlayout.addWidget(btn)
        self.setLayout(mainlayout)

    def hello(self):
        print("hi")


if __name__ == "__main__":
    app = QApplication([])
    window = MyWindow()
    window.show()
    app.exec()
