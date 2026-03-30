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
import time
import traceback
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

# Global Log Helper
LOG_FILE = "/tmp/wireguard-gui.log"
def log(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] GUI: {msg}\n")
    except: pass

def crash_handler(etype, value, tb):
    err = "".join(traceback.format_exception(etype, value, tb))
    log(f"CRITICAL UNHANDLED EXCEPTION:\n{err}")
    sys.__excepthook__(etype, value, tb)

sys.excepthook = crash_handler

log("--- GUI Application Starting ---")

class IPFetcher(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def run(self):
        log("IPFetcher: Run started")
        services = [
            {"url": "https://ip-api.com/json/", "format": "json"},
            {"url": "https://api.ipify.org?format=json", "format": "json"}
        ]
        for service in services:
            try:
                log(f"IPFetcher: Trying {service['url']}")
                req = urllib.request.Request(service["url"], headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    res = {"query": data.get("query") or data.get("ip"), "city": data.get("city", ""), "country": data.get("country", "")}
                    if res["query"]: 
                        log(f"IPFetcher: Success {res['query']}")
                        self.finished.emit(res); return
            except Exception as e:
                log(f"IPFetcher: Error {str(e)}")
        self.error.emit("Failed")

class CommandRunner(QObject):
    output_received = pyqtSignal(str)
    finished = pyqtSignal(int)
    
    def __init__(self, command: List[str]):
        super().__init__()
        self.command = command
        self.process = None
        
    def run(self):
        log(f"CommandRunner: Executing {' '.join(self.command)}")
        try:
            self.output_received.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Exec: {' '.join(self.command)}\n")
            self.process = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            if self.process.stdout:
                for line in self.process.stdout:
                    self.output_received.emit(line)
            return_code = self.process.wait()
            log(f"CommandRunner: Finished with code {return_code}")
            self.finished.emit(return_code)
        except Exception as e:
            log(f"CommandRunner: Exception {str(e)}")
            self.output_received.emit(f"Error: {str(e)}\n")
            self.finished.emit(-1)

class WireGuardStatusMonitor(QObject):
    output_received = pyqtSignal(str)
    
    def __init__(self, tunnel_name: str):
        super().__init__()
        self.tunnel_name = tunnel_name
        self.running = False
        
    def run(self):
        log(f"Monitor: Started for {self.tunnel_name}")
        self.running = True
        try:
            while self.running:
                if not os.path.exists(f"/sys/class/net/{self.tunnel_name}"): 
                    log(f"Monitor: Interface {self.tunnel_name} gone, exiting")
                    break
                res = subprocess.run(['wg', 'show', self.tunnel_name], capture_output=True, text=True, timeout=2)
                if res.returncode == 0:
                    self.output_received.emit(f"[{datetime.now().strftime('%H:%M:%S')}]\n{res.stdout}")
                
                # Check periodically for stop request
                for _ in range(20):
                    if not self.running: break
                    QThread.msleep(100)
        except Exception as e:
            log(f"Monitor: Exception {str(e)}")
        finally:
            log(f"Monitor: Finished for {self.tunnel_name}")
            
    def stop(self): 
        log(f"Monitor: Stop requested for {self.tunnel_name}")
        self.running = False

class WireGuardGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        log("WireGuardGUI: Init")
        self.wg_dir = Path("/etc/wireguard")
        self.tunnels: List[str] = []
        self.current_tunnel: Optional[str] = None
        self.connected_tunnels: Set[str] = set()
        
        # Thread and Worker Management
        self.ip_thread: Optional[QThread] = None
        self.ip_worker: Optional[IPFetcher] = None
        
        self.command_thread: Optional[QThread] = None
        self.command_worker: Optional[CommandRunner] = None
        
        self.monitor_thread: Optional[QThread] = None
        self.monitor_worker: Optional[WireGuardStatusMonitor] = None
        
        self.set_window_icon()
        self.init_ui()
        self.load_tunnels()
        self.update_connection_status()
        self.refresh_ip_info()
        
        # UI Update Timers
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_connection_status)
        self.status_timer.start(3000)
        
        self.ip_timer = QTimer()
        self.ip_timer.timeout.connect(self.refresh_ip_info)
        self.ip_timer.start(60000)
        
    def init_ui(self):
        log("WireGuardGUI: Building UI")
        self.setWindowTitle("WireGuard Manager (Root)")
        self.setMinimumSize(950, 650)
        
        cw = QWidget()
        self.setCentralWidget(cw)
        main_layout = QHBoxLayout(cw)
        
        left_layout = QVBoxLayout()
        
        # Logo
        logo_label = QLabel()
        logo_path = str(Path(__file__).parent.resolve() / "wireguard.png")
        pix = QPixmap(logo_path)
        if not pix.isNull():
            logo_label.setPixmap(pix.scaled(90, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            left_layout.addWidget(logo_label)
            
        # IP Info Box
        ip_frame = QFrame()
        ip_frame.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px;")
        ip_layout = QVBoxLayout(ip_frame)
        self.ip_label = QLabel("IP: Fetching...")
        self.ip_label.setFont(QFont("SansSerif", 9, QFont.Weight.Bold))
        self.location_label = QLabel("Loc: ...")
        ip_layout.addWidget(self.ip_label)
        ip_layout.addWidget(self.location_label)
        left_layout.addWidget(ip_frame)
        
        # Tunnel List
        hdr_layout = QHBoxLayout()
        hdr_layout.addWidget(QLabel("Tunnels:"))
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(70)
        refresh_btn.clicked.connect(self.load_tunnels)
        hdr_layout.addWidget(refresh_btn)
        left_layout.addLayout(hdr_layout)
        
        self.tunnel_list = QListWidget()
        self.tunnel_list.itemClicked.connect(self.on_tunnel_selected)
        left_layout.addWidget(self.tunnel_list)
        
        # Control Buttons
        btn_layout = QHBoxLayout()
        self.conn_btn = QPushButton("Connect")
        self.conn_btn.setEnabled(False)
        self.conn_btn.setMinimumHeight(45)
        self.conn_btn.setStyleSheet("font-weight: bold; background-color: #0d6efd; color: white;")
        self.conn_btn.clicked.connect(self.connect_tunnel)
        
        self.disc_btn = QPushButton("Disconnect")
        self.disc_btn.setEnabled(False)
        self.disc_btn.setMinimumHeight(45)
        self.disc_btn.clicked.connect(self.disconnect_tunnel)
        
        btn_layout.addWidget(self.conn_btn)
        btn_layout.addWidget(self.disc_btn)
        left_layout.addLayout(btn_layout)
        
        # Right Panel
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Status:"))
        self.status_disp = QTextEdit()
        self.status_disp.setReadOnly(True)
        self.status_disp.setFont(QFont("Monospace", 9))
        right_layout.addWidget(self.status_disp)
        
        right_layout.addWidget(QLabel("Debug Output:"))
        self.output_disp = QTextEdit()
        self.output_disp.setReadOnly(True)
        self.output_disp.setFont(QFont("Monospace", 9))
        self.output_disp.setMaximumHeight(180)
        right_layout.addWidget(self.output_disp)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        lw = QWidget(); lw.setLayout(left_layout)
        rw = QWidget(); rw.setLayout(right_layout)
        splitter.addWidget(lw)
        splitter.addWidget(rw)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter)
        
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        # Tray Icon
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.get_icon())
        tm = QMenu()
        ex = tm.addAction("Exit")
        ex.triggered.connect(QApplication.instance().quit)
        self.tray.setContextMenu(tm)
        self.tray.show()

    def get_icon(self) -> QIcon:
        p = Path(__file__).parent.resolve() / "wireguard.png"
        return QIcon(str(p)) if p.exists() else QIcon()

    def set_window_icon(self):
        ic = self.get_icon()
        if not ic.isNull():
            self.setWindowIcon(ic)
            QApplication.setWindowIcon(ic)
            
    def refresh_ip_info(self):
        if self.ip_thread and self.ip_thread.isRunning():
            return
            
        log("WireGuardGUI: Refreshing IP info")
        self.ip_label.setText("IP: Fetching...")
        
        self.ip_worker = IPFetcher()
        self.ip_thread = QThread()
        self.ip_worker.moveToThread(self.ip_thread)
        
        self.ip_thread.started.connect(self.ip_worker.run)
        self.ip_worker.finished.connect(self.on_ip_fetched)
        self.ip_worker.error.connect(self.on_ip_error)
        
        self.ip_worker.finished.connect(self.ip_thread.quit)
        self.ip_worker.error.connect(self.ip_thread.quit)
        
        # cleanup reference when finished to avoid RuntimeError
        self.ip_thread.finished.connect(self._cleanup_ip_thread)
        self.ip_thread.start()
        
    def _cleanup_ip_thread(self):
        log("WireGuardGUI: IP thread finished")
        if self.ip_thread:
            self.ip_thread.deleteLater()
            self.ip_thread = None
        self.ip_worker = None
        
    def on_ip_fetched(self, d):
        log(f"WireGuardGUI: IP info received: {d['query']}")
        self.ip_label.setText(f"IP: {d.get('query', 'Unknown')}")
        c, ct = d.get('city', ''), d.get('country', '')
        self.location_label.setText(f"Loc: {c}, {ct}" if c or ct else "Loc: Unknown")
        
    def on_ip_error(self, e):
        log(f"WireGuardGUI: IP fetch error: {e}")
        self.ip_label.setText("IP: Error")
        
    def load_tunnels(self):
        log("WireGuardGUI: Loading tunnels")
        try:
            res = subprocess.run(['bash', '-c', f'ls {self.wg_dir}/*.conf 2>/dev/null'], capture_output=True, text=True)
            self.tunnels = sorted([Path(f).stem for f in res.stdout.strip().split('\n') if f])
            self.tunnel_list.clear()
            for t in self.tunnels:
                self.tunnel_list.addItem(t)
            log(f"WireGuardGUI: Found {len(self.tunnels)} tunnels")
        except Exception as e:
            log(f"WireGuardGUI: Load error: {str(e)}")
            
    def update_connection_status(self):
        try:
            active = set()
            if os.path.exists("/sys/class/net/"):
                for iface in os.listdir("/sys/class/net/"):
                    if iface in self.tunnels:
                        active.add(iface)
            
            if active != self.connected_tunnels:
                log(f"WireGuardGUI: Active interfaces changed: {active}")
                self.connected_tunnels = active
                self.refresh_ip_info()
                
                if self.current_tunnel:
                    is_up = self.current_tunnel in active
                    self.conn_btn.setEnabled(not is_up)
                    self.disc_btn.setEnabled(is_up)
                    
                for i in range(self.tunnel_list.count()):
                    item = self.tunnel_list.item(i)
                    if item.text() in active:
                        item.setBackground(QColor("#d1e7dd"))
                    else:
                        item.setBackground(QColor("white"))
        except Exception as e:
            log(f"WireGuardGUI: Status update error: {str(e)}")
            
    def on_tunnel_selected(self, item):
        self.current_tunnel = item.text()
        log(f"WireGuardGUI: Tunnel selected: {self.current_tunnel}")
        is_up = self.current_tunnel in self.connected_tunnels
        self.conn_btn.setEnabled(not is_up)
        self.disc_btn.setEnabled(is_up)
        self.display_tunnel_info()
        
    def display_tunnel_info(self):
        if not self.current_tunnel: return
        self.status_disp.clear()
        is_up = self.current_tunnel in self.connected_tunnels
        info = f"Tunnel: {self.current_tunnel}\nStatus: {'ACTIVE' if is_up else 'INACTIVE'}\n" + "-"*30 + "\n"
        if is_up:
            try:
                res = subprocess.run(['wg', 'show', self.current_tunnel], capture_output=True, text=True, timeout=1)
                if res.returncode == 0:
                    info += res.stdout
            except: pass
        self.status_disp.setText(info)

    def connect_tunnel(self):
        if not self.current_tunnel: return
        if self.command_thread and self.command_thread.isRunning():
            log("WireGuardGUI: Command already running")
            return
            
        log(f"WireGuardGUI: Connect requested for {self.current_tunnel}")
        self.conn_btn.setEnabled(False)
        self.disc_btn.setEnabled(False)
        self.append_output(f"\nActivating {self.current_tunnel}...\n")
        
        self.command_worker = CommandRunner(['wg-quick', 'up', self.current_tunnel])
        self.command_thread = QThread()
        self.command_worker.moveToThread(self.command_thread)
        
        self.command_thread.started.connect(self.command_worker.run)
        self.command_worker.output_received.connect(self.append_output)
        self.command_worker.finished.connect(self.on_connect_finished)
        self.command_worker.finished.connect(self.command_thread.quit)
        
        self.command_thread.finished.connect(self._cleanup_command_thread)
        self.command_thread.start()
        
    def _cleanup_command_thread(self):
        log("WireGuardGUI: Command thread finished")
        if self.command_thread:
            self.command_thread.deleteLater()
            self.command_thread = None
        self.command_worker = None
        # Trigger UI update
        self.update_connection_status()
        self.display_tunnel_info()
        
    def on_connect_finished(self, code):
        log(f"WireGuardGUI: Connect finished with code {code}")
        if code == 0:
            self.start_monitoring()
        else:
            self.conn_btn.setEnabled(True)
            self.disc_btn.setEnabled(False)
            
    def disconnect_tunnel(self):
        target = self.current_tunnel
        if not target or target not in self.connected_tunnels:
            if self.connected_tunnels:
                target = list(self.connected_tunnels)[0]
            else:
                return
                
        if self.command_thread and self.command_thread.isRunning():
            log("WireGuardGUI: Command already running")
            return
            
        log(f"WireGuardGUI: Disconnect requested for {target}")
        self.conn_btn.setEnabled(False)
        self.disc_btn.setEnabled(False)
        self.append_output(f"\nDeactivating {target}...\n")
        
        if self.monitor_worker:
            log("WireGuardGUI: Stopping monitor before disconnect")
            self.monitor_worker.stop()
            
        # Give the monitor a moment to stop before running wg-quick down
        QTimer.singleShot(1000, lambda: self._do_disconnect(target))

    def _do_disconnect(self, target):
        log(f"WireGuardGUI: _do_disconnect for {target}")
        
        self.command_worker = CommandRunner(['wg-quick', 'down', target])
        self.command_thread = QThread()
        self.command_worker.moveToThread(self.command_thread)
        
        self.command_thread.started.connect(self.command_worker.run)
        self.command_worker.output_received.connect(self.append_output)
        self.command_worker.finished.connect(self.on_disconnect_finished)
        self.command_worker.finished.connect(self.command_thread.quit)
        
        self.command_thread.finished.connect(self._cleanup_command_thread)
        self.command_thread.start()
        
    def on_disconnect_finished(self, code):
        log(f"WireGuardGUI: Disconnect finished with code {code}")
        # UI update is handled by _cleanup_command_thread
        
    def start_monitoring(self):
        if not self.current_tunnel or self.current_tunnel not in self.connected_tunnels:
            return
            
        if self.monitor_thread and self.monitor_thread.isRunning():
            log("WireGuardGUI: Monitor already running, stopping first")
            self.monitor_worker.stop()
            self.monitor_thread.quit()
            self.monitor_thread.wait(1000)
            
        log(f"WireGuardGUI: Starting status monitor for {self.current_tunnel}")
        self.monitor_worker = WireGuardStatusMonitor(self.current_tunnel)
        self.monitor_thread = QThread()
        self.monitor_worker.moveToThread(self.monitor_thread)
        
        self.monitor_thread.started.connect(self.monitor_worker.run)
        self.monitor_worker.output_received.connect(lambda out: self.status_disp.setText(out))
        
        self.monitor_thread.finished.connect(self._cleanup_monitor_thread)
        self.monitor_thread.start()
        
    def _cleanup_monitor_thread(self):
        log("WireGuardGUI: Monitor thread finished")
        if self.monitor_thread:
            self.monitor_thread.deleteLater()
            self.monitor_thread = None
        self.monitor_worker = None
        
    def append_output(self, text):
        c = self.output_disp.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        c.insertText(text)
        self.output_disp.setTextCursor(c)
        self.output_disp.ensureCursorVisible()
        
    def closeEvent(self, event):
        log("WireGuardGUI: closeEvent received")
        self.status_timer.stop()
        self.ip_timer.stop()
        
        if self.monitor_worker:
            self.monitor_worker.stop()
        if self.monitor_thread:
            self.monitor_thread.quit()
            self.monitor_thread.wait(1000)
            
        if self.command_thread:
            self.command_thread.quit()
            self.command_thread.wait(1000)
            
        if self.ip_thread:
            self.ip_thread.quit()
            self.ip_thread.wait(1000)
            
        event.accept()

def main():
    log("WireGuardGUI: main() start")
    app = QApplication(sys.argv)
    app.setApplicationName("WireGuard Manager")
    app.setDesktopFileName("wireguard-manager")
    window = WireGuardGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__': main()
