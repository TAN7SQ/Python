from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QSlider,
    QFileDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PIL import Image, ImageFilter, ImageQt


class MyWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.btn = QPushButton("click to import image")
        self.btn.clicked.connect(self.pushed)

        self.lbShwoImag = QLabel(self)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 50)
        self.slider.setTickInterval(2)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.valueChanged.connect(self.silderBlur)

        self.mainlayout = QVBoxLayout()
        self.mainlayout.addWidget(self.btn)
        self.mainlayout.addWidget(self.lbShwoImag)
        self.mainlayout.addWidget(self.slider)
        self.setLayout(self.mainlayout)

    def pushed(self):
        self.image = Image.open(
            QFileDialog.getOpenFileName(
                self, "import image", ".", "image(*.png *.jpg)"
            )[0]
        )
        self.lbShwoImag.setPixmap(
            ImageQt.toqpixmap(self.image)
        )  # transe img to qtimage

    def silderBlur(self, value):
        self.blurPic = self.image.filter(ImageFilter.GaussianBlur(value))
        self.lbShwoImag.setPixmap(ImageQt.toqpixmap(self.blurPic))


if __name__ == "__main__":
    app = QApplication([])
    window = MyWindow()
    window.show()
    app.exec()
