from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
from Ui_login import Ui_login


class MyWindow(QWidget, Ui_login):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.pushButton.clicked.connect(self.loginFunc)

    def loginFunc(self):
        # 拿到username,password
        username = self.lineEdit.text()
        password = self.lineEdit_2.text()
        if username == "123" and password == "123":
            print("login success")
        else:
            print("login failed")


if __name__ == "__main__":
    app = QApplication([])
    window = MyWindow()
    window.show()
    app.exec()
