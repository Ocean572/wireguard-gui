#!/usr/bin/env python3
"""
WireGuard GUI - PyQt6 application for managing WireGuard connections
Works on all Linux distributions
"""

import sys
import subprocess
import os
import urllib.request
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Set

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QTextEdit, QLabel,
    QMessageBox, QSplitter, QStatusBar, QDialog, QDialogButtonBox,
    QSystemTrayIcon, QMenu, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread, QSize
from PyQt6.QtGui import QIcon, QFont, QColor, QTextCursor, QPixmap


class IPFetcher(QObject):
    """Fetches public IP information asynchronously"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        try:
            # Use ip-api.com for IP and location info
            with urllib.request.urlopen("http://ip-api.com/json/", timeout=5) as response:
                data = json.loads(response.read().decode())
                self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class CommandRunner(QObject):
    """Runs commands asynchronously and emits signals with output"""
    output_received = pyqtSignal(str)
    error_received = pyqtSignal(str)
    finished = pyqtSignal(int)  # exit code
    
    def __init__(self):
        super().__init__()
        self.process = None
        
    def run_command(self, command: List[str]):
        """Run a command as current user (should be root)"""
        try:
            self.output_received.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Running: {' '.join(command)}\n")
            
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            if self.process.stdout:
                for line in self.process.stdout:
                    self.output_received.emit(line)
                
            self.process.wait()
            self.finished.emit(self.process.returncode)
            
        except Exception as e:
            self.error_received.emit(f"Error running command: {str(e)}\n")
            self.finished.emit(-1)


class WireGuardStatusMonitor(QObject):
    """Monitors WireGuard status in real-time"""
    status_updated = pyqtSignal(str)  # tunnel name
    output_received = pyqtSignal(str)
    
    def __init__(self, tunnel_name: str):
        super().__init__()
        self.tunnel_name = tunnel_name
        self.running = False
        
    def start_monitoring(self):
        """Start monitoring wg show output"""
        self.running = True
        try:
            while self.running:
                try:
                    # Check if interface exists in sysfs
                    if not os.path.exists(f"/sys/class/net/{self.tunnel_name}"):
                        break

                    result = subprocess.run(['wg', 'show', self.tunnel_name], capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        self.output_received.emit(f"[{datetime.now().strftime('%H:%M:%S')}]\n{result.stdout}")
                    
                except Exception:
                    pass
                    
                for _ in range(20):
                    if not self.running: break
                    QThread.msleep(100)
                    
        except Exception as e:
            self.output_received.emit(f"Monitoring error: {str(e)}\n")
            
    def stop_monitoring(self):
        self.running = False


class ConfigEditorDialog(QDialog):
    """Dialog for editing WireGuard configuration files"""
    
    def __init__(self, parent=None, config_name: str = "", config_content: str = ""):
        super().__init__(parent)
        self.config_name = config_name
        self.setWindowTitle(f"Edit Config: {config_name}" if config_name else "New Config")
        self.setGeometry(100, 100, 700, 500)
        
        layout = QVBoxLayout(self)
        
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Config Name:"))
        self.name_input = QTextEdit()
        self.name_input.setMaximumHeight(30)
        self.name_input.setText(config_name)
        self.name_input.setReadOnly(not not config_name == "")
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        layout.addWidget(QLabel("Config Content:"))
        self.editor = QTextEdit()
        self.editor.setFont(QFont("Monospace", 9))
        self.editor.setText(config_content)
        layout.addWidget(self.editor)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_config_name(self) -> str: return self.name_input.toPlainText().strip()
    def get_config_content(self) -> str: return self.editor.toPlainText()


class WireGuardGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.wg_dir = Path("/etc/wireguard")
        self.tunnels: List[str] = []
        self.current_tunnel: Optional[str] = None
        self.connected_tunnels: Set[str] = set()
        self.command_runner = None
        self.command_thread = None
        self.monitor_thread = None
        self.monitor = None
        self.ip_thread = None
        
        # Set icon immediately
        self.set_window_icon()
        
        self.init_ui()
        
        # Load initial data
        self.load_tunnels()
        self.update_connection_status()
        self.refresh_ip_info()
        
        # Timers
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_connection_status)
        self.status_timer.start(3000)

        self.ip_timer = QTimer()
        self.ip_timer.timeout.connect(self.refresh_ip_info)
        self.ip_timer.start(60000)
        
    def init_ui(self):
        self.setWindowTitle("WireGuard Manager (Root)")
        self.setMinimumSize(950, 650)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        left_layout = QVBoxLayout()
        
        logo_label = QLabel()
        logo_path = str(Path(__file__).parent.resolve() / "wireguard.png")
        logo_pixmap = QPixmap(logo_path)
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap.scaled(90, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            left_layout.addWidget(logo_label)
        
        ip_frame = QFrame()
        ip_frame.setFrameShape(QFrame.Shape.StyledPanel)
        ip_frame.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px;")
        ip_layout = QVBoxLayout(ip_frame)
        self.ip_label = QLabel("Public IP: Fetching...")
        self.ip_label.setFont(QFont("SansSerif", 9, QFont.Weight.Bold))
        ip_layout.addWidget(self.ip_label)
        self.location_label = QLabel("Location: ...")
        self.location_label.setFont(QFont("SansSerif", 8))
        ip_layout.addWidget(self.location_label)
        left_layout.addWidget(ip_frame)
        
        list_header = QHBoxLayout()
        list_header.addWidget(QLabel("Available Tunnels:"))
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(70)
        refresh_btn.clicked.connect(self.load_tunnels)
        list_header.addWidget(refresh_btn)
        left_layout.addLayout(list_header)
        
        self.tunnel_list = QListWidget()
        self.tunnel_list.itemClicked.connect(self.on_tunnel_selected)
        left_layout.addWidget(self.tunnel_list)
        
        config_btn_layout = QHBoxLayout()
        self.add_config_btn = QPushButton("+ New")
        self.add_config_btn.clicked.connect(self.add_new_config)
        config_btn_layout.addWidget(self.add_config_btn)
        self.edit_config_btn = QPushButton("Edit")
        self.edit_config_btn.clicked.connect(self.edit_config)
        self.edit_config_btn.setEnabled(False)
        config_btn_layout.addWidget(self.edit_config_btn)
        self.delete_config_btn = QPushButton("Delete")
        self.delete_config_btn.clicked.connect(self.delete_config)
        self.delete_config_btn.setEnabled(False)
        config_btn_layout.addWidget(self.delete_config_btn)
        left_layout.addLayout(config_btn_layout)
        
        button_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_tunnel)
        self.connect_btn.setEnabled(False)
        self.connect_btn.setMinimumHeight(45)
        self.connect_btn.setStyleSheet("font-weight: bold; background-color: #0d6efd; color: white;")
        button_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self.disconnect_tunnel)
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.setMinimumHeight(45)
        button_layout.addWidget(self.disconnect_btn)
        left_layout.addLayout(button_layout)
        
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Status Information:"))
        self.status_display = QTextEdit()
        self.status_display.setReadOnly(True)
        self.status_display.setFont(QFont("Monospace", 9))
        right_layout.addWidget(self.status_display)
        
        right_layout.addWidget(QLabel("Debug Output:"))
        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setFont(QFont("Monospace", 9))
        self.output_display.setMaximumHeight(180)
        right_layout.addWidget(self.output_display)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        lw, rw = QWidget(), QWidget()
        lw.setLayout(left_layout); rw.setLayout(right_layout)
        splitter.addWidget(lw); splitter.addWidget(rw)
        splitter.setStretchFactor(0, 1); splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter)
        
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        if os.geteuid() == 0:
            self.statusBar.showMessage("Running with Root privileges")
        else:
            self.statusBar.showMessage("Running as Normal User - Use run.sh for root")
        
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.get_icon())
        self.tray_menu = QMenu()
        self.connect_menu = QMenu("Connect", self.tray_menu)
        self.tray_menu.addMenu(self.connect_menu)
        self.tray_disconnect_action = self.tray_menu.addAction("Disconnect")
        self.tray_disconnect_action.triggered.connect(self.disconnect_tunnel)
        self.tray_menu.addSeparator()
        exit_action = self.tray_menu.addAction("Exit")
        exit_action.triggered.connect(QApplication.instance().quit)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal(); self.activateWindow()

    def update_tray_menu(self):
        self.connect_menu.clear()
        if not self.tunnels:
            self.connect_menu.addAction("No configs found").setEnabled(False)
            return
        for tunnel in self.tunnels:
            action = self.connect_menu.addAction(tunnel)
            action.triggered.connect(lambda checked, t=tunnel: self.connect_from_tray(t))
            if tunnel in self.connected_tunnels:
                action.setEnabled(False); action.setText(f"{tunnel} (Connected)")

    def connect_from_tray(self, tunnel_name):
        self.current_tunnel = tunnel_name
        for i in range(self.tunnel_list.count()):
            if self.tunnel_list.item(i).text().rstrip(' *') == tunnel_name:
                self.tunnel_list.setCurrentRow(i); break
        self.connect_tunnel()
        
    def get_icon(self) -> QIcon:
        """Helper to get icon from absolute path"""
        icon_file = Path(__file__).parent.resolve() / "wireguard.png"
        if icon_file.exists():
            return QIcon(str(icon_file))
        return QIcon()

    def set_window_icon(self):
        """Set icons for windows and application"""
        icon = self.get_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)
            QApplication.setWindowIcon(icon)
    
    def refresh_ip_info(self):
        if self.ip_thread and self.ip_thread.isRunning(): return
        self.fetcher = IPFetcher()
        self.fetcher.finished.connect(self.on_ip_fetched)
        self.ip_thread = QThread()
        self.fetcher.moveToThread(self.ip_thread)
        self.ip_thread.started.connect(self.fetcher.run)
        self.fetcher.finished.connect(self.ip_thread.quit)
        self.ip_thread.start()
        
    def on_ip_fetched(self, data):
        self.ip_label.setText(f"Public IP: {data.get('query', 'Unknown')}")
        self.location_label.setText(f"Location: {data.get('city', '')}, {data.get('country', '')}")
        
    def load_tunnels(self):
        try:
            # Check for configs - should work fine as root
            result = subprocess.run(['bash', '-c', f'ls {self.wg_dir}/*.conf 2>/dev/null'], capture_output=True, text=True)
            if result.returncode == 0:
                self.tunnels = sorted([Path(f).stem for f in result.stdout.strip().split('\n') if f])
            else:
                self.tunnels = []
            
            self.tunnel_list.clear()
            for t in self.tunnels: self.tunnel_list.addItem(t)
            self.statusBar.showMessage(f"Loaded {len(self.tunnels)} tunnel(s)")
            self.update_tray_menu(); self.update_connection_status()
            
        except Exception as e:
            self.append_output(f"Error loading tunnels: {str(e)}\n")
    
    def update_connection_status(self):
        """Monitors /sys/class/net/ for active WG interfaces (root-less)"""
        try:
            active = set()
            if os.path.exists("/sys/class/net/"):
                for iface in os.listdir("/sys/class/net/"):
                    if iface in self.tunnels: active.add(iface)
            
            # Reconcile with UI
            if active != self.connected_tunnels:
                self.connected_tunnels = active
                self.update_tray_menu()
                self.tray_disconnect_action.setEnabled(len(self.connected_tunnels) > 0)
                self.refresh_ip_info()
                
                if self.current_tunnel:
                    is_up = self.current_tunnel in self.connected_tunnels
                    self.connect_btn.setEnabled(not is_up)
                    self.disconnect_btn.setEnabled(is_up)
                
                for i in range(self.tunnel_list.count()):
                    item = self.tunnel_list.item(i)
                    item.setBackground(QColor("#d1e7dd" if item.text() in active else "white"))
        except: pass
    
    def on_tunnel_selected(self, item):
        self.current_tunnel = item.text()
        is_up = self.current_tunnel in self.connected_tunnels
        self.connect_btn.setEnabled(not is_up); self.disconnect_btn.setEnabled(is_up)
        self.edit_config_btn.setEnabled(True); self.delete_config_btn.setEnabled(True)
        self.display_tunnel_info()
    
    def display_tunnel_info(self):
        if not self.current_tunnel: return
        self.status_display.clear()
        is_up = self.current_tunnel in self.connected_tunnels
        info = f"Tunnel: {self.current_tunnel}\nStatus: {'ACTIVE' if is_up else 'INACTIVE'}\n" + "-"*30 + "\n"
        if is_up:
            try:
                res = subprocess.run(['wg', 'show', self.current_tunnel], capture_output=True, text=True, timeout=1)
                info += res.stdout if res.returncode == 0 else "Could not fetch status."
            except: info += "Could not fetch status."
        self.status_display.setText(info)
    
    def add_new_config(self):
        template = "[Interface]\nAddress = 10.0.0.2/32\nPrivateKey = <key>\n\n[Peer]\nPublicKey = <key>\nAllowedIPs = 0.0.0.0/0\nEndpoint = vpn.example.com:51820"
        dialog = ConfigEditorDialog(self, "", template)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            n, c = dialog.get_config_name(), dialog.get_config_content()
            if not n: return
            try:
                with open(f"{self.wg_dir}/{n}.conf", "w") as f: f.write(c)
                self.load_tunnels()
            except Exception as e: QMessageBox.critical(self, "Error", str(e))
    
    def edit_config(self):
        if not self.current_tunnel: return
        p = self.wg_dir / f"{self.current_tunnel}.conf"
        try:
            with open(p, "r") as f: content = f.read()
            dialog = ConfigEditorDialog(self, self.current_tunnel, content)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                with open(p, "w") as f: f.write(dialog.get_config_content())
                self.load_tunnels()
        except Exception as e: QMessageBox.critical(self, "Error", str(e))
    
    def delete_config(self):
        if not self.current_tunnel or self.current_tunnel in self.connected_tunnels: return
        if QMessageBox.question(self, "Delete", f"Delete {self.current_tunnel}?") == QMessageBox.StandardButton.Yes:
            try:
                os.remove(self.wg_dir / f"{self.current_tunnel}.conf")
                self.load_tunnels(); self.current_tunnel = None
            except Exception as e: QMessageBox.critical(self, "Error", str(e))
    
    def connect_tunnel(self):
        if not self.current_tunnel: return
        self.append_output(f"\n[{datetime.now().strftime('%H:%M:%S')}] Activating {self.current_tunnel}...\n")
        self.connect_btn.setEnabled(False); self.disconnect_btn.setEnabled(False)
        self.command_runner = CommandRunner()
        self.command_runner.output_received.connect(self.append_output)
        self.command_runner.finished.connect(self.on_connect_finished)
        self.command_thread = QThread()
        self.command_runner.moveToThread(self.command_thread)
        self.command_thread.started.connect(lambda: self.command_runner.run_command(['wg-quick', 'up', self.current_tunnel]))
        self.command_thread.start()
    
    def disconnect_tunnel(self):
        target = self.current_tunnel
        if not target or target not in self.connected_tunnels:
            if self.connected_tunnels: target = list(self.connected_tunnels)[0]
            else: return
        
        self.append_output(f"\n[{datetime.now().strftime('%H:%M:%S')}] Deactivating {target}...\n")
        self.connect_btn.setEnabled(False); self.disconnect_btn.setEnabled(False)
        if self.monitor: self.monitor.stop_monitoring(); self.monitor = None
        self.command_runner = CommandRunner()
        self.command_runner.output_received.connect(self.append_output)
        self.command_runner.finished.connect(self.on_disconnect_finished)
        self.command_thread = QThread()
        self.command_runner.moveToThread(self.command_thread)
        self.command_thread.started.connect(lambda: self.command_runner.run_command(['wg-quick', 'down', target]))
        self.command_thread.start()
    
    def on_connect_finished(self, code):
        self.update_connection_status(); self.display_tunnel_info()
        self.statusBar.showMessage("Connected" if code == 0 else "Connection Failed")
        if code == 0: self.start_monitoring()
        else: self.connect_btn.setEnabled(True)
    
    def on_disconnect_finished(self, code):
        self.update_connection_status(); self.display_tunnel_info()
        self.statusBar.showMessage("Disconnected" if code == 0 else "Deactivation Failed")
        self.connect_btn.setEnabled(True)
    
    def start_monitoring(self):
        if not self.current_tunnel or self.current_tunnel not in self.connected_tunnels: return
        if self.monitor: self.monitor.stop_monitoring()
        self.monitor = WireGuardStatusMonitor(self.current_tunnel)
        self.monitor.output_received.connect(lambda out: self.status_display.setText(out))
        self.monitor_thread = QThread()
        self.monitor.moveToThread(self.monitor_thread)
        self.monitor_thread.started.connect(self.monitor.start_monitoring)
        self.monitor_thread.start()
    
    def append_output(self, text):
        c = self.output_display.textCursor(); c.movePosition(QTextCursor.MoveOperation.End)
        c.insertText(text); self.output_display.setTextCursor(c)
        self.output_display.ensureCursorVisible()
    
    def closeEvent(self, event):
        if self.monitor: self.monitor.stop_monitoring()
        self.status_timer.stop(); self.ip_timer.stop(); event.accept()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("WireGuard Manager")
    # Link running app to the .desktop file for GNOME icon matching
    app.setDesktopFileName("wireguard-gui")
    
    window = WireGuardGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__': main()
