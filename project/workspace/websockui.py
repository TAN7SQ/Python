import sys
from PySide6.QtWidgets import QApplication

import asyncio
import websockets
import json
import threading
import time
from typing import List, Dict
from dataclasses import dataclass, field

from PySide6.QtCore import Qt, QTimer, Signal, QRectF, QPointF
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)
from PySide6.QtGui import QColor, QPainter, QPen, QFont


# ===================== 数据模型 =====================
@dataclass  # 作用：自动生成初始化(__init__)、打印(__repr__)、比较(__eq__)，三种函数
class WebSocketData:
    """WebSocket接收的数据模型"""

    timestamp: float
    variables: Dict[str, float] = field(default_factory=dict)


# ===================== WebSocket数据可视化 =====================
class DataVisualizer(QWidget):
    data_updated = Signal(WebSocketData)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.data_buffer: List[WebSocketData] = []
        self.max_data_points = 100
        self.variables: List[str] = []

        # 启动 WebSocket 线程
        self.ws_thread = threading.Thread(target=self.run_websocket, daemon=True)
        self.ws_thread.start()

        # 定时更新图表
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot)
        self.update_timer.start(100)

    def init_ui(self):
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(5, 5, 5, 5)
        self.mainLayout.setSpacing(1)

        # 标题
        self.title_label = QLabel("WebSocket Data Visualization")
        self.title_label.setStyleSheet(
            "font-size: 12pt; font-weight: bold; color: #FFFFFF;"
        )
        self.mainLayout.addWidget(self.title_label)

        # 表格显示
        self.table = QTableWidget()
        self.table.setMinimumHeight(150)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Variable", "Value"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet(
            "QTableWidget { background-color:#2E2E2E; color:#FFFFFF; }"
        )
        self.mainLayout.addWidget(self.table, 1)

        # 图表显示
        self.plot_widget = PlotWidget()
        self.plot_widget.setMinimumHeight(400)
        self.mainLayout.addWidget(self.plot_widget, 10)

        # WebSocket控制
        self.ws_layout = QHBoxLayout()
        self.ws_edit = QLineEdit("ws://localhost:8765")
        self.ws_edit.setPlaceholderText("WebSocket URL (ws://ip:port)")
        self.ws_edit.setStyleSheet(
            "background-color: white; color: black; padding: 5px;"
        )

        self.ws_btn = QPushButton("Reconnect")
        self.ws_btn.setStyleSheet("background-color:#2196F3; color:white;")
        self.ws_btn.clicked.connect(self.restart_websocket)

        self.ws_status = QLabel("Disconnected")
        self.ws_status.setStyleSheet("color:#FF5722; padding:0 10px;")

        self.ws_layout.addWidget(self.ws_edit)
        self.ws_layout.addWidget(self.ws_btn)
        self.ws_layout.addWidget(self.ws_status)
        self.mainLayout.addLayout(self.ws_layout)

    async def websocket_client(self):
        """WebSocket客户端"""
        # text获取 LineEdit 控件的字符，strip 去除空格
        url = self.ws_edit.text().strip()
        while True:
            try:
                async with websockets.connect(
                    url,
                    ping_interval=30,
                    ping_timeout=60,
                    # 每 30 秒发送一次心跳包,60 秒收不到则认为断联
                ) as websocket:
                    # 更新界面状态标签
                    self.ws_status.setText("Connected")
                    self.ws_status.setStyleSheet("color:#4CAF50; padding:0 10px;")

                    # async 异步迭代，持续接收服务器推送的消息
                    async for message in websocket:
                        try:
                            data = json.loads(message)  # 字符串解析成字典
                            ws_data = WebSocketData(
                                timestamp=data.get("timestamp", time.time()),
                                variables=data.get("variables", {}),
                            )
                            self.data_updated.emit(ws_data)  # 发出数据更新的信号
                            self.data_buffer.append(ws_data)
                            if len(self.data_buffer) > self.max_data_points:
                                self.data_buffer.pop(0)
                        except json.JSONDecodeError:
                            continue
            except Exception:
                self.ws_status.setText("Disconnected (retrying...)")
                self.ws_status.setStyleSheet("color:#FF5722; padding:0 10px;")
                await asyncio.sleep(3)

    def run_websocket(self):
        asyncio.run(self.websocket_client())

    def restart_websocket(self):
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
            var_item.setForeground(QColor("#FFFFFF"))

            val_item = QTableWidgetItem(f"{value:.2f}")
            val_item.setFlags(val_item.flags() & ~Qt.ItemIsEditable)
            val_item.setTextAlignment(Qt.AlignRight)
            val_item.setForeground(QColor("#FFFFFF"))

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
        self.plot_widget.update_data(times, values)  # 更新图表


# ===================== 绘图组件 =====================
class PlotWidget(QWidget):
    """自定义绘图组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
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
        self.x_axis_label, self.y_axis_label = "Time", "Value"

    def set_variables(self, variables: List[str]):
        self.variables = variables
        self.values = {var: [] for var in variables}

    def update_data(self, times: List[float], values: Dict[str, List[float]]):
        self.times = times
        self.values = values
        self.update()  # 产生一个更新事件，在内部会调用painEvent

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#2E2E2E"))

        # 如果没有数据
        if not self.times or not self.variables:
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(self.rect(), Qt.AlignCenter, "No data to display")
            return

        margin = 40
        plot_rect = QRectF(
            margin, margin, self.width() - 2 * margin - 100, self.height() - 2 * margin
        )

        # 坐标范围
        x_min, x_max = min(self.times), max(self.times)
        x_range = x_max - x_min if x_max > x_min else 100
        y_values = [v for vals in self.values.values() for v in vals]
        y_min = min(y_values) - (max(y_values) - min(y_values)) * 0.1 if y_values else 0
        y_max = (
            max(y_values) + (max(y_values) - min(y_values)) * 0.1 if y_values else 10
        )
        y_range = y_max - y_min if y_max > y_min else 10

        # 坐标轴
        pen = QPen(QColor(200, 200, 200), 1.5)
        painter.setPen(pen)
        painter.drawLine(plot_rect.bottomLeft(), plot_rect.bottomRight())
        painter.drawLine(plot_rect.bottomLeft(), plot_rect.topLeft())

        # 标签
        painter.setPen(QColor(200, 200, 200))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(
            QRectF(plot_rect.center().x() - 30, self.height() - margin + 5, 60, 20),
            Qt.AlignCenter,
            self.x_axis_label,
        )
        painter.save()
        painter.translate(margin - 25, plot_rect.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-30, -10, 60, 20), Qt.AlignCenter, self.y_axis_label)
        painter.restore()

        # 绘制网格
        pen.setStyle(Qt.DotLine)
        pen.setColor(QColor(80, 80, 80))
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
            # painter.setBrush(self.colors[idx % len(self.colors)])
            # for point in points[:: max(1, len(points) // 20)]:
            #     painter.drawEllipse(point, 3, 3)

            # 绘制图例
            legend_x = plot_rect.right() + 20
            legend_y = margin + 20 + idx * 25
            if legend_y < self.height() - margin:
                painter.setBrush(self.colors[idx % len(self.colors)])
                painter.setPen(Qt.NoPen)
                painter.drawRect(legend_x, legend_y - 6, 12, 12)
                painter.setPen(QColor(200, 200, 200))
                painter.drawText(legend_x + 18, legend_y + 4, var)


# ===================== 测试WebSocket服务器 =====================
def start_test_websocket_server():
    """启动测试用的WebSocket服务器"""
    import random
    import threading

    async def handle_client(websocket):
        """处理客户端连接"""
        print("WebSocket client connected")
        try:
            ts = 0
            st = 0.001
            while True:
                data = {
                    "timestamp": ts,
                    "variables": {
                        "temperature": 20 + random.uniform(-5, 5),
                        "humidity": 50 + random.uniform(-10, 10),
                        "pressure": 1013 + random.uniform(-5, 5),
                        "voltage": 12 + random.uniform(-0.5, 0.5),
                    },
                }
                ts = ts + 1
                await websocket.send(json.dumps(data))
                await asyncio.sleep(st)  # 降低发送频率，避免数据过多
        except:
            print("WebSocket client disconnected")

    async def main():
        """启动服务器"""
        async with websockets.serve(handle_client, host="localhost", port=8765):
            print("Test WebSocket server started on ws://localhost:8765")
            await asyncio.Future()

    def run_server():
        asyncio.run(main())

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()


def test_websock_window():
    start_test_websocket_server()
    """程序入口"""
    app = QApplication(sys.argv)
    window = DataVisualizer()
    window.setWindowTitle("WebSocket Data Visualizer")
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())


# 既能作为脚本运行，也能被 import
if __name__ == "__main__":
    test_websock_window()
