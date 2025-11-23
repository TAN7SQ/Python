from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QInputDialog,
)


class MyWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(300, 200)

        self.btn = QPushButton("button")
        self.btn.clicked.connect(self.button_clicked)

        self.mainlayout = QVBoxLayout()
        self.mainlayout.addWidget(self.btn)
        self.setLayout(self.mainlayout)

    def button_clicked(self):
        # get item\double\int\text
        reply, ok = QInputDialog.getInt(
            self,
            "title",
            "conten",
            1,  # default number
            0,  # start number
            100,  # end numbver
            1,  # step
        )
        print(reply, ok)


if __name__ == "__main__":
    app = QApplication([])
    window = MyWindow()
    window.show()
    app.exec()
