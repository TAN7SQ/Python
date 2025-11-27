import sys
import cv2
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QMessageBox,
    QSizePolicy,
)
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
import paramiko
from paramiko.ssh_exception import SSHException, NoValidConnectionsError


class RTSPStreamThread(QThread):
    """RTSP视频流读取线程"""

    frame_signal = Signal(QImage)  # 帧信号（传递Qt图像格式）
    error_signal = Signal(str)  # 错误信号

    def __init__(self, rtsp_url):
        super().__init__()
        self.rtsp_url = rtsp_url
        self.is_running = True
        self.cap = None

    def run(self):
        # 初始化视频捕获
        self.cap = cv2.VideoCapture(self.rtsp_url)
        if not self.cap.isOpened():
            self.error_signal.emit(f"无法连接RTSP流：{self.rtsp_url}")
            return

        # 读取视频帧
        while self.is_running:
            ret, frame = self.cap.read()
            if not ret:
                self.error_signal.emit("RTSP流断开或读取失败")
                break

            # 转换颜色空间（BGR→RGB）
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # 转换为Qt图像格式
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(
                rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888
            )
            self.frame_signal.emit(qt_image)

            # 控制帧率（约30fps）
            self.msleep(33)

    def stop(self):
        self.is_running = False
        if self.cap:
            self.cap.release()
        self.wait()


class SSHClientThread(QThread):
    """SSH登录线程（避免阻塞UI）"""

    success_signal = Signal(str)  # 登录成功信号（返回提示）
    error_signal = Signal(str)  # 登录失败信号（返回错误信息）

    def __init__(self, host, port, username, password):
        super().__init__()
        self.host = host
        self.port = port
        self.username = username
        self.password = password

    def run(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            # 连接SSH服务器（超时10秒）
            ssh.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10,
            )
            self.success_signal.emit(
                f"SSH登录成功！\n主机：{self.host}\n用户：{self.username}"
            )
            ssh.close()
        except NoValidConnectionsError:
            self.error_signal.emit(f"无法连接主机：{self.host}:{self.port}")
        except SSHException as e:
            self.error_signal.emit(f"SSH登录失败：{str(e)}")
        except Exception as e:
            self.error_signal.emit(f"未知错误：{str(e)}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SSH登录 + RTSP流显示")
        self.setGeometry(100, 100, 1200, 600)  # 窗口大小：1200x600

        # 初始化线程
        self.ssh_thread = None
        self.rtsp_thread = None

        # 主布局（左右分栏）
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # ---------------------- 左侧SSH登录界面 ----------------------
        ssh_widget = QWidget()
        ssh_layout = QVBoxLayout(ssh_widget)
        ssh_layout.setSpacing(15)
        ssh_layout.setAlignment(Qt.AlignTop)

        # SSH标题
        ssh_title = QLabel("SSH登录")
        ssh_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        ssh_layout.addWidget(ssh_title)

        # 表单控件
        self.host_edit = self._create_labeled_edit(
            ssh_layout, "主机地址：", "192.168.1.100"
        )
        self.port_edit = self._create_labeled_edit(ssh_layout, "端口：", "22")
        self.user_edit = self._create_labeled_edit(ssh_layout, "用户名：", "root")
        self.pwd_edit = self._create_labeled_edit(
            ssh_layout, "密码：", "", is_password=True
        )

        # 登录按钮
        self.login_btn = QPushButton("SSH登录")
        self.login_btn.setStyleSheet("padding: 8px; font-size: 14px;")
        self.login_btn.clicked.connect(self.start_ssh_login)
        ssh_layout.addWidget(self.login_btn)

        # 登录状态标签
        self.ssh_status = QLabel("状态：未登录")
        self.ssh_status.setStyleSheet("color: #666; margin-top: 10px;")
        ssh_layout.addWidget(self.ssh_status)

        # ---------------------- 右侧RTSP流显示界面 ----------------------
        rtsp_widget = QWidget()
        rtsp_layout = QVBoxLayout(rtsp_widget)
        rtsp_layout.setSpacing(15)

        # RTSP标题
        rtsp_title = QLabel("RTSP视频流")
        rtsp_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        rtsp_layout.addWidget(rtsp_title)

        # RTSP地址输入
        self.rtsp_edit = self._create_labeled_edit(
            rtsp_layout, "RTSP地址：", "rtsp://admin:123456@192.168.1.101:554/stream1"
        )

        # 流控制按钮（开始/停止）
        btn_layout = QHBoxLayout()
        self.start_rtsp_btn = QPushButton("开始播放")
        self.start_rtsp_btn.setStyleSheet("padding: 8px; font-size: 14px;")
        self.start_rtsp_btn.clicked.connect(self.start_rtsp_stream)
        btn_layout.addWidget(self.start_rtsp_btn)

        self.stop_rtsp_btn = QPushButton("停止播放")
        self.stop_rtsp_btn.setStyleSheet("padding: 8px; font-size: 14px;")
        self.stop_rtsp_btn.clicked.connect(self.stop_rtsp_stream)
        self.stop_rtsp_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_rtsp_btn)
        rtsp_layout.addLayout(btn_layout)

        # 视频显示标签
        self.video_label = QLabel("等待播放...")
        self.video_label.setStyleSheet(
            "border: 1px solid #ccc; background-color: #f5f5f5;"
        )
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        rtsp_layout.addWidget(self.video_label)

        # RTSP状态标签
        self.rtsp_status = QLabel("流状态：未播放")
        self.rtsp_status.setStyleSheet("color: #666;")
        rtsp_layout.addWidget(self.rtsp_status)

        # ---------------------- 加入主布局 ----------------------
        main_layout.addWidget(rtsp_widget, stretch=2)  # 右侧占2份宽度
        main_layout.addWidget(ssh_widget, stretch=1)  # 左侧占1份宽度

    def _create_labeled_edit(
        self, parent_layout, label_text, default_text, is_password=False
    ):
        """创建带标签的输入框（复用控件）"""
        layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(80)
        edit = QLineEdit(default_text)
        if is_password:
            edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(label)
        layout.addWidget(edit)
        parent_layout.addLayout(layout)
        return edit

    def start_ssh_login(self):
        """启动SSH登录（通过线程避免UI阻塞）"""
        # 获取输入参数
        host = self.host_edit.text().strip()
        port = (
            int(self.port_edit.text().strip())
            if self.port_edit.text().strip().isdigit()
            else 22
        )
        username = self.user_edit.text().strip()
        password = self.pwd_edit.text().strip()

        # 验证输入
        if not host or not username:
            QMessageBox.warning(self, "输入错误", "主机地址和用户名不能为空！")
            return

        # 停止之前的登录线程（如果存在）
        if self.ssh_thread and self.ssh_thread.isRunning():
            QMessageBox.information(self, "提示", "正在登录中，请稍后...")
            return

        # 更新UI状态
        self.login_btn.setEnabled(False)
        self.ssh_status.setText("状态：登录中...")
        self.ssh_status.setStyleSheet("color: #0066cc; margin-top: 10px;")

        # 启动登录线程
        self.ssh_thread = SSHClientThread(host, port, username, password)
        self.ssh_thread.success_signal.connect(self.on_ssh_success)
        self.ssh_thread.error_signal.connect(self.on_ssh_error)
        self.ssh_thread.start()

    def on_ssh_success(self, msg):
        """SSH登录成功回调"""
        self.ssh_status.setText(f"状态：已登录\n{msg}")
        self.ssh_status.setStyleSheet("color: #2e8b57; margin-top: 10px;")
        self.login_btn.setEnabled(True)
        QMessageBox.information(self, "登录成功", msg)

    def on_ssh_error(self, err_msg):
        """SSH登录失败回调"""
        self.ssh_status.setText(f"状态：登录失败\n{err_msg}")
        self.ssh_status.setStyleSheet("color: #dc143c; margin-top: 10px;")
        self.login_btn.setEnabled(True)
        QMessageBox.warning(self, "登录失败", err_msg)

    def start_rtsp_stream(self):
        """启动RTSP流播放"""
        rtsp_url = self.rtsp_edit.text().strip()
        if not rtsp_url:
            QMessageBox.warning(self, "输入错误", "RTSP地址不能为空！")
            return

        # 停止之前的流线程（如果存在）
        if self.rtsp_thread and self.rtsp_thread.isRunning():
            self.stop_rtsp_stream()

        # 更新UI状态
        self.start_rtsp_btn.setEnabled(False)
        self.stop_rtsp_btn.setEnabled(True)
        self.rtsp_status.setText("流状态：播放中...")
        self.rtsp_status.setStyleSheet("color: #2e8b57;")

        # 启动RTSP线程
        self.rtsp_thread = RTSPStreamThread(rtsp_url)
        self.rtsp_thread.frame_signal.connect(self.update_video_frame)
        self.rtsp_thread.error_signal.connect(self.on_rtsp_error)
        self.rtsp_thread.start()

    def stop_rtsp_stream(self):
        """停止RTSP流播放"""
        if self.rtsp_thread and self.rtsp_thread.isRunning():
            self.rtsp_thread.stop()
        self.start_rtsp_btn.setEnabled(True)
        self.stop_rtsp_btn.setEnabled(False)
        self.rtsp_status.setText("流状态：未播放")
        self.rtsp_status.setStyleSheet("color: #666;")
        self.video_label.setText("等待播放...")

    def update_video_frame(self, qt_image):
        """更新视频帧显示（自适应标签大小）"""
        # 缩放图像以适应标签尺寸（保持宽高比）
        scaled_image = qt_image.scaled(
            self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video_label.setPixmap(QPixmap.fromImage(scaled_image))

    def on_rtsp_error(self, err_msg):
        """RTSP流错误回调"""
        self.rtsp_status.setText(f"流状态：错误\n{err_msg}")
        self.rtsp_status.setStyleSheet("color: #dc143c;")
        self.start_rtsp_btn.setEnabled(True)
        self.stop_rtsp_btn.setEnabled(False)
        self.video_label.setText(f"播放失败：{err_msg}")
        QMessageBox.warning(self, "流错误", err_msg)

    def closeEvent(self, event):
        """窗口关闭时停止所有线程"""
        self.stop_rtsp_stream()
        if self.ssh_thread and self.ssh_thread.isRunning():
            self.ssh_thread.terminate()
            self.ssh_thread.wait()
        event.accept()


if __name__ == "__main__":
    # 安装依赖提示：pip install pyside6 paramiko opencv-python
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
