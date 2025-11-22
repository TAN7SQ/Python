from PySide6.QtWidgets import QApplication, QWidget, QComboBox, QVBoxLayout


class MyWindow(QWidget):
    def __init__(self):
        super().__init__()

        comboBox = QComboBox(self)
        comboBox.addItems(["a", "b", "c"])

        comboBox.currentIndexChanged.connect(lambda: print(comboBox.currentText()))

        mainlayout = QVBoxLayout()
        mainlayout.addWidget(comboBox)


if __name__ == "__main__":
    app = QApplication([])
    window = MyWindow()
    window.show()
    app.exec()
