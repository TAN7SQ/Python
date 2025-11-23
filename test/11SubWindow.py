from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QWidget,
    QPushButton,
    QLineEdit,
    QVBoxLayout,
)

# import qdarktheme

import qdarkstyle


class Subwindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(qdarkstyle.load_stylesheet_pyside6())

        self.lb = QLabel("this is sub window")
        self.lineEdit = QLineEdit()
        self.lineEdit.setText("subwindow inputline ")

        self.mainLayout = QVBoxLayout()
        self.mainLayout.addWidget(self.lb)
        self.mainLayout.addWidget(self.lineEdit)
        self.setLayout(self.mainLayout)


class MyWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(qdarkstyle.load_stylesheet_pyside6())

        self.subwindow = Subwindow()
        self.subwindow.show()

        self.lb = QLabel("this is main window")

        self.btnClose = QPushButton("close sub window")
        self.btnClose.clicked.connect(lambda: self.subwindow.close())
        self.btnHide = QPushButton("hid sub window")
        self.btnHide.clicked.connect(lambda: self.subwindow.hide())
        self.btnOpen = QPushButton("open sub window")
        self.btnOpen.clicked.connect(lambda: self.subwindow.show())

        self.mainLayout = QVBoxLayout()
        self.mainLayout.addWidget(self.lb)
        self.mainLayout.addWidget(self.btnClose)
        self.mainLayout.addWidget(self.btnHide)
        self.mainLayout.addWidget(self.btnOpen)
        self.setLayout(self.mainLayout)


if __name__ == "__main__":
    app = QApplication([])
    window = MyWindow()

    window.show()
    app.exec()
