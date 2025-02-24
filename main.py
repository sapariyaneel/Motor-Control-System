import sys
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                            QGridLayout, QFrame, QSpinBox, QTabWidget, QStyleFactory, QComboBox)
from PyQt5.QtCore import QTimer, Qt, QRect
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QBrush, QIntValidator
import pyqtgraph as pg
from sensor_interface import GyroSensor
from fft_processor import FFTProcessor
import csv
from datetime import datetime
import serial.tools.list_ports
import time

STYLES = {
    'BACKGROUND': '#ffffff',
    'DARK_BG': '#f0f0f0',
    'TEXT': '#000000',
    'BUTTON_BLUE': '#2196F3',
    'BUTTON_NAVY': '#1976D2',
    'BUTTON_RED': '#F44336',
    'BUTTON_GREEN': '#4CAF50',
    'MOTOR1_COLOR': '#2196F3',
    'MOTOR2_COLOR': '#E91E63',
    'MOTOR3_COLOR': '#4CAF50',
    'GAUGE_BORDER': '#F44336',
    'INPUT_BG': '#ffffff',
    'CONNECTED_GREEN': '#4CAF50',
    'TAB_BG': '#f5f5f5',
    'TAB_SELECTED': '#2196F3',
    'BORDER': '#e0e0e0'
}

class CircularGauge(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.value = 0
        self.title = title
        self.setMinimumSize(200, 200)
        
    def setValue(self, value):
        self.value = value
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw circle
        center = self.rect().center()
        radius = min(self.width(), self.height()) // 2 - 10
        painter.setPen(QPen(QColor(STYLES['GAUGE_BORDER']), 2))
        painter.drawEllipse(center, radius, radius)
        
        # Draw ticks and numbers
        for i in range(0, 360, 20):
            angle = np.radians(i)
            start_point = (center.x() + (radius-10) * np.sin(angle),
                         center.y() - (radius-10) * np.cos(angle))
            end_point = (center.x() + radius * np.sin(angle),
                        center.y() - radius * np.cos(angle))
            painter.drawLine(int(start_point[0]), int(start_point[1]),
                           int(end_point[0]), int(end_point[1]))
            
            # Draw numbers
            number_point = (center.x() + (radius-25) * np.sin(angle),
                          center.y() - (radius-25) * np.cos(angle))
            painter.drawText(int(number_point[0]-15), int(number_point[1]+5), 
                           str(i))
        
        # Draw needle
        painter.setPen(QPen(QColor(STYLES['MOTOR1_COLOR']), 3))
        angle = np.radians(self.value)
        end_point = (center.x() + (radius-20) * np.sin(angle),
                    center.y() - (radius-20) * np.cos(angle))
        painter.drawLine(center.x(), center.y(),
                        int(end_point[0]), int(end_point[1]))
        
        # Draw value
        painter.drawText(10, self.height()-10, f"{self.title}= {self.value:.4f}°")

class ArtificialHorizon(QWidget):
    def __init__(self):
        super().__init__()
        self.pitch = 0
        self.roll = 0
        self.setMinimumSize(300, 300)
        
    def setPitchRoll(self, pitch, roll):
        self.pitch = max(-90, min(90, pitch))  # Clamp between -90 and 90
        self.roll = roll % 360  # Keep roll between 0 and 360
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            
            width = self.width()
            height = self.height()
            center_x = width // 2
            center_y = height // 2
            radius = min(width, height) // 2 - 10
            
            # Draw outer circle
            painter.setPen(QPen(QColor(STYLES['GAUGE_BORDER']), 2))
            painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
            
            # Save state before rotation
            painter.save()
            painter.translate(center_x, center_y)
            painter.rotate(-self.roll)
            
            # Draw sky and ground
            sky_rect = QRect(-radius, -radius - int(self.pitch * radius/90), 
                            2*radius, radius + int(self.pitch * radius/90))
            ground_rect = QRect(-radius, -int(self.pitch * radius/90), 
                               2*radius, radius - int(self.pitch * radius/90))
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor('#87CEEB'))  # Sky blue
            painter.drawRect(sky_rect)
            painter.setBrush(QColor('#8B4513'))  # Saddle brown
            painter.drawRect(ground_rect)
            
            # Draw pitch lines
            painter.setPen(QPen(Qt.white, 2))
            for i in range(-90, 91, 10):
                if i == 0:
                    continue
                y = int(-i * radius/90)  # Convert to int
                painter.drawLine(-radius//2, y, radius//2, y)
                painter.drawText(-radius//2 - 20, y + 5, f"{i}")
            
            painter.restore()
            
            # Draw fixed aircraft reference
            painter.setPen(QPen(Qt.yellow, 3))
            painter.drawLine(center_x - 40, center_y, center_x + 40, center_y)
            painter.drawLine(center_x, center_y - 40, center_x, center_y + 40)
        finally:
            painter.end()

class ArtificialHorizonTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        
        self.horizon = ArtificialHorizon()
        self.layout.addWidget(self.horizon)
        
        values_layout = QHBoxLayout()
        self.pitch_label = QLabel("Pitch: 0.0°")
        self.roll_label = QLabel("Roll: 0.0°")
        self.yaw_label = QLabel("Yaw: 0.0°")
        
        for label in [self.pitch_label, self.roll_label, self.yaw_label]:
            label.setStyleSheet(f"color: {STYLES['TEXT']}; font-size: 14px;")
            values_layout.addWidget(label)
            
        self.layout.addLayout(values_layout)
        
    def update_data(self):
        t = time.time()
        # Create smooth oscillating values
        pitch = 125 + 25 * np.sin(t * 0.5)
        roll = 195 + 25 * np.sin(t * 0.5 + 2)
        yaw = 260 + 25 * np.sin(t * 0.5 + 4)
        
        self.horizon.setPitchRoll(pitch, roll)
        self.pitch_label.setText(f"Pitch= {pitch:.4f}°")
        self.roll_label.setText(f"Roll= {roll:.4f}°")
        self.yaw_label.setText(f"Yaw= {yaw:.4f}°")

class EncoderTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        
        gauges_layout = QHBoxLayout()
        self.encoder1 = CircularGauge("Encoder 1")
        self.encoder2 = CircularGauge("Encoder 2")
        self.encoder3 = CircularGauge("Encoder 3")
        
        gauges_layout.addWidget(self.encoder1)
        gauges_layout.addWidget(self.encoder2)
        gauges_layout.addWidget(self.encoder3)
        
        self.layout.addLayout(gauges_layout)
        
        self.plot = pg.PlotWidget(title="Encoder Values")
        self.plot.setBackground('w')
        self.plot.showGrid(x=True, y=True)
        self.plot.setLabel('bottom', 'Time (s)')
        self.plot.setLabel('left', 'Angle (°)')
        self.plot.addLegend()
        
        self.layout.addWidget(self.plot)
        
    def update_data(self):
        t = time.time()
        # Create smooth oscillating values
        e1 = 125 + 25 * np.sin(t * 0.5)
        e2 = 195 + 25 * np.sin(t * 0.5 + 2)
        e3 = 260 + 25 * np.sin(t * 0.5 + 4)
        
        self.encoder1.setValue(e1)
        self.encoder2.setValue(e2)
        self.encoder3.setValue(e3)
        
        # Update plot data
        if not hasattr(self, 'time_data'):
            self.time_data = list(range(120))
            self.encoder_data = {'E1': [], 'E2': [], 'E3': []}
        
        # Add new data points
        self.encoder_data['E1'].append(e1)
        self.encoder_data['E2'].append(e2)
        self.encoder_data['E3'].append(e3)
        
        # Keep last 120 points
        for key in self.encoder_data:
            if len(self.encoder_data[key]) > 120:
                self.encoder_data[key].pop(0)
        
        # Update plot
        self.plot.clear()
        colors = {'E1': STYLES['MOTOR1_COLOR'], 
                  'E2': STYLES['MOTOR2_COLOR'], 
                  'E3': STYLES['MOTOR3_COLOR']}
        for key, color in colors.items():
            self.plot.plot(self.time_data[:len(self.encoder_data[key])], 
                          self.encoder_data[key], 
                          pen=color, name=key)

class MotorControlTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        
        # Initialize data buffers
        self.data_buffer = {
            'position': {'M1': [], 'M2': [], 'M3': []},
            'speed': {'M1': [], 'M2': [], 'M3': []},
            'torque': {'M1': [], 'M2': [], 'M3': []},
            'temp': {'M1': [], 'M2': [], 'M3': []},
            'voltage': {'M1': [], 'M2': [], 'M3': []}
        }
        
        self.is_paused = False
        self.filter_enabled = False
        
        self.initUI()
        self.connectSignals()
        
        # Add input validation
        for input_list in [self.torque_inputs, self.position_inputs, self.velocity_inputs]:
            for input_widget in input_list:
                input_widget.setValidator(QIntValidator())
        
    def updatePlots(self):
        try:
            # Create time data for x-axis
            time_data = np.linspace(0, 6, len(next(iter(self.data_buffer['speed'].values()))))
            
            # Update each plot
            for data_type, plot in self.plots.items():
                plot.clear()
                for motor, color in [('M1', STYLES['MOTOR1_COLOR']), 
                                   ('M2', STYLES['MOTOR2_COLOR']), 
                                   ('M3', STYLES['MOTOR3_COLOR'])]:
                    if len(self.data_buffer[data_type][motor]) > 0:
                        plot.plot(time_data[-len(self.data_buffer[data_type][motor]):],
                                self.data_buffer[data_type][motor],
                                pen=color, name=f"Motor {motor[1]}")
        except Exception as e:
            print(f"Error updating plots: {str(e)}")

    def initUI(self):
        # Main horizontal layout to split controls and graphs
        main_layout = QHBoxLayout()
        
        # Left side (gauges and graphs)
        left_panel = QVBoxLayout()
        
        # Encoder gauges at top
        gauge_layout = QHBoxLayout()
        self.encoder_gauges = []
        for i in range(3):
            gauge = CircularGauge(f"Encoder {i+1}")
            gauge.setMinimumSize(250, 250)  # Make gauges bigger
            self.encoder_gauges.append(gauge)
            gauge_layout.addWidget(gauge)
        left_panel.addLayout(gauge_layout)
        
        # Graphs below gauges
        graphs_layout = QGridLayout()
        self.setupGraphs(graphs_layout)
        left_panel.addLayout(graphs_layout)
        
        # Right side (controls)
        right_panel = QVBoxLayout()
        
        # Top control buttons
        top_controls = QHBoxLayout()
        self.pause_btn = self.createStyledButton("PAUSE", STYLES['BUTTON_BLUE'])
        self.filter_btn = self.createStyledButton("FILTER", STYLES['BUTTON_BLUE'])
        self.home_btn = self.createStyledButton("SET HOME", STYLES['BUTTON_BLUE'])
        
        top_controls.addWidget(self.pause_btn)
        top_controls.addWidget(self.filter_btn)
        top_controls.addWidget(self.home_btn)
        right_panel.addLayout(top_controls)
        
        # Motor controls
        motor_controls = QGridLayout()
        self.setupMotorControls(motor_controls)
        self.setupValueDisplays(motor_controls)
        right_panel.addLayout(motor_controls)
        
        # Add left and right panels to main layout
        main_layout.addLayout(left_panel, stretch=2)  # Give more space to left panel
        main_layout.addLayout(right_panel, stretch=1)
        
        # Bottom controls (ports, etc.)
        bottom_controls = QHBoxLayout()
        self.setupBottomControls(bottom_controls)
        
        # Add everything to the main vertical layout
        self.layout.addLayout(main_layout)
        self.layout.addLayout(bottom_controls)

    def setupMotorControls(self, layout):
        # Motor labels with proper styling
        for i, color in enumerate([STYLES['MOTOR1_COLOR'], STYLES['MOTOR2_COLOR'], STYLES['MOTOR3_COLOR']]):
            motor_label = QLabel(f"MOTOR {i+1}")
            motor_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 14px;")
            layout.addWidget(motor_label, 0, i+1)  # Changed column index
        
        # Add controls with less spacing
        row = 1
        
        # Torque controls
        layout.addWidget(QLabel("Torque Limit (0-100%)"), row, 0)
        self.torque_inputs = []
        for i in range(3):
            input_widget = QLineEdit("100")
            input_widget.setFixedWidth(80)
            layout.addWidget(input_widget, row, i+1)
            self.torque_inputs.append(input_widget)
        self.set_torque_btn = self.createStyledButton("Set Torque", STYLES['BUTTON_BLUE'])
        layout.addWidget(self.set_torque_btn, row, 4)
        
        # Position controls
        row += 1
        layout.addWidget(QLabel("Position (0-300°)"), row, 0)
        self.position_inputs = []
        for i in range(3):
            input_widget = QLineEdit("150")
            input_widget.setFixedWidth(80)
            layout.addWidget(input_widget, row, i+1)
            self.position_inputs.append(input_widget)
        self.set_position_btn = self.createStyledButton("Set Position", STYLES['BUTTON_BLUE'])
        self.sync_position_btn = self.createStyledButton("Sync Position", STYLES['BUTTON_BLUE'])
        layout.addWidget(self.set_position_btn, row, 4)
        layout.addWidget(self.sync_position_btn, row, 5)
        
        # Velocity controls
        row += 1
        layout.addWidget(QLabel("Velocity (0-2047)"), row, 0)
        self.velocity_inputs = []
        for i in range(3):
            input_widget = QLineEdit("1024")
            input_widget.setFixedWidth(80)
            layout.addWidget(input_widget, row, i+1)
            self.velocity_inputs.append(input_widget)
        self.set_velocity_btn = self.createStyledButton("Set Velocity", STYLES['BUTTON_BLUE'])
        self.sync_velocity_btn = self.createStyledButton("Sync Velocity", STYLES['BUTTON_BLUE'])
        layout.addWidget(self.set_velocity_btn, row, 4)
        layout.addWidget(self.sync_velocity_btn, row, 5)

    def setupBottomControls(self, layout):
        # COM port controls group
        com_group = QHBoxLayout()
        
        # Create combobox for COM ports instead of line edit
        self.com_box = QComboBox()
        self.updateComPorts()  # Initial port list
        self.com_box.setFixedWidth(100)
        
        self.refresh_btn = self.createStyledButton("REFRESH", STYLES['BUTTON_BLUE'])
        self.refresh_btn.clicked.connect(self.updateComPorts)
        
        self.connect_btn = self.createStyledButton("CONNECT", STYLES['BUTTON_BLUE'])
        self.connect_label = QLabel("DISCONNECTED")
        self.connect_label.setStyleSheet("background-color: red; padding: 5px; border-radius: 3px;")
        self.disconnect_btn = self.createStyledButton("DISCONNECT", STYLES['BUTTON_BLUE'])
        
        # Add save controls
        self.file_box = QLineEdit("Test1.txt")
        self.file_box.setFixedWidth(100)
        self.save_btn = self.createStyledButton("SAVE", STYLES['BUTTON_BLUE'])
        
        # Add stop button
        self.stop_btn = self.createStyledButton("STOP", STYLES['BUTTON_RED'])
        
        # Add all controls to layout
        for widget in [self.com_box, self.refresh_btn, self.connect_btn, 
                      self.connect_label, self.disconnect_btn,
                      self.file_box, self.save_btn, self.stop_btn]:
            com_group.addWidget(widget)
        
        # Add motor status indicators
        self.motor_status = []
        status_layout = QHBoxLayout()
        for i, color in enumerate([STYLES['MOTOR1_COLOR'], STYLES['MOTOR2_COLOR'], STYLES['MOTOR3_COLOR']]):
            status = QLabel("●")
            status.setStyleSheet(f"color: red; font-size: 24px; padding: 5px;")
            self.motor_status.append(status)
            status_layout.addWidget(status)
        
        com_group.addLayout(status_layout)
        layout.addLayout(com_group)

    def setupGraphs(self, layout):
        # Create plots with proper styling
        self.plots = {}
        plot_configs = {
            'speed': ('Speed', 'RPM', (-10, 120)),
            'torque': ('Torque', '%', (0, 100)),
            'temp': ('Temperature', '°C', (20, 60)),
            'voltage': ('Voltage', 'V', (10, 14))
        }
        
        row = 0
        col = 0
        for data_type, (title, unit, y_range) in plot_configs.items():
            plot = pg.PlotWidget(title=f"{title} vs Time")
            plot.setBackground('w')
            plot.showGrid(x=True, y=True, alpha=0.3)  # Make grid lighter
            plot.setLabel('left', title, unit)
            plot.setLabel('bottom', 'Time', 's')
            plot.setYRange(y_range[0], y_range[1])
            plot.addLegend()
            plot.getAxis('bottom').setPen('k')
            plot.getAxis('left').setPen('k')
            plot.getAxis('bottom').setTextPen('k')
            plot.getAxis('left').setTextPen('k')
            
            # Set fixed height and width
            plot.setMinimumHeight(200)
            plot.setMinimumWidth(300)
            
            layout.addWidget(plot, row, col)
            self.plots[data_type] = plot
            
            col = (col + 1) % 2
            if col == 0:
                row += 1

    def createStyledButton(self, text, color):
        btn = QPushButton(text)
        hover_color = self.adjustColor(color, 1.2)
        pressed_color = self.adjustColor(color, 0.8)
        
        style = f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 3px;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                color: white;
            }}
            QPushButton:pressed {{
                background-color: {pressed_color};
            }}
            QPushButton:disabled {{
                background-color: #cccccc;
                color: #666666;
            }}
        """
        btn.setStyleSheet(style)
        return btn

    def adjustColor(self, color, factor):
        # Helper method to adjust color brightness
        color = color.lstrip('#')
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        rgb = tuple(min(255, int(c * factor)) for c in rgb)
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    def getValueDisplayStyle(self):
        return f"""
            QLineEdit {{
                background-color: {STYLES['BUTTON_NAVY']};
                color: white;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
                font-size: 12px;
            }}
        """

    def getInputStyle(self):
        return f"""
            QLineEdit {{
                background-color: {STYLES['INPUT_BG']};
                color: {STYLES['TEXT']};
                border: 1px solid {STYLES['BORDER']};
                border-radius: 3px;
                padding: 5px;
                font-size: 12px;
            }}
        """

    def createStyledPlot(self, title, ymin, ymax):
        plot = pg.PlotWidget(title=title)
        plot.setBackground('w')
        plot.showGrid(x=True, y=True)
        plot.setLabel('bottom', 'Time (s)')
        plot.setLabel('left', title)
        plot.setYRange(ymin, ymax)
        plot.addLegend()
        
        # Style the plot
        plot.getAxis('bottom').setPen('k')
        plot.getAxis('left').setPen('k')
        plot.getAxis('bottom').setTextPen('k')
        plot.getAxis('left').setTextPen('k')
        
        return plot

    def connectSignals(self):
        # Connect all button signals
        self.pause_btn.clicked.connect(self.togglePause)
        self.filter_btn.clicked.connect(self.toggleFilter)
        self.home_btn.clicked.connect(self.setHome)
        self.refresh_btn.clicked.connect(self.updateComPorts)
        self.connect_btn.clicked.connect(self.connectPort)
        self.disconnect_btn.clicked.connect(self.disconnectPort)
        self.save_btn.clicked.connect(self.saveData)
        
        # Connect motor control buttons
        self.set_torque_btn.clicked.connect(self.setTorqueLimit)
        self.set_position_btn.clicked.connect(self.setPosition)
        self.sync_position_btn.clicked.connect(self.syncPosition)
        self.set_velocity_btn.clicked.connect(self.setVelocity)
        self.sync_velocity_btn.clicked.connect(self.syncVelocity)

    def update_data(self):
        if not self.is_paused:
            try:
                # Get test data
                test_data = self.generateTestData()
                
                # Update encoder gauges with position data
                for i, motor in enumerate(['M1', 'M2', 'M3']):
                    self.encoder_gauges[i].setValue(test_data['position'][motor])
                
                # Update data buffers and UI
                for i, motor in enumerate(['M1', 'M2', 'M3']):
                    for data_type in ['position', 'speed', 'torque', 'temp', 'voltage']:
                        value = test_data[data_type][motor]
                        if self.filter_enabled:
                            value = self.apply_filter(value)
                        self.data_buffer[data_type][motor].append(value)
                        while len(self.data_buffer[data_type][motor]) > 120:
                            self.data_buffer[data_type][motor].pop(0)
                
                # Update displays and plots
                self.updateValueDisplays(test_data)
                self.updatePlots()
                
            except Exception as e:
                print(f"Error updating data: {str(e)}")

    def togglePause(self):
        self.is_paused = not self.is_paused
        self.pause_btn.setText("RESUME" if self.is_paused else "PAUSE")
        if self.is_paused:
            self.pause_btn.setStyleSheet(
                self.createStyledButton("RESUME", STYLES['BUTTON_GREEN']).styleSheet()
            )
        else:
            self.pause_btn.setStyleSheet(
                self.createStyledButton("PAUSE", STYLES['BUTTON_BLUE']).styleSheet()
            )

    def toggleFilter(self):
        self.filter_enabled = not self.filter_enabled
        self.filter_btn.setStyleSheet(
            self.createStyledButton("FILTER", 
                                  STYLES['BUTTON_GREEN'] if self.filter_enabled else STYLES['BUTTON_BLUE']).styleSheet()
        )

    def setHome(self):
        # Reset all values to zero/home position
        self.home_values = {
            'position': {'M1': 0, 'M2': 0, 'M3': 0},
            'speed': {'M1': 0, 'M2': 0, 'M3': 0},
            'torque': {'M1': 0, 'M2': 0, 'M3': 0},
            'temp': {'M1': 0, 'M2': 0, 'M3': 0},
            'voltage': {'M1': 0, 'M2': 0, 'M3': 0}
        }
        
        # Clear data buffers
        for data_type in self.data_buffer:
            for motor in self.data_buffer[data_type]:
                self.data_buffer[data_type][motor].clear()
        
        # Update displays with zero values
        self.updateValueDisplays(self.home_values)
        
        # Reset encoder gauges
        for gauge in self.encoder_gauges:
            gauge.setValue(0)
        
        # Update plots
        self.updatePlots()
        
        self.home_btn.setStyleSheet(
            self.createStyledButton("SET HOME", STYLES['BUTTON_GREEN']).styleSheet()
        )

    def refreshPort(self):
        try:
            port = self.com_box.currentText()
            if hasattr(self.parent(), 'sensor'):
                self.parent().sensor.disconnect()
            self.parent().sensor = GyroSensor(port=port)
            if self.parent().sensor.connected:
                self.connect_label.setText("CONNECTED")
                self.connect_label.setStyleSheet(f"background-color: {STYLES['CONNECTED_GREEN']}; padding: 5px;")
            else:
                self.connect_label.setText("DISCONNECTED")
                self.connect_label.setStyleSheet("background-color: red; padding: 5px;")
        except Exception as e:
            print(f"Error connecting to port: {e}")
            self.connect_label.setText("DISCONNECTED")
            self.connect_label.setStyleSheet("background-color: red; padding: 5px;")

    def stopApplication(self):
        # Stop all motors
        try:
            for i, motor in enumerate(['M1', 'M2', 'M3']):
                # Set velocity and torque to 0
                self.velocity_inputs[i].setText("0")
                self.torque_inputs[i].setText("0")
            
            # Stop data collection
            self.is_paused = True
            self.pause_btn.setText("RESUME")
            self.pause_btn.setStyleSheet(self.createStyledButton("RESUME", STYLES['BUTTON_GREEN']).styleSheet())
            
            # Update UI
            self.connect_label.setText("STOPPED")
            self.connect_label.setStyleSheet("background-color: red; padding: 5px;")
            
        except Exception as e:
            print(f"Error stopping application: {e}")

    def apply_filter(self, value, alpha=0.2):
        if not hasattr(self, '_last_values'):
            self._last_values = {}
        
        key = str(id(value))  # Create unique key for each data stream
        if key not in self._last_values:
            self._last_values[key] = value
        
        filtered = alpha * value + (1 - alpha) * self._last_values[key]
        self._last_values[key] = filtered
        return filtered

    def disconnectPort(self):
        try:
            if hasattr(self.parent(), 'sensor'):
                self.parent().sensor.disconnect()
            self.connect_label.setText("DISCONNECTED")
            self.connect_label.setStyleSheet("background-color: red; padding: 5px;")
        except Exception as e:
            print(f"Error disconnecting: {e}")

    def setTorqueLimit(self):
        try:
            for i, motor in enumerate(['M1', 'M2', 'M3']):
                torque = int(self.torque_inputs[i].text())
                if 0 <= torque <= 100:
                    print(f"Setting {motor} torque to {torque}%")
        except ValueError:
            print("Invalid torque value")

    def setPosition(self):
        try:
            for i, motor in enumerate(['M1', 'M2', 'M3']):
                position = int(self.position_inputs[i].text())
                if 0 <= position <= 300:
                    print(f"Setting {motor} position to {position}°")
        except ValueError:
            print("Invalid position value")

    def syncPosition(self):
        try:
            position = int(self.position_inputs[0].text())
            if 0 <= position <= 300:
                for motor in ['M1', 'M2', 'M3']:
                    print(f"Syncing {motor} to position {position}°")
        except ValueError:
            print("Invalid position value")

    def setVelocity(self):
        try:
            for i, motor in enumerate(['M1', 'M2', 'M3']):
                velocity = int(self.velocity_inputs[i].text())
                if 0 <= velocity <= 2047:
                    print(f"Setting {motor} velocity to {velocity}")
        except ValueError:
            print("Invalid velocity value")

    def syncVelocity(self):
        try:
            velocity = int(self.velocity_inputs[0].text())
            if 0 <= velocity <= 2047:
                for motor in ['M1', 'M2', 'M3']:
                    print(f"Syncing {motor} to velocity {velocity}")
        except ValueError:
            print("Invalid velocity value")

    def saveData(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.file_box.text()}_{timestamp}.csv"
            
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Time", "M1_Speed", "M2_Speed", "M3_Speed",
                    "M1_Torque", "M2_Torque", "M3_Torque",
                    "M1_Temp", "M2_Temp", "M3_Temp",
                    "M1_Voltage", "M2_Voltage", "M3_Voltage"
                ])
                
                data_length = len(self.data_buffer['speed']['M1'])
                for i in range(data_length):
                    row = [f"{i/20:.1f}"]  # Time
                    for data_type in ['speed', 'torque', 'temp', 'voltage']:
                        for motor in ['M1', 'M2', 'M3']:
                            row.append(f"{self.data_buffer[data_type][motor][i]:.2f}")
                    writer.writerow(row)
            print(f"Data saved to {filename}")
        except Exception as e:
            print(f"Error saving data: {e}")

    def connectPort(self):
        try:
            port = self.com_box.currentText()
            self.sensor = GyroSensor(port=port)  # Create sensor in the tab itself
            
            if self.sensor.connected:
                self.connect_label.setText("CONNECTED")
                self.connect_label.setStyleSheet(
                    f"background-color: {STYLES['CONNECTED_GREEN']}; padding: 5px; border-radius: 3px;"
                )
                self.connect_btn.setEnabled(False)
                self.disconnect_btn.setEnabled(True)
                
                # Update motor status indicators
                for status in self.motor_status:
                    status.setStyleSheet("QLabel { color: green; font-size: 24px; padding: 5px; }")
            else:
                self.showConnectionError()
        except Exception as e:
            print(f"Error connecting to port: {e}")
            self.showConnectionError()

    def showConnectionError(self):
        self.connect_label.setText("DISCONNECTED")
        self.connect_label.setStyleSheet("background-color: red; padding: 5px; border-radius: 3px;")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        
        # Update motor status indicators
        for status in self.motor_status:
            status.setStyleSheet("QLabel { color: red; font-size: 24px; padding: 5px; }")

    def setupComPortSelector(self, layout):
        com_group = QHBoxLayout()
        
        # Create combobox for COM ports instead of line edit
        self.com_box = QComboBox()
        self.updateComPorts()  # Initial port list
        self.com_box.setFixedWidth(100)
        
        self.refresh_btn = self.createStyledButton("REFRESH", STYLES['BUTTON_BLUE'])
        self.refresh_btn.clicked.connect(self.updateComPorts)
        
        self.connect_btn = self.createStyledButton("CONNECT", STYLES['BUTTON_BLUE'])
        self.connect_label = QLabel("DISCONNECTED")
        self.connect_label.setStyleSheet("background-color: red; padding: 5px; border-radius: 3px;")
        self.disconnect_btn = self.createStyledButton("DISCONNECT", STYLES['BUTTON_BLUE'])
        
        for widget in [self.com_box, self.refresh_btn, self.connect_btn, 
                      self.connect_label, self.disconnect_btn]:
            com_group.addWidget(widget)
        
        layout.addLayout(com_group)

    def updateComPorts(self):
        self.com_box.clear()
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.com_box.addItems(ports)

    def generateTestData(self):
        t = time.time()
        # Create smooth oscillating patterns
        data = {
            'position': {
                'M1': 125 + 25 * np.sin(t * 0.5),      # Oscillate between 100-150
                'M2': 195 + 25 * np.sin(t * 0.5 + 2),  # Oscillate between 170-220
                'M3': 260 + 25 * np.sin(t * 0.5 + 4)   # Oscillate between 235-285
            },
            'speed': {
                'M1': 60 + 20 * np.sin(t * 0.3),       # Oscillate between 40-80
                'M2': 60 + 20 * np.sin(t * 0.3 + 2),
                'M3': 60 + 20 * np.sin(t * 0.3 + 4)
            },
            'torque': {
                'M1': 50 + 10 * np.sin(t * 0.2),       # Oscillate between 40-60
                'M2': 50 + 10 * np.sin(t * 0.2 + 2),
                'M3': 50 + 10 * np.sin(t * 0.2 + 4)
            },
            'temp': {
                'M1': 45 + 2 * np.sin(t * 0.1),        # Oscillate between 43-47
                'M2': 45 + 2 * np.sin(t * 0.1 + 2),
                'M3': 45 + 2 * np.sin(t * 0.1 + 4)
            },
            'voltage': {
                'M1': 12 + 0.5 * np.sin(t * 0.15),     # Oscillate between 11.5-12.5
                'M2': 12 + 0.5 * np.sin(t * 0.15 + 2),
                'M3': 12 + 0.5 * np.sin(t * 0.15 + 4)
            }
        }
        return data

    def setupValueDisplays(self, layout):
        # Add real-time value displays with compact spacing
        self.value_displays = {}
        display_titles = ['Current Position', 'Current Speed', 'Current Torque', 'Current Temperature', 'Current Voltage']
        
        for row, title in enumerate(display_titles):
            label = QLabel(title)
            label.setStyleSheet(f"color: {STYLES['TEXT']}; font-weight: bold; font-size: 11px;")
            label.setFixedWidth(120)  # Fixed width for labels
            layout.addWidget(label, row+4, 0)
            
            self.value_displays[title] = []
            for col in range(3):
                display = QLabel("0.00")
                display.setStyleSheet(self.getValueLabelStyle())
                display.setFixedWidth(80)  # Fixed width for value displays
                layout.addWidget(display, row+4, col+1)
                self.value_displays[title].append(display)

    def updateValueDisplays(self, test_data):
        # Update real-time displays
        for i, motor in enumerate(['M1', 'M2', 'M3']):
            self.value_displays['Current Position'][i].setText(f"{test_data['position'][motor]:.2f}°")
            self.value_displays['Current Speed'][i].setText(f"{test_data['speed'][motor]:.2f} rpm")
            self.value_displays['Current Torque'][i].setText(f"{test_data['torque'][motor]:.2f}%")
            self.value_displays['Current Temperature'][i].setText(f"{test_data['temp'][motor]:.2f}°C")
            self.value_displays['Current Voltage'][i].setText(f"{test_data['voltage'][motor]:.2f}V")

    def getValueLabelStyle(self):
        return f"""
            QLabel {{
                background-color: {STYLES['INPUT_BG']};
                color: {STYLES['TEXT']};
                border: 1px solid {STYLES['BORDER']};
                border-radius: 3px;
                padding: 3px;
                font-size: 11px;
                qproperty-alignment: AlignCenter;
            }}
        """

    def setupEncoderGauges(self, layout):
        gauge_layout = QHBoxLayout()
        
        # Create encoder gauges
        self.encoder_gauges = []
        for i in range(3):
            gauge = CircularGauge(f"Encoder {i+1}")
            gauge.setMinimumSize(150, 150)  # Make them a bit smaller than the main encoder page
            self.encoder_gauges.append(gauge)
            gauge_layout.addWidget(gauge)
        
        layout.addLayout(gauge_layout)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Set window icon
        from PyQt5.QtGui import QIcon
        self.setWindowIcon(QIcon('logo.ico'))

        self.setWindowTitle('Gyro')
        self.setGeometry(100, 100, 1400, 900)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.motor_control_tab = MotorControlTab()
        self.artificial_horizon_tab = ArtificialHorizonTab()
        self.encoder_tab = EncoderTab()
        
        # Add tabs
        self.tab_widget.addTab(self.motor_control_tab, "Motor Control")
        self.tab_widget.addTab(self.artificial_horizon_tab, "Artificial Horizon")
        self.tab_widget.addTab(self.encoder_tab, "Encoder Display")
        
        main_layout.addWidget(self.tab_widget)
        
        # Initialize sensor and timer
        self.sensor = GyroSensor()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_all_data)
        self.timer.start(50)
        
        # Add stop flag
        self.stopped = False
        
    def update_all_data(self):
        if not self.stopped:
            try:
                self.motor_control_tab.update_data()
                self.artificial_horizon_tab.update_data()
                self.encoder_tab.update_data()
            except Exception as e:
                print(f"Error in main update loop: {e}")

    def stopApplication(self):
        self.stopped = True
        # Reset all tabs to zero
        self.motor_control_tab.setHome()
        self.artificial_horizon_tab.update_data()  # Will use zero values
        self.encoder_tab.update_data()  # Will use zero values

# Add this at the end of the file
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())
