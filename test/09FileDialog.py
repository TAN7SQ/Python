from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QFileDialog,
)


class MyWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(300, 200)

        self.btn = QPushButton("get one file")
        self.btn.clicked.connect(
            lambda: print(
                QFileDialog.getOpenFileName(
                    self,
                    "title",  # window titile
                    ".",  # default open file path,in this file
                    "Al File(*);;py files(*.py *.c)",  # filter,using ;; to split it
                )
            )
        )
        self.btn2 = QPushButton("get multiple files")
        self.btn2.clicked.connect(
            lambda: print(
                QFileDialog.getOpenFileNames(
                    self,
                    "title",  # window titile
                    ".",  # default open file path,in this file
                    "Al File(*);;py files(*.py *.c)",  # filter,using ;; to split it
                )
            )
        )

        self.btn3 = QPushButton("open multiple folder")
        self.btn3.clicked.connect(
            lambda: print(
                QFileDialog.getExistingDirectory(
                    self,
                    "title",  # window titile
                    ".",  # default open file path,in this file
                )
            )
        )

        self.btn4 = QPushButton("save multiple folder")
        self.btn4.clicked.connect(
            lambda: print(
                QFileDialog.getSaveFileName(
                    self,
                    "title",  # window titile
                    ".",  # default open file path,in this file
                )
            )
        )

        self.mainlayout = QVBoxLayout()
        self.mainlayout.addWidget(self.btn)
        self.mainlayout.addWidget(self.btn2)
        self.mainlayout.addWidget(self.btn3)
        self.setLayout(self.mainlayout)


if __name__ == "__main__":
    app = QApplication([])
    window = MyWindow()
    window.show()
    app.exec()
