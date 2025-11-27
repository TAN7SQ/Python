import sys
import asyncio
import websockets
import json
import threading
import paramiko
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import numpy as np

import qdarkstyle

from PySide6.QtCore import (
    Qt,
    QThread,
    Signal,
    QTimer,
    QSize,
    QRectF,
    QPointF,
    QObject,
    QUrl,
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTabWidget,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QCompleter,
    QScrollArea,
)
from PySide6.QtGui import (
    QImage,
    QPixmap,
    QPainter,
    QPen,
    QColor,
    QFont,
    QKeyEvent,
    QTextCursor,
)
from PySide6.QtMultimedia import QMediaPlayer, QMediaFormat
from PySide6.QtMultimediaWidgets import QVideoWidget


# ===================== 数据模型 =====================
@dataclass
class SSHConnection:
    """SSH连接配置"""

    host: str
    port: int = 22
    username: str = ""
    password: str = ""
    client: Optional[paramiko.SSHClient] = None
    shell: Optional[paramiko.Channel] = None
    is_connected: bool = False
    history: List[str] = field(default_factory=list)
    completions: List[str] = field(
        default_factory=lambda: [
            "ls",
            "cd",
            "pwd",
            "mkdir",
            "rm",
            "cp",
            "mv",
            "cat",
            "grep",
            "ps",
            "top",
            "ifconfig",
            "ping",
            "sudo",
            "apt-get",
            "yum",
            "docker",
            "git",
            "ssh",
        ]
    )


@dataclass
class WebSocketData:
    """WebSocket接收的数据模型"""

    timestamp: float
    variables: Dict[str, float] = field(default_factory=dict)


# ===================== SSH终端工作线程 =====================
class SSHWorker(QObject):
    """SSH后台工作线程，处理输入输出"""

    output_received = Signal(str)
    error_occurred = Signal(str)
    connection_closed = Signal()

    def __init__(self, connection: SSHConnection):
        super().__init__()
        self.connection = connection
        self.is_running = False

    def start(self):
        """启动工作线程"""
        self.is_running = True
        self.receive_output()

    def stop(self):
        """停止工作线程"""
        self.is_running = False

    def send_command(self, command: str):
        """发送命令"""
        try:
            if self.connection.shell and self.connection.is_connected:
                self.connection.shell.send(f"{command}\n")
        except Exception as e:
            self.error_occurred.emit(f"Failed to send command: {str(e)}")

    def receive_output(self):
        """持续接收SSH输出"""
        buffer = ""
        while self.is_running and self.connection.is_connected:
            try:
                if self.connection.shell and self.connection.shell.recv_ready():
                    data = self.connection.shell.recv(4096)
                    try:
                        output = data.decode("utf-8")
                    except UnicodeDecodeError:
                        output = data.decode("gbk", errors="ignore")

                    buffer += output

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        self.output_received.emit(line + "\n")

                    if buffer and len(buffer) > 100:
                        self.output_received.emit(buffer)
                        buffer = ""

                time.sleep(0.05)
            except Exception as e:
                if self.is_running:
                    self.error_occurred.emit(f"Connection error: {str(e)}")
                break

        if buffer:
            self.output_received.emit(buffer)
        self.connection_closed.emit()


# ===================== SSH终端窗口 =====================
class SSHTerminal(QWidget):
    """SSH终端窗口"""

    tab_close_requested = Signal()

    def __init__(self, connection: SSHConnection, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.worker = None
        self.worker_thread = None
        self.prompt = f"{connection.username}@{connection.host}:~$ "

        self.init_ui()
        self.init_ssh()
        self.setup_autocomplete()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # 输出区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.output_widget = QWidget()
        self.output_layout = QVBoxLayout(self.output_widget)
        self.output_layout.setContentsMargins(5, 5, 5, 5)
        self.output_layout.setSpacing(2)

        self.scroll_area.setWidget(self.output_widget)
        self.layout.addWidget(self.scroll_area, 1)

        # 输入区域
        self.input_layout = QHBoxLayout()
        self.input_layout.setContentsMargins(5, 5, 5, 5)
        self.input_layout.setSpacing(5)

        self.prompt_label = QLabel(self.prompt)
        self.input_edit = QLineEdit()
        self.input_edit.returnPressed.connect(self.send_command)
        self.input_edit.setFocusPolicy(Qt.StrongFocus)

        self.input_layout.addWidget(self.prompt_label)
        self.input_layout.addWidget(self.input_edit, 1)
        self.layout.addLayout(self.input_layout)

    def setup_autocomplete(self):
        """设置命令自动补全"""
        completer = QCompleter(self.connection.completions)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.input_edit.setCompleter(completer)

    def init_ssh(self):
        """初始化SSH连接"""
        try:
            self.connection.client = paramiko.SSHClient()
            self.connection.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.connection.client.connect(
                hostname=self.connection.host,
                port=self.connection.port,
                username=self.connection.username,
                password=self.connection.password,
                timeout=10,
                allow_agent=False,
                look_for_keys=False,
            )

            self.connection.shell = self.connection.client.invoke_shell(
                term="xterm", width=80, height=24
            )
            self.connection.shell.settimeout(0.5)
            self.connection.is_connected = True

            self.worker = SSHWorker(self.connection)
            self.worker_thread = QThread()
            self.worker.moveToThread(self.worker_thread)

            self.worker.output_received.connect(self.display_output)
            self.worker.error_occurred.connect(self.display_error)
            self.worker.connection_closed.connect(self.on_connection_closed)
            self.worker_thread.started.connect(self.worker.start)

            self.worker_thread.start()

            self.display_output(
                f"Successfully connected to {self.connection.host}:{self.connection.port}\n"
            )
            self.input_edit.setEnabled(True)
            self.input_edit.setFocus()

        except paramiko.AuthenticationException:
            QMessageBox.critical(
                self, "SSH Error", "Authentication failed: Check username/password"
            )
            self.tab_close_requested.emit()
        except paramiko.NoValidConnectionsError:
            QMessageBox.critical(
                self, "SSH Error", "Cannot connect to host: Check host/port"
            )
            self.tab_close_requested.emit()
        except Exception as e:
            QMessageBox.critical(self, "SSH Error", f"Connection failed: {str(e)}")
            self.tab_close_requested.emit()

    def display_output(self, output: str):
        """显示SSH输出"""
        label = QLabel(output)
        label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        label.setOpenExternalLinks(False)
        self.output_layout.addWidget(label)
        QTimer.singleShot(0, self.scroll_to_bottom)

    def display_error(self, error: str):
        """显示错误信息"""
        label = QLabel(f"\n[ERROR] {error}\n")
        self.output_layout.addWidget(label)
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        """滚动到最底部"""
        scroll_bar = self.scroll_area.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def send_command(self):
        """发送SSH命令"""
        command = self.input_edit.text().strip()
        if not command or not self.connection.is_connected:
            return

        self.display_output(f"{self.prompt}{command}\n")

        if command and command not in self.connection.history:
            self.connection.history.append(command)
            if command not in self.connection.completions:
                self.connection.completions.append(command)
                self.setup_autocomplete()

        if self.worker:
            self.worker.send_command(command)

        self.input_edit.clear()

    def on_connection_closed(self):
        """连接关闭处理"""
        self.connection.is_connected = False
        self.display_output("\nConnection closed\n")
        self.input_edit.setEnabled(False)
        QTimer.singleShot(2000, self.tab_close_requested.emit)

    def closeEvent(self, event):
        """关闭时清理资源"""
        if self.worker_thread and self.worker_thread.isRunning():
            if self.worker:
                self.worker.stop()
            self.worker_thread.quit()
            self.worker_thread.wait(1000)

        if self.connection.is_connected:
            self.connection.is_connected = False
            try:
                if self.connection.shell:
                    self.connection.shell.close()
                if self.connection.client:
                    self.connection.client.close()
            except:
                pass

        event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        """键盘事件处理"""
        if not self.input_edit.hasFocus():
            self.input_edit.setFocus()
            self.input_edit.keyPressEvent(event)
        else:
            super().keyPressEvent(event)


# ===================== SSH登录对话框 =====================
class SSHLoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SSH Login")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.connection = SSHConnection(host="")
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        self.host_edit = QLineEdit("192.168.1.100")
        self.port_edit = QLineEdit("22")
        self.port_edit.setMaximumWidth(80)
        self.user_edit = QLineEdit("pi")
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)

        layout.addRow("Host:", self.host_edit)
        layout.addRow("Port:", self.port_edit)
        layout.addRow("Username:", self.user_edit)
        layout.addRow("Password:", self.pass_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def accept(self):
        """验证并创建连接"""
        try:
            self.connection.host = self.host_edit.text().strip()
            self.connection.port = int(self.port_edit.text().strip())
            self.connection.username = self.user_edit.text().strip()
            self.connection.password = self.pass_edit.text().strip()

            if not self.connection.host:
                raise ValueError("Host cannot be empty")
            if self.connection.port < 1 or self.connection.port > 65535:
                raise ValueError("Invalid port number (1-65535)")
            if not self.connection.username:
                raise ValueError("Username cannot be empty")

            super().accept()
        except ValueError as e:
            QMessageBox.warning(self, "Input Error", str(e))


# ===================== RTSP视频播放器 =====================
class RTSPPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = None
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)

        # 视频显示区域
        self.video_widget = QVideoWidget()
        self.layout.addWidget(self.video_widget, 1)

        # 控制栏
        self.control_layout = QHBoxLayout()
        self.control_layout.setContentsMargins(10, 0, 10, 10)

        self.rtsp_edit = QLineEdit("rtsp://10.236.165.25:8554/live")
        self.rtsp_edit.setPlaceholderText(
            "Enter RTSP URL (e.g., rtsp://user:pass@ip:port/stream)"
        )

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_stream)

        self.control_layout.addWidget(self.rtsp_edit)
        self.control_layout.addWidget(self.connect_btn)
        self.layout.addLayout(self.control_layout)

    def toggle_stream(self):
        """连接/断开RTSP流"""
        if self.player and self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.stop()
            self.connect_btn.setText("Connect")
            self.rtsp_edit.setEnabled(True)
        else:
            self.start_stream()

    def start_stream(self):
        """启动RTSP流"""
        rtsp_url = self.rtsp_edit.text().strip()
        if not rtsp_url:
            QMessageBox.warning(self, "Input Error", "RTSP URL cannot be empty")
            return

        try:
            self.player = QMediaPlayer()
            self.player.setVideoOutput(self.video_widget)
            self.player.setSource(QUrl(rtsp_url))
            self.player.play()
            self.connect_btn.setText("Disconnect")
            self.rtsp_edit.setEnabled(False)
            QTimer.singleShot(3000, self.check_playback_status)

        except Exception as e:
            QMessageBox.critical(
                self, "Stream Error", f"Failed to start stream: {str(e)}"
            )
            self.connect_btn.setText("Connect")
            self.rtsp_edit.setEnabled(True)

    def check_playback_status(self):
        """检查播放状态"""
        if self.player and self.player.playbackState() != QMediaPlayer.PlayingState:
            QMessageBox.warning(
                self,
                "Stream Warning",
                "Failed to receive video stream.\n"
                "Possible reasons:\n"
                "1. GStreamer not installed or configured\n"
                "2. RTSP URL requires special auth (e.g., digest)\n"
                "3. Firewall blocking the connection",
            )


# ===================== WebSocket数据可视化 =====================
class DataVisualizer(QWidget):
    data_updated = Signal(WebSocketData)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.data_buffer: List[WebSocketData] = []
        self.max_data_points = 100
        self.variables: List[str] = []

        self.ws_thread = threading.Thread(target=self.run_websocket, daemon=True)
        self.ws_thread.start()

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot)
        self.update_timer.start(100)

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        # 标题
        self.title_label = QLabel("WebSocket Data Visualization")
        self.layout.addWidget(self.title_label)

        # 表格显示
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Variable", "Value"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.layout.addWidget(self.table, 1)

        # 图表显示
        self.plot_widget = PlotWidget()
        self.plot_widget.setMinimumHeight(250)
        self.layout.addWidget(self.plot_widget, 2)

        # WebSocket控制
        self.ws_layout = QHBoxLayout()
        self.ws_edit = QLineEdit("ws://localhost:8765")
        self.ws_edit.setPlaceholderText("WebSocket URL (ws://ip:port)")

        self.ws_btn = QPushButton("Reconnect")
        self.ws_btn.clicked.connect(self.restart_websocket)

        self.ws_status = QLabel("Disconnected")

        self.ws_layout.addWidget(self.ws_edit)
        self.ws_layout.addWidget(self.ws_btn)
        self.ws_layout.addWidget(self.ws_status)
        self.layout.addLayout(self.ws_layout)

    async def websocket_client(self):
        """WebSocket客户端"""
        url = self.ws_edit.text().strip()
        while True:
            try:
                async with websockets.connect(
                    url, ping_interval=30, ping_timeout=60
                ) as websocket:
                    self.ws_status.setText("Connected")

                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            ws_data = WebSocketData(
                                timestamp=data.get("timestamp", time.time()),
                                variables=data.get("variables", {}),
                            )
                            self.data_updated.emit(ws_data)
                            self.data_buffer.append(ws_data)
                            if len(self.data_buffer) > self.max_data_points:
                                self.data_buffer.pop(0)
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            print(f"Data processing error: {e}")
            except Exception as e:
                self.ws_status.setText(f"Disconnected (retrying...)")
                await asyncio.sleep(3)

    def run_websocket(self):
        """运行WebSocket事件循环"""
        asyncio.run(self.websocket_client())

    def restart_websocket(self):
        """重启WebSocket连接"""
        self.ws_thread = threading.Thread(target=self.run_websocket, daemon=True)
        self.ws_thread.start()

    def update_plot(self):
        """更新表格和图表"""
        if not self.data_buffer:
            return

        latest_data = self.data_buffer[-1]

        # 更新表格
        self.table.setRowCount(len(latest_data.variables))
        for row, (var, value) in enumerate(latest_data.variables.items()):
            var_item = QTableWidgetItem(var)
            var_item.setFlags(var_item.flags() & ~Qt.ItemIsEditable)

            val_item = QTableWidgetItem(f"{value:.2f}")
            val_item.setFlags(val_item.flags() & ~Qt.ItemIsEditable)
            val_item.setTextAlignment(Qt.AlignRight)

            self.table.setItem(row, 0, var_item)
            self.table.setItem(row, 1, val_item)

        # 更新变量列表
        new_vars = list(latest_data.variables.keys())
        if new_vars != self.variables:
            self.variables = new_vars
            self.plot_widget.set_variables(self.variables)

        # 更新图表数据
        times = [d.timestamp for d in self.data_buffer]
        values = {
            var: [d.variables.get(var, 0) for d in self.data_buffer]
            for var in self.variables
        }
        self.plot_widget.update_data(times, values)


class PlotWidget(QWidget):
    """自定义绘图组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.variables: List[str] = []
        self.times: List[float] = []
        self.values: Dict[str, List[float]] = {}
        self.colors = [
            QColor(255, 59, 48),
            QColor(52, 199, 89),
            QColor(0, 122, 255),
            QColor(255, 149, 0),
            QColor(175, 82, 222),
            QColor(255, 45, 85),
            QColor(90, 200, 250),
            QColor(255, 204, 0),
        ]
        self.x_axis_label = "Time"
        self.y_axis_label = "Value"

    def set_variables(self, variables: List[str]):
        self.variables = variables
        self.values = {var: [] for var in variables}

    def update_data(self, times: List[float], values: Dict[str, List[float]]):
        self.times = times
        self.values = values
        self.update()

    def paintEvent(self, event):
        if not self.times or not self.variables:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.fillRect(self.rect(), QColor(250, 250, 250))
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(self.rect(), Qt.AlignCenter, "No data to display")
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制背景
        painter.fillRect(self.rect(), QColor(250, 250, 250))

        # 绘制坐标轴
        margin = 40
        plot_rect = QRectF(
            margin,
            margin,
            self.width() - 2 * margin - 100,
            self.height() - 2 * margin,
        )

        # 计算轴范围
        x_min = min(self.times) if self.times else 0
        x_max = max(self.times) if self.times else 100
        x_range = x_max - x_min if x_max > x_min else 100

        y_values = []
        for var_values in self.values.values():
            y_values.extend([v for v in var_values if v is not None])
        y_min = min(y_values) - (max(y_values) - min(y_values)) * 0.1 if y_values else 0
        y_max = (
            max(y_values) + (max(y_values) - min(y_values)) * 0.1 if y_values else 10
        )
        y_range = y_max - y_min if y_max > y_min else 10

        # 绘制坐标轴线条
        pen = QPen(QColor(50, 50, 50), 1.5)
        painter.setPen(pen)
        painter.drawLine(plot_rect.bottomLeft(), plot_rect.bottomRight())
        painter.drawLine(plot_rect.bottomLeft(), plot_rect.topLeft())

        # 绘制轴标签
        painter.setPen(QColor(30, 30, 30))
        painter.setFont(QFont("Arial", 9))

        # X轴标签
        x_label_rect = QRectF(
            plot_rect.center().x() - 30, self.height() - margin + 5, 60, 20
        )
        painter.drawText(x_label_rect, Qt.AlignCenter, self.x_axis_label)

        # Y轴标签（旋转）
        painter.save()
        painter.translate(margin - 25, plot_rect.center().y())
        painter.rotate(-90)
        y_label_rect = QRectF(-30, -10, 60, 20)
        painter.drawText(y_label_rect, Qt.AlignCenter, self.y_axis_label)
        painter.restore()

        # 绘制网格
        pen.setStyle(Qt.DotLine)
        pen.setColor(QColor(200, 200, 200))
        painter.setPen(pen)

        # X轴网格
        x_ticks = 5
        for i in range(x_ticks + 1):
            x = plot_rect.left() + (i / x_ticks) * plot_rect.width()
            painter.drawLine(
                QPointF(x, plot_rect.top()), QPointF(x, plot_rect.bottom())
            )
            tick_value = x_min + (i / x_ticks) * x_range
            tick_label = f"{tick_value:.1f}"
            label_rect = QRectF(x - 20, plot_rect.bottom() + 5, 40, 15)
            painter.drawText(label_rect, Qt.AlignCenter, tick_label)

        # Y轴网格
        y_ticks = 5
        for i in range(y_ticks + 1):
            y = plot_rect.bottom() - (i / y_ticks) * plot_rect.height()
            painter.drawLine(
                QPointF(plot_rect.left(), y), QPointF(plot_rect.right(), y)
            )
            tick_value = y_min + (i / y_ticks) * y_range
            tick_label = f"{tick_value:.1f}"
            label_rect = QRectF(plot_rect.left() - 60, y - 7, 50, 15)
            painter.drawText(label_rect, Qt.AlignRight, tick_label)

        # 绘制数据曲线
        for idx, var in enumerate(self.variables):
            if var not in self.values or len(self.values[var]) != len(self.times):
                continue

            points = []
            valid_points = True
            for t, val in zip(self.times, self.values[var]):
                if val is None:
                    valid_points = False
                    break
                x = plot_rect.left() + ((t - x_min) / x_range) * plot_rect.width()
                y = plot_rect.bottom() - ((val - y_min) / y_range) * plot_rect.height()
                points.append(QPointF(x, y))

            if not valid_points or len(points) < 2:
                continue

            # 绘制折线
            pen = QPen(self.colors[idx % len(self.colors)], 2)
            painter.setPen(pen)
            for i in range(1, len(points)):
                painter.drawLine(points[i - 1], points[i])

            # 绘制数据点
            painter.setBrush(self.colors[idx % len(self.colors)])
            for point in points[:: max(1, len(points) // 20)]:
                painter.drawEllipse(point, 3, 3)

            # 绘制图例
            legend_x = plot_rect.right() + 20
            legend_y = margin + 20 + idx * 25
            if legend_y < self.height() - margin:
                painter.setBrush(self.colors[idx % len(self.colors)])
                painter.setPen(Qt.NoPen)
                painter.drawRect(legend_x, legend_y - 6, 12, 12)
                painter.setPen(QColor(30, 30, 30))
                painter.drawText(legend_x + 18, legend_y + 4, var)


# ===================== 文件上传组件 =====================
class FileUploader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ssh_connection: Optional[SSHConnection] = None
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        self.title_label = QLabel("File Upload (via SSH)")
        self.layout.addWidget(self.title_label)

        self.upload_layout = QHBoxLayout()
        self.upload_layout.setSpacing(10)

        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Select file to upload")
        self.file_edit.setReadOnly(True)

        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_file)

        self.upload_btn = QPushButton("Upload")
        self.upload_btn.clicked.connect(self.upload_file)
        self.upload_btn.setEnabled(False)

        self.upload_layout.addWidget(self.file_edit)
        self.upload_layout.addWidget(self.browse_btn)
        self.upload_layout.addWidget(self.upload_btn)
        self.layout.addLayout(self.upload_layout)

        # 上传状态
        self.status_layout = QHBoxLayout()
        self.status_icon = QLabel()
        self.status_label = QLabel("No file selected")
        self.status_layout.addWidget(self.status_icon)
        self.status_layout.addWidget(self.status_label)
        self.layout.addLayout(self.status_layout)

        # 目标路径
        self.path_layout = QHBoxLayout()
        self.path_label = QLabel("Remote Path:")
        self.remote_path = QLineEdit("/home/")
        self.path_layout.addWidget(self.path_label)
        self.path_layout.addWidget(self.remote_path)
        self.layout.addLayout(self.path_layout)

    def set_ssh_connection(self, connection: Optional[SSHConnection]):
        """设置SSH连接用于上传"""
        self.ssh_connection = connection
        is_connected = connection is not None and connection.is_connected
        self.upload_btn.setEnabled(is_connected and self.file_edit.text())

        if is_connected and connection.username:
            self.remote_path.setText(f"/home/{connection.username}/")

    def browse_file(self):
        """选择文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File", "", "All Files (*.*)"
        )
        if file_path:
            self.file_edit.setText(file_path)
            self.status_label.setText(f"Selected: {file_path.split('/')[-1]}")
            self.upload_btn.setEnabled(
                self.ssh_connection is not None and self.ssh_connection.is_connected
            )

    def upload_file(self):
        """上传文件到SSH服务器"""
        if not self.ssh_connection or not self.ssh_connection.is_connected:
            QMessageBox.warning(self, "Upload Error", "No active SSH connection")
            return

        file_path = self.file_edit.text().strip()
        if not file_path:
            QMessageBox.warning(self, "Upload Error", "No file selected")
            return

        remote_path = self.remote_path.text().strip()
        if not remote_path:
            QMessageBox.warning(self, "Upload Error", "Remote path cannot be empty")
            return

        if not remote_path.endswith("/"):
            remote_path += "/"

        file_name = file_path.split("/")[-1]
        full_remote_path = f"{remote_path}{file_name}"

        try:
            self.upload_btn.setEnabled(False)
            self.status_label.setText("Uploading...")

            sftp = self.ssh_connection.client.open_sftp()
            try:
                sftp.stat(remote_path)
            except IOError:
                sftp.mkdir(remote_path)

            sftp.put(file_path, full_remote_path)
            sftp.close()

            self.status_label.setText(f"Upload successful: {full_remote_path}")
        except Exception as e:
            error_msg = f"Upload failed: {str(e)}"
            self.status_label.setText(error_msg)
            QMessageBox.warning(self, "Upload Error", error_msg)
        finally:
            self.upload_btn.setEnabled(True)


# ===================== 主窗口 =====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RTSP + SSH + WebSocket Integrated Monitor")
        self.setMinimumSize(1400, 900)
        self.init_ui()

    def init_ui(self):
        # 中心组件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 左侧分割（上下布局）
        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.setHandleWidth(10)

        self.rtsp_player = RTSPPlayer()
        left_splitter.addWidget(self.rtsp_player)

        self.data_visualizer = DataVisualizer()
        left_splitter.addWidget(self.data_visualizer)

        left_splitter.setSizes([500, 400])
        main_layout.addWidget(left_splitter, 2)

        # 右侧分割（上下布局）
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.setHandleWidth(10)

        self.ssh_tab_widget = QTabWidget()
        self.ssh_tab_widget.setMovable(True)
        self.ssh_tab_widget.setTabsClosable(True)
        self.ssh_tab_widget.tabCloseRequested.connect(self.close_ssh_tab)

        self.add_ssh_btn = QPushButton("+ New SSH Terminal")
        self.add_ssh_btn.clicked.connect(self.add_ssh_terminal)
        self.ssh_tab_widget.setCornerWidget(self.add_ssh_btn, Qt.TopRightCorner)

        right_splitter.addWidget(self.ssh_tab_widget)

        self.file_uploader = FileUploader()
        right_splitter.addWidget(self.file_uploader)

        right_splitter.setSizes([600, 250])
        main_layout.addWidget(right_splitter, 1)

    def add_ssh_terminal(self):
        """添加新的SSH终端"""
        dialog = SSHLoginDialog(self)
        if dialog.exec():
            connection = dialog.connection
            terminal = SSHTerminal(connection)
            terminal.tab_close_requested.connect(
                lambda: self.close_ssh_tab(self.ssh_tab_widget.indexOf(terminal))
            )

            def update_upload_connection(index):
                if index >= 0:
                    current_widget = self.ssh_tab_widget.widget(index)
                    if isinstance(current_widget, SSHTerminal):
                        self.file_uploader.set_ssh_connection(current_widget.connection)

            self.ssh_tab_widget.currentChanged.connect(update_upload_connection)

            tab_index = self.ssh_tab_widget.addTab(
                terminal, f"{connection.username}@{connection.host}:{connection.port}"
            )
            self.ssh_tab_widget.setCurrentIndex(tab_index)
            update_upload_connection(tab_index)

    def close_ssh_tab(self, index):
        """关闭SSH标签页"""
        widget = self.ssh_tab_widget.widget(index)
        if widget:
            widget.close()
        self.ssh_tab_widget.removeTab(index)

        if self.ssh_tab_widget.count() > 0:
            current_widget = self.ssh_tab_widget.currentWidget()
            if isinstance(current_widget, SSHTerminal):
                self.file_uploader.set_ssh_connection(current_widget.connection)
        else:
            self.file_uploader.set_ssh_connection(None)


# ===================== 测试WebSocket服务器 =====================
def start_test_websocket_server():
    """启动测试用的WebSocket服务器"""
    import random
    import threading

    async def handle_client(websocket):
        """处理客户端连接"""
        print("WebSocket client connected")
        try:
            while True:
                data = {
                    "timestamp": time.time(),
                    "variables": {
                        "temperature": 20 + random.uniform(-5, 5),
                        "humidity": 50 + random.uniform(-10, 10),
                        "pressure": 1013 + random.uniform(-5, 5),
                        "voltage": 12 + random.uniform(-0.5, 0.5),
                    },
                }
                await websocket.send(json.dumps(data))
                await asyncio.sleep(0.001)
        except:
            print("WebSocket client disconnected")

    async def main():
        """启动服务器"""
        async with websockets.serve(handle_client, "localhost", 8765):
            print("Test WebSocket server started on ws://localhost:8765")
            await asyncio.Future()

    def run_server():
        asyncio.run(main())

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()


if __name__ == "__main__":
    # 启动测试WebSocket服务器（可选）
    start_test_websocket_server()

    app = QApplication(sys.argv)
    # 此处可添加开源主题，示例：
    # import qdarkstyle
    app.setStyleSheet(qdarkstyle.load_stylesheet())
    # 或
    # from qt_material import apply_stylesheet
    # apply_stylesheet(app, theme='light_blue.xml')

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
