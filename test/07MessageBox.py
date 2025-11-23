from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QMessageBox,
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
        # QMessageBox.information(self, "nihao", "helo")
        replay = QMessageBox.information(
            self,
            "title",
            "content",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.No,  # create btn
            QMessageBox.StandardButton.Ok,  # default btn
        )
        if replay == QMessageBox.StandardButton.Ok:
            print("clicl ok")
        elif replay == QMessageBox.StandardButton.No:
            print("click no")
        # QMessageBox.question(self, "nihao", "helo")
        # QMessageBox.warning(self, "nihao", "warning")
        # QMessageBox.critical(self, "nihao", "critical")


if __name__ == "__main__":
    app = QApplication([])
    window = MyWindow()
    window.show()
    app.exec()
