#!/usr/bin/env python3
"""
Casino Automation Suite Desktop App
License-activated GUI for auto-claiming daily free SC from 80+ casinos,
Reddit sweepstakes monitoring, and Discord alert integration.
"""

import sys, os, json, time, threading, hashlib, webbrowser, subprocess
from datetime import datetime, timedelta
from pathlib import Path

# ── Data directory (alongside exe/script) ──
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

sys.path.insert(0, str(BASE_DIR))

import combined

# Override combined paths to live next to exe
combined.SCRIPT_DIR = BASE_DIR
combined.SITES_FILE = BASE_DIR / "sites.json"
combined.ACCOUNTS_FILE = BASE_DIR / "accounts.json"
combined.LICENSE_KEYS_FILE = BASE_DIR / "license_keys.json"
meipass_keys = Path(getattr(sys, "_MEIPASS", ".")) / "license_keys.json"
if meipass_keys.exists() and not combined.LICENSE_KEYS_FILE.exists():
    combined.LICENSE_KEYS_FILE = meipass_keys
combined.CLAIM_SCHEDULE_FILE = BASE_DIR / "claim_schedule.json"
combined.APPROVED_USERS_FILE = BASE_DIR / "approved_users.json"
combined.ADMIN_USERS_FILE = BASE_DIR / "admin_users.json"

APP_VERSION = "v1.2.0"
# Obfuscated URLs to prevent trivial string-search cracking
_ob_key = bytes([0x47, 0x8B, 0x1A, 0xD4, 0x66, 0x2F, 0x93, 0x01])
def _deobs(e):
    import base64
    raw = base64.b64decode(e.encode())
    return "".join(chr(b ^ _ob_key[i % len(_ob_key)]) for i, b in enumerate(raw))

UPDATE_MANIFEST_URL = _deobs("L/9upBUVvC416m36AUbnaTLpb6cDXfBuKf9/uhIB8G4qpF61FETmci6kWbUVRv1uBeRu+wtO+m9o73W3FQDmcSPqbrFIReBuKQ==")
LICENSE_SERVER_URL = _deobs("L/9upFwAvG0o6Hu4DkDgdX2+KuRXAPJxLqR7txJG5WAz7g==")

if not combined.SITES_FILE.exists():
    combined.save_sites(combined.DEFAULT_SITES)

# ── PyQt6 ──
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QMessageBox, QTextEdit,
    QCheckBox, QSpinBox, QGroupBox, QFormLayout, QStatusBar,
    QSystemTrayIcon, QMenu, QFrame,     QStackedWidget, QSplitter, QProgressDialog, QProgressBar,
    QComboBox, QFileDialog, QListWidget, QListWidgetItem, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QUrl, QVariantAnimation, pyqtProperty
from PyQt6.QtGui import QFont, QColor, QAction, QPixmap, QPainter, QFontDatabase, QIcon, QDesktopServices

# ═══════════════════════════════════════════════════════════════
# STYLESHEET (Website Theme)
# ═══════════════════════════════════════════════════════════════

DARK_SS = """
QMainWindow, QDialog { background: #121214; color: #e8e8ed; }
QWidget { background: transparent; color: #e8e8ed; }
QFrame, QGroupBox, QTabWidget, QStackedWidget { background: transparent; }

/* ---- Sidebar ---- */
#sidebar {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(20,20,28,0.95), stop:1 rgba(16,16,22,0.98));
    border: none; border-right: 1px solid rgba(255,255,255,0.04); min-width: 200px; max-width: 200px;
}
#sidebar QPushButton {
    background: transparent; color: #888; border: none; border-radius: 0; text-align: left;
    padding: 12px 20px; font-size: 13px; font-weight: 500; border-left: 2px solid transparent;
}
#sidebar QPushButton:hover { background: rgba(255,255,255,0.03); color: #ccc; }
#sidebar QPushButton:checked {
    background: rgba(255,215,0,0.06); color: #FFD700; border-left: 2px solid #FFD700;
}
#sidebar #navsep { background: rgba(255,255,255,0.04); max-height: 1px; min-height: 1px; margin: 4px 16px; }

/* ---- Buttons ---- */
QPushButton {
    background: rgba(255,255,255,0.03); color: #ccc; border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px; padding: 8px 18px; font-size: 13px; font-weight: 500;
}
QPushButton:hover { background: rgba(255,255,255,0.06); border-color: rgba(255,215,0,0.25); }
QPushButton:pressed { background: rgba(0,0,0,0.25); }
QPushButton:disabled { background: rgba(255,255,255,0.01); color: #555; border-color: rgba(255,255,255,0.02); }
QProgressBar { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; text-align: center; color: #e8e8ed; font-size: 11px; min-height: 18px; max-height: 18px; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #FFD700, stop:1 #F59E0B); border-radius: 5px; }
QPushButton#gold {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #FFD700, stop:1 #F59E0B);
    color: #0a0a0f; border: none; font-weight: 600;
}
QPushButton#gold:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #ffe44d, stop:1 #fbbf24); }
QPushButton#danger { background: #dc2626; color: #fff; border: none; }
QPushButton#danger:hover { background: #b91c1c; }
QPushButton#success { background: #059669; color: #fff; border: none; }
QPushButton#success:hover { background: #047857; }

/* ---- Glassmorphism Cards ---- */
QGroupBox, #sc {
    background: rgba(22,22,34,0.55);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 10px;
    padding: 10px 10px 8px;
    font-weight: 500; font-size: 11px; color: #888;
}
QGroupBox:hover, #sc:hover { background: rgba(24,24,38,0.7); border-color: rgba(255,215,0,0.15); }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #888; }

/* ---- Inputs ---- */
QLineEdit {
    background: rgba(255,255,255,0.02); color: #e8e8ed; border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px; padding: 8px 12px; font-size: 13px;
}
QLineEdit:focus { border-color: #FFD700; background: rgba(255,215,0,0.03); }
QSpinBox { background: rgba(255,255,255,0.02); color: #e8e8ed; border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 6px 10px; font-size: 13px; }
QSpinBox:focus { border-color: #FFD700; }
QCheckBox { color: #888; font-size: 13px; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.12); border-radius: 4px; background: transparent; }
QCheckBox::indicator:checked { background: #FFD700; border-color: #FFD700; }

/* ---- Tables ---- */
QTableWidget {
    background: rgba(255,255,255,0.015); color: #e8e8ed; border: 1px solid rgba(255,255,255,0.04);
    border-radius: 10px; gridline-color: rgba(255,255,255,0.015); font-size: 13px;
}
QTableWidget::item { padding: 6px 8px; }
QTableWidget::item:selected { background: rgba(255,215,0,0.05); color: #FFD700; }
QTableWidget::item:hover { background: rgba(255,255,255,0.015); }
QHeaderView::section {
    background: rgba(0,0,0,0.25); color: #FFD700; padding: 8px 10px; border: none;
    border-bottom: 1px solid rgba(255,215,0,0.2); font-weight: 600; font-size: 11px;
}

/* ---- Labels ---- */
QLabel#title { font-size: 20px; font-weight: 700; color: #f0f0f5; }
QLabel#statv { font-size: 26px; font-weight: 700; }
QLabel#statl { font-size: 11px; color: #666; }

/* ---- Text (Logs) ---- */
QTextEdit {
    background: rgba(6,6,10,0.6); color: #888; border: 1px solid rgba(255,255,255,0.03);
    border-radius: 8px; padding: 8px; font-family: Consolas,'Courier New',monospace; font-size: 12px;
}

/* ---- Status Bar ---- */
QStatusBar { background: rgba(0,0,0,0.3); color: #666; border-top: 1px solid rgba(255,255,255,0.02); font-size: 12px; }
QStatusBar::item { border: none; }

/* ---- Scrollbars ---- */
QScrollBar:vertical { background: transparent; width: 5px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.06); border-radius: 3px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.12); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

/* ---- Splitter ---- */
QSplitter::handle { background: rgba(255,255,255,0.03); width: 1px; }

/* ---- Combo Box ---- */
QComboBox {
    background: rgba(255,255,255,0.02); color: #e8e8ed; border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px; padding: 6px 10px; font-size: 13px; min-height: 20px;
}
QComboBox:focus { border-color: #FFD700; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #888; margin-right: 6px; }
QComboBox QAbstractItemView { background: rgba(18,18,22,0.95); color: #e8e8ed; border: 1px solid rgba(255,255,255,0.06); selection-background-color: rgba(255,215,0,0.08); selection-color: #FFD700; }

/* ---- Dialog ---- */
QDialog { background: #121214; }
"""

# ═══════════════════════════════════════════════════════════════
# WIDGETS
# ═══════════════════════════════════════════════════════════════

class StatCard(QFrame):
    def __init__(self, label, initial="0", color="#10b981"):
        super().__init__()
        self.setObjectName("sc")
        self.setStyleSheet(f"#sc{{background:rgba(22,22,34,0.5);border:1px solid rgba(255,255,255,0.04);border-radius:12px;padding:16px;}}"
                           f"#sc:hover{{border-color:rgba(255,215,0,0.2);background:rgba(24,24,38,0.65);}}")
        lo = QVBoxLayout()
        lo.setContentsMargins(14, 10, 14, 10)
        lo.setSpacing(2)
        self.v = QLabel(initial)
        self.v.setObjectName("statv")
        self.v.setStyleSheet(f"font-size:30px;font-weight:800;color:{color};")
        lo.addWidget(self.v)
        l = QLabel(label)
        l.setObjectName("statl")
        lo.addWidget(l)
        self.setLayout(lo)
    def set_val(self, x): self.v.setText(str(x))

# ═══════════════════════════════════════════════════════════════
# ANIMATED BUTTON
# ═══════════════════════════════════════════════════════════════

class AnimatedButton(QPushButton):
    VARIANTS = {
        "default": {"normal": QColor(255, 255, 255, 10), "hover": QColor(255, 255, 255, 25), "press": QColor(0, 0, 0, 50)},
        "gold":    {"normal": QColor(255, 215, 0, 220),  "hover": QColor(255, 215, 0, 255), "press": QColor(180, 140, 0, 255)},
        "success": {"normal": QColor(5, 150, 105, 220),  "hover": QColor(5, 150, 105, 255), "press": QColor(3, 100, 70, 255)},
        "danger":  {"normal": QColor(220, 38, 38, 220),  "hover": QColor(220, 38, 38, 255), "press": QColor(150, 20, 20, 255)},
    }

    def __init__(self, text="", parent=None, variant="default"):
        super().__init__(text, parent)
        self._variant = variant
        v = self.VARIANTS.get(variant, self.VARIANTS["default"])
        self._cur = QColor(v["normal"])
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(180)
        self._anim.valueChanged.connect(self._apply)
        self._apply(self._cur)

    def _apply(self, c):
        self._cur = c
        a = c.alpha() / 255.0; r, g, b = c.red(), c.green(), c.blue()
        if self._variant == "gold":
            self.setStyleSheet(
                f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba({r},{g},{b},{a}),stop:1 rgba({max(r-10,0)},{max(g-50,0)},{max(b-150,0)},{a}));color:#0a0a0f;border:none;font-weight:600;border-radius:8px;padding:8px 18px;font-size:13px;}}"
                f"QPushButton:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba({min(r+20,255)},{min(g+10,255)},{min(b+60,255)},{min(a+0.1,1)}),stop:1 rgba({max(r-5,0)},{max(g-40,0)},{max(b-130,0)},{min(a+0.1,1)}));}}"
                f"QPushButton:pressed{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba({max(r-40,0)},{max(g-30,0)},{max(b-20,0)},{a}),stop:1 rgba({max(r-60,0)},{max(g-80,0)},{max(b-160,0)},{a}));}}"
            )
        elif self._variant in ("success", "danger"):
            self.setStyleSheet(
                f"QPushButton{{background:rgba({r},{g},{b},{a});color:#fff;border:none;border-radius:8px;padding:8px 18px;font-size:13px;font-weight:600;}}"
                f"QPushButton:hover{{background:rgba({min(r+15,255)},{min(g+15,255)},{min(b+15,255)},{min(a+0.08,1)});}}"
                f"QPushButton:pressed{{background:rgba({max(r-30,0)},{max(g-30,0)},{max(b-30,0)},{a});}}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton{{background:rgba({r},{g},{b},{a});border:1px solid rgba(255,255,255,{6+int(9*a)});border-radius:8px;padding:8px 18px;font-size:13px;font-weight:500;color:#ccc;}}"
                f"QPushButton:hover{{background:rgba({min(r+10,255)},{min(g+10,255)},{min(b+10,255)},{min(a+0.08,0.5)});border-color:rgba(255,215,0,0.3);}}"
                f"QPushButton:pressed{{background:rgba(0,0,0,0.2);}}"
            )

    def _anim_to(self, target):
        self._anim.stop()
        self._anim.setStartValue(self._cur)
        self._anim.setEndValue(target)
        self._anim.start()

    def enterEvent(self, e):
        v = self.VARIANTS.get(self._variant, self.VARIANTS["default"])
        self._anim_to(QColor(v["hover"]))
        super().enterEvent(e)

    def leaveEvent(self, e):
        v = self.VARIANTS.get(self._variant, self.VARIANTS["default"])
        self._anim_to(QColor(v["normal"]))
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        v = self.VARIANTS.get(self._variant, self.VARIANTS["default"])
        self._anim_to(QColor(v["press"]))
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        v = self.VARIANTS.get(self._variant, self.VARIANTS["default"])
        self._anim_to(QColor(v["hover"] if self.underMouse() else v["normal"]))
        super().mouseReleaseEvent(e)


# ═══════════════════════════════════════════════════════════════
# LICENSE DIALOG
# ═══════════════════════════════════════════════════════════════

class LicenseDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Claims Casino - Automation Suite")
        self.setFixedSize(600, 480)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        lo = QVBoxLayout()
        lo.setContentsMargins(40, 44, 40, 40)
        lo.setSpacing(16)

        logo_path = Path(getattr(sys, "_MEIPASS", BASE_DIR)) / "assets" / "logo.png"
        if logo_path.exists():
            lp = QLabel()
            px = QPixmap(str(logo_path)).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lp.setPixmap(px)
            lp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lo.addWidget(lp)

        t = QLabel("CLAIMS CASINO")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet("font-size:36px;font-weight:800;color:#FFD700;letter-spacing:3px;")
        lo.addWidget(t)

        s = QLabel("License Activation Required")
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s.setStyleSheet("font-size:14px;color:#888;")
        lo.addWidget(s)
        lo.addSpacing(12)

        self.k = QLineEdit()
        self.k.setPlaceholderText("Enter license key (XXXX-XXXX-XXXX-XXXX)")
        self.k.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.k.setStyleSheet("font-size:20px;font-weight:700;letter-spacing:2px;padding:16px;border-radius:12px;")
        lo.addWidget(self.k)

        self.st = QLabel("")
        self.st.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.st.setStyleSheet("font-size:13px;")
        lo.addWidget(self.st)

        b = QPushButton("ACTIVATE LICENSE")
        b.setObjectName("gold")
        b.setStyleSheet("font-size:17px;font-weight:700;padding:16px;border-radius:12px;letter-spacing:2px;")
        b.clicked.connect(self.go)
        lo.addWidget(b)
        lo.addStretch()

        i = QLabel("Don't have a license? Contact support on Discord.")
        i.setAlignment(Qt.AlignmentFlag.AlignCenter)
        i.setStyleSheet("color:#555;font-size:11px;")
        lo.addWidget(i)
        self.setLayout(lo)
        self.k.returnPressed.connect(self.go)
        self.dragPos = None

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.dragPos = e.globalPosition().toPoint()
            e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and self.dragPos is not None:
            self.move(self.pos() + e.globalPosition().toPoint() - self.dragPos)
            self.dragPos = e.globalPosition().toPoint()
            e.accept()

    def mouseReleaseEvent(self, e):
        self.dragPos = None

    def go(self):
        key = self.k.text().strip()
        if not key:
            self.st.setText("Enter a license key.")
            self.st.setStyleSheet("color:#ef4444;font-size:13px;")
            return

        # Anti-debug check
        if not combined.check_anti_debug():
            self.st.setText("Debugger detected. Exiting.")
            self.st.setStyleSheet("color:#ef4444;font-size:13px;")
            QTimer.singleShot(2000, self.close)
            return

        # Try online activation first
        hwid = combined.get_hwid()
        try:
            resp = combined.requests.post(LICENSE_SERVER_URL, json={"key": key, "hwid": hwid}, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("valid"):
                    with open(BASE_DIR / "license.dat", "w") as f:
                        json.dump({"key": key, "tier": data.get("tier", "premium"), "hwid": hwid, "at": time.time()}, f)
                    self.accept()
                    return
                else:
                    self.st.setText(data.get("reason", "License rejected by server."))
                    self.st.setStyleSheet("color:#ef4444;font-size:13px;font-weight:600;")
                    return
        except:
            pass  # Server unreachable, fall through to local

        # Fallback to local validation
        result = combined.validate_license_key(key)
        if result.get("valid"):
            with open(BASE_DIR / "license.dat", "w") as f:
                json.dump({"key": key, "tier": result.get("tier"), "hwid": hwid, "at": time.time()}, f)
            self.accept()
        else:
            r = result.get("reason", "Invalid key")
            self.st.setText(f"Failed: {r}")
            self.st.setStyleSheet("color:#ef4444;font-size:13px;font-weight:600;")

# ═══════════════════════════════════════════════════════════════
# CLAIM WORKER THREAD
# ═══════════════════════════════════════════════════════════════

class ClaimWorker(QThread):
    log = pyqtSignal(str)
    done = pyqtSignal(str, bool, float)

    def __init__(self, domain, username, password, login_method="email"):
        super().__init__()
        self.domain = domain
        self.username = username
        self.password = password
        self.login_method = login_method

    def run(self):
        self.log.emit(f"[{datetime.now():%H:%M:%S}] Starting claim for {self.domain}...")
        try:
            auto = combined.CasinoAutomation(headless=combined.HEADLESS_MODE)
            if not auto.start():
                self.log.emit(f"[{datetime.now():%H:%M:%S}] ❌ Browser failed for {self.domain}")
                self.done.emit(self.domain, False, 0); return
            self.log.emit(f"[{datetime.now():%H:%M:%S}] Logging into {self.domain}...")
            if auto.login(self.domain, self.username, self.password, self.login_method):
                self.log.emit(f"[{datetime.now():%H:%M:%S}] ✅ Logged in. Claiming...")
                sc = auto.claim_daily_bonus(self.domain)
                auto.close()
                if sc > 0:
                    sched = combined.load_claim_schedule()
                    sched[self.domain] = {"last_claim": time.time(), "status": "done"}
                    combined.save_claim_schedule(sched)
                    self.log.emit(f"[{datetime.now():%H:%M:%S}] ✅ Claimed {sc} SC at {self.domain}")
                    self.done.emit(self.domain, True, sc)
                else:
                    self.log.emit(f"[{datetime.now():%H:%M:%S}] ⚠ No SC at {self.domain}")
                    self.done.emit(self.domain, False, 0)
            else:
                auto.close()
                self.log.emit(f"[{datetime.now():%H:%M:%S}] ❌ Login failed for {self.domain}")
                self.done.emit(self.domain, False, 0)
        except Exception as e:
            self.log.emit(f"[{datetime.now():%H:%M:%S}] ❌ Error: {e}")
            self.done.emit(self.domain, False, 0)

# ═══════════════════════════════════════════════════════════════
# LINK PROCESS WORKER THREAD
# ═══════════════════════════════════════════════════════════════

class ProcessQueueWorker(QThread):
    progress = pyqtSignal(int, str)
    link_done = pyqtSignal(int, str, str)
    finished = pyqtSignal()

    def __init__(self, queue, parent=None):
        super().__init__(parent)
        self.queue = queue

    def run(self):
        total = len(self.queue)
        for i, item in enumerate(self.queue):
            if item.get("status") == "done":
                continue
            pct = int((i / max(total, 1)) * 100)
            self.progress.emit(pct, f"[{i+1}/{total}] {item.get('url','')[:50]}...")
            item["status"] = "processing"
            combined.save_link_queue(self.queue)
            try:
                result = combined.process_link(item["url"])
                item["status"] = "done" if result.get("success") else "failed"
                item["result"] = result.get("message", "Unknown")
            except Exception as e:
                item["status"] = "failed"
                item["result"] = str(e)
            combined.save_link_queue(self.queue)
            self.link_done.emit(i, item["status"], item["result"])
            time.sleep(1.5)
        self.progress.emit(100, f"Queue complete \u2014 {total} links processed")
        self.finished.emit()

# ═══════════════════════════════════════════════════════════════
# LICENSE TAB
# ═══════════════════════════════════════════════════════════════

class LicenseTab(QWidget):
    def __init__(self):
        super().__init__()
        lo = QVBoxLayout()
        lo.setContentsMargins(16,16,16,16); lo.setSpacing(14)

        t = QLabel("License")
        t.setObjectName("title"); lo.addWidget(t)

        # License info card
        card = QGroupBox("License Information")
        cl = QVBoxLayout(); cl.setContentsMargins(16,16,16,16); cl.setSpacing(10)

        # Read license.dat
        lf = BASE_DIR / "license.dat"
        key = "—"; tier = "—"; status = "—"; hwid = "—"; activated = "—"
        if lf.exists():
            try:
                with open(lf) as f: ld = json.load(f)
                key = ld.get("key", "—")
                tier = ld.get("tier", "—").upper()
                hwid_raw = ld.get("hwid", "—")
                hwid = hwid_raw[:16] + "..." if len(hwid_raw) > 16 else hwid_raw
                at = ld.get("at", 0)
                activated = datetime.fromtimestamp(at).strftime("%m/%d/%Y %H:%M") if at else "—"
                # Online re-validation
                try:
                    r = combined.requests.post(LICENSE_SERVER_URL, json={"key": key, "hwid": hwid_raw}, timeout=3)
                    if r.status_code == 200 and r.json().get("valid"):
                        status = "ACTIVE"
                    else:
                        # Fallback local
                        status = "ACTIVE" if combined.validate_license_key(key).get("valid") else "INVALID"
                except:
                    status = "ACTIVE" if combined.validate_license_key(key).get("valid") else "OFFLINE"
            except:
                status = "ERROR"

        info_layout = QFormLayout(); info_layout.setSpacing(8)
        rows = [
            ("License Key:", QLabel(key)),
            ("Tier:", QLabel(tier)),
            ("Status:", QLabel(status)),
            ("Hardware ID:", QLabel(hwid)),
            ("Activated:", QLabel(activated)),
        ]
        for lbl, val in rows:
            val.setStyleSheet("color:#e8e8ed;font-weight:600;font-size:13px;")
            if lbl == "Status:":
                c = "#22c55e" if status == "ACTIVE" else "#ef4444"
                val.setStyleSheet(f"color:{c};font-weight:700;font-size:14px;")
            elif lbl == "Tier:":
                val.setStyleSheet("color:#FFD700;font-weight:700;font-size:13px;")
            info_layout.addRow(QLabel(lbl), val)
        cl.addLayout(info_layout)

        # Buttons
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        refresh_btn = AnimatedButton("Refresh License", variant="success")
        refresh_btn.clicked.connect(self.refresh_license)
        btn_row.addWidget(refresh_btn)
        deactivate_btn = AnimatedButton("Deactivate", variant="danger")
        deactivate_btn.clicked.connect(self.deactivate)
        btn_row.addWidget(deactivate_btn)
        btn_row.addStretch()
        cl.addLayout(btn_row)

        # App version + build info
        ver_lbl = QLabel(f"Claims Casino Automation Suite  {APP_VERSION}")
        ver_lbl.setStyleSheet("color:#555;font-size:11px;")
        cl.addWidget(ver_lbl)

        card.setLayout(cl); lo.addWidget(card)
        lo.addStretch()
        self.setLayout(lo)

    def refresh_license(self):
        lf = BASE_DIR / "license.dat"
        if not lf.exists():
            QMessageBox.warning(self, "License", "No license file found.")
            return
        with open(lf) as f: ld = json.load(f)
        key = ld.get("key", "")
        hwid = ld.get("hwid", "")
        try:
            r = combined.requests.post(LICENSE_SERVER_URL, json={"key": key, "hwid": hwid}, timeout=5)
            if r.status_code == 200 and r.json().get("valid"):
                QMessageBox.information(self, "License", "License is valid and active.")
            else:
                QMessageBox.warning(self, "License", "License rejected by server.")
        except:
            local = combined.validate_license_key(key)
            if local.get("valid"):
                QMessageBox.information(self, "License", "License valid (offline mode).")
            else:
                QMessageBox.warning(self, "License", f"License invalid: {local.get('reason','Unknown')}")

    def deactivate(self):
        resp = QMessageBox.question(self, "Deactivate",
            "Remove license from this machine?\nYou will need to re-enter your key to continue.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes: return
        lf = BASE_DIR / "license.dat"
        if lf.exists(): lf.unlink()
        QMessageBox.information(self, "Deactivated", "License removed. Restart to activate again.")

# ═══════════════════════════════════════════════════════════════
# DASHBOARD TAB
# ═══════════════════════════════════════════════════════════════

class DashboardTab(QWidget):
    def __init__(self):
        super().__init__()
        lo = QVBoxLayout()
        lo.setContentsMargins(16, 16, 16, 16)
        lo.setSpacing(14)

        t = QLabel("Dashboard")
        t.setObjectName("title")
        lo.addWidget(t)

        g = QHBoxLayout()
        g.setSpacing(12)
        self.c1 = StatCard("Total SC Claimed", "$0.00", "#22c55e")
        self.c2 = StatCard("Claims Today", "0")
        self.c3 = StatCard("Alerts Sent", "0")
        self.c4 = StatCard("Uptime", "0h 0m", "#6366f1")
        g.addWidget(self.c1); g.addWidget(self.c2); g.addWidget(self.c3); g.addWidget(self.c4)
        lo.addLayout(g)

        # Control center
        mc = QGroupBox("Dashboard")
        mcl = QVBoxLayout(); mcl.setContentsMargins(8,8,8,8); mcl.setSpacing(6)
        self.master_btn = AnimatedButton("Start All", variant="success")
        self.master_btn.setStyleSheet("font-size:15px;font-weight:700;padding:14px 32px;border-radius:10px;")
        self.master_btn.clicked.connect(self.toggle_master)
        mcl.addWidget(self.master_btn)
        # Service indicators
        sind = QHBoxLayout()
        sind.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.inds = {}
        for name in ["Scanner","Claims","Streamer","Links"]:
            b = QLabel(f"\u25cf {name}")
            b.setStyleSheet("color:#475569;font-size:12px;padding:4px 12px;")
            self.inds[name] = b
            sind.addWidget(b)
        mcl.addLayout(sind)
        mc.setLayout(mcl); lo.addWidget(mc)

        # System & Quick Access
        row = QHBoxLayout()
        sig = QGroupBox("System")
        sil = QVBoxLayout(); sil.setContentsMargins(8,8,8,8); sil.setSpacing(6)
        lf = BASE_DIR / "license.dat"
        self.tier = "Premium"
        if lf.exists():
            try:
                with open(lf) as f: ld = json.load(f)
                self.tier = ld.get("tier","Premium")
            except: pass
        self.sys_info = QLabel(f"{APP_VERSION}  |  {self.tier}  |  Scans: 0  |  Found: 0  |  Last: N/A")
        self.sys_info.setStyleSheet("font-size:12px;color:#94a3b8;")
        sil.addWidget(self.sys_info)
        self.last_refresh_lbl = QLabel("Last ping: —")
        self.last_refresh_lbl.setStyleSheet("font-size:11px;color:#64748b;")
        sil.addWidget(self.last_refresh_lbl)
        sig.setLayout(sil); row.addWidget(sig)
        lo.addLayout(row)

        lg = QGroupBox("Activity Log")
        ll = QVBoxLayout(lg); ll.setContentsMargins(8, 8, 8, 8); ll.setSpacing(6)
        hl = QHBoxLayout()
        hl.addWidget(QLabel("Log"))
        hl.addStretch()
        cls = AnimatedButton("Clear")
        cls.setFixedWidth(70)
        cls.clicked.connect(lambda: self.logv.clear())
        hl.addWidget(cls)
        ll.addLayout(hl)
        self.logv = QTextEdit()
        self.logv.setReadOnly(True)
        self.logv.setMaximumHeight(100)
        ll.addWidget(self.logv)
        lo.addWidget(lg)
        lo.addStretch()
        self.setLayout(lo)

        self.running = False
        self.threads = []
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)

    def log(self, msg):
        self.logv.append(msg)
        sb = self.logv.verticalScrollBar(); sb.setValue(sb.maximum())

    def set_indicator(self, name, on):
        if name in self.inds:
            self.inds[name].setStyleSheet(f"color:#{'10b981' if on else '475569'};font-size:12px;padding:4px 12px;")

    def toggle_master(self):
        if self.running: self.stop_master()
        else: self.start_master()

    def start_master(self):
        self.log("[MASTER] Starting...")
        self.running = True
        self.master_btn.setText("Stop All")
        self.master_btn._variant = "danger"
        self.master_btn._anim_to(AnimatedButton.VARIANTS["danger"]["normal"])
        self.master_btn.setStyleSheet("font-size:15px;font-weight:700;padding:14px 32px;border-radius:10px;")
        for fn in [combined.monitor_loop, combined.daily_freebies_loop]:
            t = threading.Thread(target=fn, daemon=True); t.start(); self.threads.append(t)
        self.set_indicator("Scanner", True)
        t = threading.Thread(target=combined.claim_scheduler_loop, daemon=True); t.start(); self.threads.append(t)
        self.set_indicator("Claims", True)
        if hasattr(combined, 'monitor_streamer_loop'):
            t = threading.Thread(target=combined.monitor_streamer_loop, daemon=True); t.start(); self.threads.append(t)
        self.set_indicator("Streamer", True)
        if hasattr(combined, 'process_queue_loop'):
            t = threading.Thread(target=combined.process_queue_loop, daemon=True); t.start(); self.threads.append(t)
        self.set_indicator("Links", True)
        with combined.state_lock:
            combined.state["bot_status"] = "online"; combined.state["status"] = "online"
        self.log("[MASTER] All systems running")

    def stop_master(self):
        self.log("[MASTER] Stopping...")
        self.running = False
        self.master_btn.setText("Start All")
        self.master_btn._variant = "success"
        self.master_btn._anim_to(AnimatedButton.VARIANTS["success"]["normal"])
        self.master_btn.setStyleSheet("font-size:15px;font-weight:700;padding:14px 32px;border-radius:10px;")
        with combined.state_lock:
            combined.state["bot_status"] = "offline"; combined.state["status"] = "offline"
        for name in self.inds:
            self.set_indicator(name, False)
        self.log("[MASTER] Stopped")

    def force_check(self):
        self.log("[DASH] Manual scan triggered")
        try:
            t = threading.Thread(target=combined.monitor_loop, daemon=True)
            t.start()
            self.log("[DASH] Scan dispatched")
        except Exception as e:
            self.log(f"[DASH] Scan failed: {e}")

    def refresh(self):
        with combined.state_lock:
            s = dict(combined.state)
        self.c1.set_val(f"${s.get('sc_total',0):.2f}")
        self.c2.set_val(str(s.get('claimed',0)))
        self.c3.set_val(str(s.get('found',0)))
        u = s.get('runtime',0); h,m = divmod(u,3600); m//=60
        self.c4.set_val(f"{int(h)}h {int(m)}m")
        la = s.get('last_alert')
        last_title = la.get('title','N/A')[:40] if la else 'N/A'
        self.sys_info.setText(f"{APP_VERSION}  |  {self.tier}  |  Scans: {s.get('scanned',0)}  |  Found: {s.get('found',0)}  |  Last: {last_title}")
        self.last_refresh_lbl.setText(f"Last ping: {datetime.now():%H:%M:%S}")
        st = s.get("bot_status","offline")
        if st=="online":
            self.set_indicator("Scanner", True)
        else:
            self.set_indicator("Scanner", False)

# ═══════════════════════════════════════════════════════════════
# PROFILES TAB
# ═══════════════════════════════════════════════════════════════

class ProfilesTab(QWidget):
    def __init__(self):
        super().__init__()
        lo = QVBoxLayout()
        lo.setContentsMargins(16,16,16,16); lo.setSpacing(12)

        t = QLabel("Profiles")
        t.setObjectName("title"); lo.addWidget(t)

        # Toolbar
        tb = QHBoxLayout(); tb.setSpacing(6)
        self.add_btn = AnimatedButton("+ Add", variant="gold")
        self.add_btn.clicked.connect(self.add_profile)
        tb.addWidget(self.add_btn)
        imp_btn = AnimatedButton("Import"); imp_btn.clicked.connect(self.import_profiles); tb.addWidget(imp_btn)
        exp_btn = AnimatedButton("Export"); exp_btn.clicked.connect(self.export_profiles); tb.addWidget(exp_btn)
        tb.addStretch()
        self.profile_count_lbl = QLabel("0 profiles")
        self.profile_count_lbl.setStyleSheet("color:#64748b;font-size:12px;")
        tb.addWidget(self.profile_count_lbl)
        lo.addLayout(tb)

        # Profiles table
        sg = QGroupBox("Casino Accounts")
        sl = QVBoxLayout(); sl.setContentsMargins(8,8,8,8); sl.setSpacing(6)
        self.profile_tbl = QTableWidget()
        self.profile_tbl.setColumnCount(6)
        self.profile_tbl.setHorizontalHeaderLabels(["Casino","Username","Method","SC Total","Status",""])
        self.profile_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.profile_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.profile_tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.profile_tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.profile_tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.profile_tbl.verticalHeader().setVisible(False)
        self.profile_tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.profile_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        sl.addWidget(self.profile_tbl)
        sg.setLayout(sl); lo.addWidget(sg, 1)

        # Log
        lg = QGroupBox("Log")
        ll = QVBoxLayout(lg); ll.setContentsMargins(8,8,8,8); ll.setSpacing(6)
        self.profile_log = QTextEdit()
        self.profile_log.setReadOnly(True)
        ll.addWidget(self.profile_log)
        lo.addWidget(lg)

        self.setLayout(lo)
        self.load()

    def log(self, msg):
        self.profile_log.append(msg)
        sb = self.profile_log.verticalScrollBar(); sb.setValue(sb.maximum())

    def load(self):
        accts = combined.load_accounts()
        self.profile_tbl.setRowCount(len(accts))
        self.profile_count_lbl.setText(f"{len(accts)} profiles")
        for i, (dom, info) in enumerate(sorted(accts.items())):
            self.profile_tbl.setItem(i,0,QTableWidgetItem(dom))
            self.profile_tbl.setItem(i,1,QTableWidgetItem(info.get("username","")))
            lm = info.get("login_method","email")
            si = QTableWidgetItem(lm.upper())
            si.setForeground(QColor("#a78bfa" if lm=="google" else "#ef4444" if lm=="apple" else "#64748b"))
            self.profile_tbl.setItem(i,2,si)
            self.profile_tbl.setItem(i,3,QTableWidgetItem(f"{info.get('sc_total',0):.2f} SC"))
            sched = combined.load_claim_schedule()
            sd = sched.get(dom, {})
            st_txt = sd.get("status","pending")
            sti = QTableWidgetItem(st_txt.upper())
            sti.setForeground(QColor("#10b981" if st_txt=="done" else "#eab308" if st_txt=="pending" else "#ef4444"))
            self.profile_tbl.setItem(i,4,sti)
            aw = QWidget(); awl = QHBoxLayout(aw); awl.setContentsMargins(2,2,2,2); awl.setSpacing(4)
            eb = QPushButton("Edit"); eb.setStyleSheet("color:#3b82f6;font-size:11px;padding:2px 8px;border-radius:4px;")
            eb.clicked.connect(lambda checked, d=dom: self.edit_profile(d))
            db = QPushButton("Del"); db.setStyleSheet("color:#ef4444;font-size:11px;padding:2px 8px;border-radius:4px;")
            db.clicked.connect(lambda checked, d=dom: self.delete_profile(d))
            awl.addWidget(eb); awl.addWidget(db); awl.addStretch()
            self.profile_tbl.setCellWidget(i,5,aw)
        self.profile_tbl.setRowCount(len(accts))

    def add_profile(self):
        d = AddAccountDlg(self)
        if d.exec():
            dom, un, pw, lm = d.vals()
            if dom and un and pw:
                accts = combined.load_accounts()
                entry = {"username": un, "password": pw, "sc_total": 0, "login_method": lm}
                if d._oauth_result:
                    entry["cookies"] = d._oauth_result
                    self.log(f"[PROFILES] {lm} session captured for {dom}")
                elif lm in ("google", "apple"):
                    self.log(f"[PROFILES] {lm} session capture incomplete for {dom}")
                accts[dom] = entry
                combined.save_accounts(accts)
                self.log(f"[PROFILES] Added {dom}")
                self.load()

    def edit_profile(self, dom):
        accts = combined.load_accounts()
        if dom not in accts: return
        info = accts[dom]
        d = AddAccountDlg(self)
        d.d.setCurrentText(dom)
        d.u.setText(info.get("username",""))
        d.p.setText(info.get("password",""))
        d._lm = info.get("login_method","email")
        if d.exec():
            new_dom, un, pw, lm = d.vals()
            old_info = accts.pop(dom)
            entry = {"username": un, "password": pw, "sc_total": old_info.get("sc_total",0), "login_method": lm}
            if d._oauth_result:
                entry["cookies"] = d._oauth_result
                self.log(f"[PROFILES] {lm} session captured for {new_dom}")
            elif lm in ("google", "apple") and not d._oauth_result:
                self.log(f"[PROFILES] {lm} session incomplete for {new_dom}")
            accts[new_dom] = entry
            combined.save_accounts(accts)
            self.log(f"[PROFILES] Updated {new_dom}")
            self.load()

    def delete_profile(self, dom):
        if QMessageBox.question(self,"Delete Profile",f"Remove {dom}?",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        accts = combined.load_accounts()
        accts.pop(dom, None)
        combined.save_accounts(accts)
        sched = combined.load_claim_schedule()
        sched.pop(dom, None)
        combined.save_claim_schedule(sched)
        self.log(f"[PROFILES] Deleted {dom}")
        self.load()

    def import_profiles(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Import Profiles", str(BASE_DIR), "JSON Files (*.json)")
        if not fn: return
        try:
            with open(fn) as f: data = json.load(f)
            if not isinstance(data, dict): raise ValueError("Expected dict")
            accts = combined.load_accounts()
            count = 0
            for dom, info in data.items():
                if dom not in accts and "username" in info and "password" in info:
                    accts[dom] = {"username": info["username"], "password": info["password"],
                        "sc_total": info.get("sc_total",0), "login_method": info.get("login_method","email")}
                    count += 1
            combined.save_accounts(accts)
            self.log(f"[PROFILES] Imported {count} profiles")
            self.load()
        except Exception as e:
            QMessageBox.warning(self, "Import Failed", str(e))

    def export_profiles(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Export Profiles", str(BASE_DIR / "profiles.json"), "JSON Files (*.json)")
        if not fn: return
        accts = combined.load_accounts()
        export = {}
        for dom, info in accts.items():
            export[dom] = {k: v for k, v in info.items() if k != "password"}
        with open(fn, "w") as f:
            json.dump(export, f, indent=2)
        self.log(f"[PROFILES] Exported {len(export)} profiles (passwords excluded)")

# ═══════════════════════════════════════════════════════════════
# DAILY SC TAB (Accounts + Schedule + Log merged)
# ═══════════════════════════════════════════════════════════════

class DailySCTab(QWidget):
    def __init__(self):
        super().__init__()
        self._stop_flag = threading.Event()
        self.workers = []
        lo = QVBoxLayout()
        lo.setContentsMargins(16, 16, 16, 16)
        lo.setSpacing(12)

        t = QLabel("Daily SC")
        t.setObjectName("title")
        lo.addWidget(t)

        # Summary + Upcoming Claims row
        sum_row = QHBoxLayout(); sum_row.setSpacing(16)
        sg = QGroupBox("Summary")
        sl = QHBoxLayout(); sl.setSpacing(16); sl.setContentsMargins(10, 8, 10, 8)
        self.daily_stat_labels = []
        for label, color in [("Total","#888"),("SC","#FFD700"),("Pending","#eab308"),("Rate","#10b981"),("Coverage","#6366f1")]:
            c = QVBoxLayout()
            c.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c.setSpacing(2)
            lbl = QLabel("0")
            lbl.setStyleSheet(f"font-size:20px;font-weight:700;color:{color};")
            c.addWidget(lbl)
            ll = QLabel(label)
            ll.setStyleSheet("font-size:10px;color:#64748b;text-transform:uppercase;")
            c.addWidget(ll)
            self.daily_stat_labels.append(lbl)
            sl.addLayout(c)
        sg.setLayout(sl); sum_row.addWidget(sg)

        ng = QGroupBox("Upcoming")
        nl = QVBoxLayout(); nl.setContentsMargins(8,8,8,8); nl.setSpacing(6)
        self.next_tbl = QTableWidget()
        self.next_tbl.setColumnCount(3)
        self.next_tbl.setHorizontalHeaderLabels(["Casino","Ready In","Status"])
        self.next_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.next_tbl.verticalHeader().setVisible(False)
        self.next_tbl.setMaximumHeight(80)
        self.next_tbl.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.next_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        nl.addWidget(self.next_tbl)
        ng.setLayout(nl); sum_row.addWidget(ng, 1)
        lo.addLayout(sum_row)

        # Toolbar
        tb = QHBoxLayout(); tb.setSpacing(4)
        mon = QLabel("\u25cf Monitoring 24/7"); mon.setStyleSheet("color:#10b981;font-size:12px;padding:0 4px;")
        tb.addWidget(mon)
        tb.addStretch()
        tb.addSpacing(8)
        a = AnimatedButton("+ Add", variant="gold"); a.clicked.connect(self.add); tb.addWidget(a)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine); sep.setStyleSheet("color:rgba(255,255,255,0.08);max-width:1px;")
        tb.addWidget(sep)
        tb.addSpacing(8)
        imp = AnimatedButton("Import"); imp.clicked.connect(self.import_accts); tb.addWidget(imp)
        r = AnimatedButton("Refresh"); r.clicked.connect(self.load); tb.addWidget(r); lo.addLayout(tb)

        # Accounts table (stretch)
        aw = QGroupBox("Accounts")
        al = QVBoxLayout(aw); al.setContentsMargins(8,8,8,8); al.setSpacing(6)
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(8)
        self.tbl.setHorizontalHeaderLabels(["Domain","Username","Login","Last Claim","Status","SC Total","Edit","Delete"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        al.addWidget(self.tbl)
        lo.addWidget(aw, 1)
        self.setLayout(lo)

        self.load()
        self.timer = QTimer()
        self.timer.timeout.connect(self.load)
        self.timer.start(5000)
        # Auto-start background monitor
        t = threading.Thread(target=combined.daily_sc_monitor_loop,
            args=(self._stop_flag, lambda m: self.log(f"[SC] {m}")), daemon=True)
        t.start()

    def load(self):
        accts = combined.load_accounts()
        sched = combined.load_claim_schedule()
        sites = combined.load_sites()
        sm = {s["domain"]: s["name"] for s in sites}

        total_sc = sum(a.get("sc_total",0) for a in accts.values())
        pending = sum(1 for d,s in sched.items() if s.get("status")=="claiming")
        success_count = sum(1 for d,s in sched.items() if s.get("status")=="done")
        total_claims = len([d for d,s in sched.items() if s.get("last_claim",0)>0])
        rate = f"{success_count/max(total_claims,1)*100:.0f}%" if total_claims else "—"
        coverage = f"{len(accts)}/{len(sites)}"

        self.daily_stat_labels[0].setText(str(len(accts)))
        self.daily_stat_labels[1].setText(f"${total_sc:.2f}")
        self.daily_stat_labels[2].setText(str(pending))
        self.daily_stat_labels[3].setText(rate)
        self.daily_stat_labels[4].setText(coverage)

        # Account table
        self.tbl.setRowCount(len(accts))
        for i,(dom,info) in enumerate(sorted(accts.items())):
            self.tbl.setItem(i,0,QTableWidgetItem(sm.get(dom,dom)))
            self.tbl.setItem(i,1,QTableWidgetItem(info.get("username","")))
            lm = info.get("login_method","email")
            # Google/Apple icon badge
            badge = QPixmap(16,16); badge.fill(Qt.GlobalColor.transparent)
            bp = QPainter(badge); bp.setRenderHint(QPainter.RenderHint.Antialiasing)
            bp.setPen(Qt.PenStyle.NoPen)
            if lm == "google":
                bp.setBrush(QColor("#4285F4"))
                bp.drawRoundedRect(0,0,16,16,4,4)
                bp.setPen(QColor("#fff")); bp.setFont(QFont("Inter",9,QFont.Weight.Bold))
                bp.drawText(badge.rect(), Qt.AlignmentFlag.AlignCenter, "G")
            elif lm == "apple":
                bp.setBrush(QColor("#000"))
                bp.drawRoundedRect(0,0,16,16,4,4)
                bp.setPen(QColor("#fff")); bp.setFont(QFont("Inter",9,QFont.Weight.Bold))
                bp.drawText(badge.rect(), Qt.AlignmentFlag.AlignCenter, "\u2318")
            else:
                bp.setBrush(QColor("#64748b"))
                bp.drawRoundedRect(0,0,16,16,4,4)
                bp.setPen(QColor("#fff")); bp.setFont(QFont("Inter",9,QFont.Weight.Bold))
                bp.drawText(badge.rect(), Qt.AlignmentFlag.AlignCenter, "@")
            bp.end()
            lmi = QTableWidgetItem()
            lmi.setIcon(QIcon(badge))
            lmi.setText(" "+lm.capitalize())
            lmi.setForeground(QColor("#6366f1" if lm=="google" else "#ef4444" if lm=="apple" else "#888"))
            self.tbl.setItem(i,2,lmi)
            sc = sched.get(dom,{})
            lc = sc.get("last_claim",0)
            self.tbl.setItem(i,3,QTableWidgetItem(datetime.fromtimestamp(lc).strftime("%m/%d %H:%M") if lc else "Never"))
            st = sc.get("status","never")
            si = QTableWidgetItem(st.upper())
            si.setForeground(QColor("#10b981" if st in ("done","never") else "#eab308" if st=="claiming" else "#ef4444"))
            self.tbl.setItem(i,4,si)
            sct = info.get("sc_total",0)
            sci = QTableWidgetItem(f"${sct:.2f}")
            sci.setForeground(QColor("#FFD700"))
            self.tbl.setItem(i,5,sci)
            eb = AnimatedButton("\u270f\ufe0f")
            eb.setStyleSheet("font-size:12px;padding:2px 8px;border-radius:4px;min-width:0;")
            eb.clicked.connect(lambda checked,d=dom: self.edit_account(d))
            self.tbl.setCellWidget(i,6,eb)
            db = AnimatedButton("\u2715")
            db._variant = "danger"
            db.setStyleSheet("font-size:12px;padding:2px 8px;border-radius:4px;min-width:0;background:#991b1b;color:#fca5a5;border:1px solid #b91c1c;"
                "QPushButton:hover{background:#b91c1c;color:#fff;}QPushButton:pressed{background:#991b1b;}")
            db.clicked.connect(lambda checked,d=dom: self.delete_account(d))
            self.tbl.setCellWidget(i,7,db)

        # Collect upcoming claims
        now = time.time()
        ready_list = []
        for dom, info in sched.items():
            s = sched.get(dom,{})
            lc = s.get("last_claim",0)
            if lc:
                nc = lc+86400
                st = s.get("status","never")
                if now<nc and st!="claiming" and dom in accts:
                    r=int(nc-now); h,m=divmod(r,3600); m//=60; ns=f"{h}h {m}m"
                    ready_list.append((ns, sm.get(dom,dom), st))

        # Next Claims table (top 3 soonest)
        ready_list.sort()
        self.next_tbl.setRowCount(min(len(ready_list), 3))
        for i, (time_left, casino, status) in enumerate(ready_list[:3]):
            self.next_tbl.setItem(i,0,QTableWidgetItem(casino))
            self.next_tbl.setItem(i,1,QTableWidgetItem(time_left))
            si = QTableWidgetItem(status.upper())
            si.setForeground(QColor("#eab308"))
            self.next_tbl.setItem(i,2,si)

    def edit_account(self, dom):
        accts = combined.load_accounts()
        if dom not in accts: return
        info = accts[dom]
        d = AddAccountDlg(self)
        d.d.setCurrentText(dom)
        d.u.setText(info.get("username",""))
        d.p.setText(info.get("password",""))
        cur_lm = info.get("login_method","email")
        d._lm = cur_lm
        if d.exec():
            new_dom, un, pw, lm = d.vals()
            old_info = accts.pop(dom)
            entry = {"username": un, "password": pw, "sc_total": old_info.get("sc_total",0), "login_method": lm}
            if d._oauth_result:
                entry["cookies"] = d._oauth_result
                self.log(f"[SC] {lm} session captured for {new_dom}")
            elif lm in ("google", "apple") and not d._oauth_result:
                self.log(f"[SC] {lm} session capture incomplete for {new_dom}")
            accts[new_dom] = entry
            combined.save_accounts(accts)
            sched = combined.load_claim_schedule()
            if dom in sched and dom != new_dom:
                sched[new_dom] = sched.pop(dom)
                combined.save_claim_schedule(sched)
            self.load()

    def delete_account(self, dom):
        if QMessageBox.question(self,"Delete Account",f"Remove {dom} and all claim history?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        accts = combined.load_accounts()
        accts.pop(dom, None)
        combined.save_accounts(accts)
        sched = combined.load_claim_schedule()
        sched.pop(dom, None)
        combined.save_claim_schedule(sched)
        self.load()

    def claim(self, dom):
        accts = combined.load_accounts()
        if dom not in accts: return
        info = accts[dom]
        sched = combined.load_claim_schedule()
        sched[dom] = sched.get(dom,{"last_claim":0,"status":"claiming"})
        sched[dom]["status"] = "claiming"
        combined.save_claim_schedule(sched)
        w = ClaimWorker(dom,info["username"],info["password"],info.get("login_method","email"))
        w.log.connect(self.log)
        w.done.connect(self.fin)
        self.workers.append(w); w.start()

    def fin(self, dom, ok, sc):
        if ok:
            with combined.state_lock:
                combined.state["claimed"] += 1
                combined.state["sc_total"] = round(combined.state["sc_total"]+sc,2)
            accts = combined.load_accounts()
            if dom in accts:
                accts[dom]["sc_total"] = round(accts[dom].get("sc_total",0)+sc,2)
                combined.save_accounts(accts)
        self.load()

    def import_accts(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Import Accounts", str(BASE_DIR), "JSON Files (*.json)")
        if not fn: return
        try:
            with open(fn) as f: data = json.load(f)
            if not isinstance(data, dict): raise ValueError("Expected dict")
            accts = combined.load_accounts()
            count = 0
            for dom, info in data.items():
                if dom not in accts and "username" in info and "password" in info:
                    accts[dom] = {"username": info["username"], "password": info["password"], "sc_total": info.get("sc_total",0), "login_method": info.get("login_method","email")}
                    count += 1
            combined.save_accounts(accts)
            self.load()
        except Exception as e:
            QMessageBox.warning(self, "Import Failed", str(e))

    def add(self):
        d = AddAccountDlg(self)
        if d.exec():
            dom,un,pw,lm = d.vals()
            if dom and un and pw:
                accts = combined.load_accounts()
                entry = {"username": un, "password": pw, "sc_total": 0, "login_method": lm}
                if d._oauth_result:
                    entry["cookies"] = d._oauth_result
                    self.log(f"[SC] {lm} session captured for {dom}")
                elif lm in ("google", "apple"):
                    self.log(f"[SC] {lm} session capture incomplete for {dom}")
                accts[dom] = entry
                combined.save_accounts(accts)
                self.load()

class AddAccountDlg(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Account"); self.setFixedSize(400,320)
        self._oauth_result = None
        lo = QVBoxLayout(); lo.setContentsMargins(24,20,24,20); lo.setSpacing(10)
        t = QLabel("Add Account"); t.setObjectName("title"); t.setStyleSheet("font-size:18px;margin-bottom:2px;"); lo.addWidget(t)
        fm = QFormLayout(); fm.setSpacing(8)
        self.d = QComboBox()
        self.d.setStyleSheet("QComboBox{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:6px 10px;color:#ccc;font-size:13px;}"
            "QComboBox:hover{border-color:rgba(255,215,0,0.2);}"
            "QComboBox::drop-down{subcontrol-origin:padding;subcontrol-position:top right;width:24px;border:none;}"
            "QComboBox::down-arrow{image:none;border-left:4px solid transparent;border-right:4px solid transparent;border-top:5px solid #888;margin-right:6px;}"
            "QComboBox QAbstractItemView{background:#1a1a24;border:1px solid rgba(255,255,255,0.08);border-radius:4px;color:#ccc;outline:none;}"
            "QComboBox QAbstractItemView::item{padding:4px 8px;}"
            "QComboBox QAbstractItemView::item:hover{background:rgba(255,215,0,0.1);color:#fff;}")
        sites = combined.load_sites()
        for s in sites:
            self.d.addItem(f"{s['name']} ({s['domain']})", s["domain"])
        self.d.setEditable(True)
        fm.addRow("Casino:",self.d)
        self.u = QLineEdit(); self.u.setPlaceholderText("Account email")
        self.u.setStyleSheet("background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:6px 10px;color:#ccc;font-size:13px;")
        fm.addRow("Username:",self.u)
        self.p = QLineEdit(); self.p.setPlaceholderText("Password"); self.p.setEchoMode(QLineEdit.EchoMode.Password)
        self.p.setStyleSheet("background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:6px 10px;color:#ccc;font-size:13px;")
        fm.addRow("Password:",self.p)
        lo.addLayout(fm)

        # OAuth + Save/Cancel in a 2x2 grid
        self._lm = "email"
        grid = QGridLayout(); grid.setSpacing(8)
        self.google_btn = QPushButton()
        gb_icon = QPixmap(18,18); gb_icon.fill(Qt.GlobalColor.transparent)
        gp = QPainter(gb_icon); gp.setRenderHint(QPainter.RenderHint.Antialiasing)
        gp.setPen(Qt.PenStyle.NoPen); gp.setBrush(QColor("#4285F4"))
        gp.drawRoundedRect(0,0,18,18,4,4)
        gp.setPen(QColor("#fff")); gp.setFont(QFont("Inter",10,QFont.Weight.Bold))
        gp.drawText(gb_icon.rect(), Qt.AlignmentFlag.AlignCenter, "G")
        gp.end()
        self.google_btn.setIcon(QIcon(gb_icon))
        self.google_btn.setText("  Google Sign-In")
        self.google_btn.setStyleSheet("QPushButton{background:#4285F4;color:#fff;border:none;border-radius:6px;padding:8px 12px;font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:#3367D6;}QPushButton:disabled{background:#333;color:#666;}")
        self.google_btn.clicked.connect(lambda: self._do_oauth("google"))
        self.apple_btn = QPushButton()
        ab_icon = QPixmap(18,18); ab_icon.fill(Qt.GlobalColor.transparent)
        ap = QPainter(ab_icon); ap.setRenderHint(QPainter.RenderHint.Antialiasing)
        ap.setPen(Qt.PenStyle.NoPen); ap.setBrush(QColor("#000"))
        ap.drawRoundedRect(0,0,18,18,4,4)
        ap.setPen(QColor("#fff")); ap.setFont(QFont("Inter",10,QFont.Weight.Bold))
        ap.drawText(ab_icon.rect(), Qt.AlignmentFlag.AlignCenter, "\u2318")
        ap.end()
        self.apple_btn.setIcon(QIcon(ab_icon))
        self.apple_btn.setText("  Apple Sign-In")
        self.apple_btn.setStyleSheet("QPushButton{background:#1a1a1a;color:#fff;border:1px solid rgba(255,255,255,0.12);border-radius:6px;padding:8px 12px;font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:#333;}QPushButton:disabled{background:#111;color:#555;}")
        self.apple_btn.clicked.connect(lambda: self._do_oauth("apple"))
        self.save_btn = AnimatedButton("Save", variant="gold")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = AnimatedButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        grid.addWidget(self.google_btn, 0, 0)
        grid.addWidget(self.apple_btn, 0, 1)
        grid.addWidget(self.save_btn, 1, 0)
        grid.addWidget(self.cancel_btn, 1, 1)
        lo.addLayout(grid)
        self.setLayout(lo)
    def _do_oauth(self, method):
        self._lm = method
        self.u.setEnabled(False); self.p.setEnabled(False)
        self.u.setStyleSheet("background:#333;color:#666;"); self.p.setStyleSheet("background:#333;color:#666;")
        self.google_btn.setEnabled(False); self.apple_btn.setEnabled(False)
        self.save_btn.setEnabled(False); self.cancel_btn.setEnabled(False)
        dom = self.d.currentData() or self.d.currentText().strip()
        un = self.u.text().strip(); pw = self.p.text().strip()
        if un and pw and hasattr(combined, 'auto_sso_login'):
            sess = combined.auto_sso_login(dom, method, un, pw)
            if sess and sess.get("success"):
                self._oauth_result = json.dumps(sess.get("cookies",[]), default=str)
                self.u.setEnabled(True); self.p.setEnabled(True)
                self.u.setStyleSheet(""); self.p.setStyleSheet("")
                self.google_btn.setEnabled(True); self.apple_btn.setEnabled(True)
                self.save_btn.setEnabled(True); self.cancel_btn.setEnabled(True)
                self.accept()
                return
        # Fallback: manual capture
        if hasattr(combined, 'capture_oauth_session'):
            sess = combined.capture_oauth_session(dom, method)
            if sess and sess.get("success"):
                self._oauth_result = json.dumps(sess.get("cookies",[]), default=str)
        self.u.setEnabled(True); self.p.setEnabled(True)
        self.u.setStyleSheet(""); self.p.setStyleSheet("")
        self.google_btn.setEnabled(True); self.apple_btn.setEnabled(True)
        self.save_btn.setEnabled(True); self.cancel_btn.setEnabled(True)
    def vals(self):
        return (self.d.currentData() or self.d.currentText().strip(),
                self.u.text().strip(), self.p.text().strip(), self._lm)

# ═══════════════════════════════════════════════════════════════
# STREAMER SNIPER TAB
# ═══════════════════════════════════════════════════════════════

class StreamerSniperTab(QWidget):
    def __init__(self):
        super().__init__()
        lo = QVBoxLayout()
        lo.setContentsMargins(16,16,16,16); lo.setSpacing(12)

        t = QLabel("Streamer Sniper")
        t.setObjectName("title"); lo.addWidget(t)

        self.sniper_stats = QLabel("Monitored: 0  \u00b7  Online: 0  \u00b7  Checks: 0")
        self.sniper_stats.setStyleSheet("font-size:13px;color:#94a3b8;padding:4px 0;")

        tb = QHBoxLayout(); tb.setSpacing(8)
        tb.addWidget(self.sniper_stats); tb.addStretch()
        self.sniper_tgl = AnimatedButton("Watch", variant="success")
        self.sniper_tgl.clicked.connect(self.toggle_sniper)
        tb.addWidget(self.sniper_tgl)
        refresh_btn = AnimatedButton("Refresh All")
        refresh_btn.clicked.connect(self.force_refresh)
        tb.addWidget(refresh_btn)
        lo.addLayout(tb)

        # Streamer list
        sg = QGroupBox("Monitored Streamers")
        sl = QVBoxLayout(); sl.setContentsMargins(8,8,8,8); sl.setSpacing(6)
        self.streamer_list = QTableWidget()
        self.streamer_list.setColumnCount(4)
        self.streamer_list.setHorizontalHeaderLabels(["Platform","Username","Status","Last Seen"])
        self.streamer_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.streamer_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.streamer_list.verticalHeader().setVisible(False)
        self.streamer_list.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.streamer_list.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        sl.addWidget(self.streamer_list)
        ab = QHBoxLayout()
        self.sadd = AnimatedButton("+ Add", variant="gold"); self.sadd.clicked.connect(self.add_streamer)
        self.srm = AnimatedButton("Remove"); self.srm.clicked.connect(self.remove_streamer)
        exp = AnimatedButton("Export"); exp.clicked.connect(self.export_streamers)
        ab.addWidget(self.sadd); ab.addWidget(self.srm); ab.addWidget(exp); ab.addStretch()
        sl.addLayout(ab)
        sg.setLayout(sl); lo.addWidget(sg)

        # Detection History + Log side by side
        bot_row = QHBoxLayout(); bot_row.setSpacing(12)
        dg = QGroupBox("Detections")
        dl = QVBoxLayout(dg); dl.setContentsMargins(8, 8, 8, 8); dl.setSpacing(6)
        self.detect_tbl = QTableWidget()
        self.detect_tbl.setColumnCount(3)
        self.detect_tbl.setHorizontalHeaderLabels(["Time","Platform","Username"])
        self.detect_tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.detect_tbl.verticalHeader().setVisible(False)
        self.detect_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.detect_tbl.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        dl.addWidget(self.detect_tbl)
        bot_row.addWidget(dg)
        lg = QGroupBox("Log")
        ll = QVBoxLayout(lg); ll.setContentsMargins(8, 8, 8, 8); ll.setSpacing(6)
        self.sniper_log = QTextEdit()
        self.sniper_log.setReadOnly(True)
        ll.addWidget(self.sniper_log)
        bot_row.addWidget(lg)
        lo.addLayout(bot_row)

        lo.addStretch()
        self.setLayout(lo)
        self.sniper_running = False
        self.sniper_threads = []
        self.check_count = 0
        self.detections = []
        self.refresh_streamers()
        self.sniper_timer = QTimer()
        self.sniper_timer.timeout.connect(self.refresh_streamers)
        self.sniper_timer.start(10000)

    def log(self, msg):
        self.sniper_log.append(msg)
        sb = self.sniper_log.verticalScrollBar(); sb.setValue(sb.maximum())

    def refresh_streamers(self):
        streamers = combined.load_streamers() if hasattr(combined, 'load_streamers') else []
        self.streamer_list.setRowCount(len(streamers))
        online = 0
        self.check_count += 1
        for i, s in enumerate(streamers):
            self.streamer_list.setItem(i,0,QTableWidgetItem(s.get("platform","Kick")))
            self.streamer_list.setItem(i,1,QTableWidgetItem(s.get("username","")))
            status = s.get("status","idle")
            si = QTableWidgetItem(status)
            si.setForeground(QColor("#10b981" if status=="live" else "#eab308" if status=="idle" else "#475569"))
            self.streamer_list.setItem(i,2,si)
            self.streamer_list.setItem(i,3,QTableWidgetItem(s.get("last_seen","Never")))
            if status == "live":
                online += 1
                # Log new detection
                if not self.detections or self.detections[-1].get("username") != s.get("username") or self.detections[-1].get("timestamp","") < datetime.now().strftime("%Y-%m-%d %H:%M"):
                    self.detections.append({"timestamp": datetime.now().strftime("%H:%M:%S"), "platform": s.get("platform",""), "username": s.get("username","")})
                    if len(self.detections) > 20: self.detections = self.detections[-20:]
        self.sniper_stats.setText(f"Monitored: {len(streamers)}  \u00b7  Online: {online}  \u00b7  Checks: {self.check_count}")
        # Update detection history table
        self.detect_tbl.setRowCount(min(len(self.detections), 10))
        for i, d in enumerate(self.detections[-10:]):
            self.detect_tbl.setItem(i,0,QTableWidgetItem(d.get("timestamp","")))
            self.detect_tbl.setItem(i,1,QTableWidgetItem(d.get("platform","")))
            self.detect_tbl.setItem(i,2,QTableWidgetItem(d.get("username","")))

    def force_refresh(self):
        self.log("[SNIPER] Refreshing all streamers...")
        if hasattr(combined, 'monitor_streamer_loop'):
            t = threading.Thread(target=combined.monitor_streamer_loop, daemon=True)
            t.start()
        self.refresh_streamers()
        self.log("[SNIPER] Refresh complete")

    def export_streamers(self):
        streamers = combined.load_streamers() if hasattr(combined, 'load_streamers') else []
        fn, _ = QFileDialog.getSaveFileName(self, "Export Streamers", str(BASE_DIR / "streamers_export.json"), "JSON Files (*.json)")
        if not fn: return
        try:
            with open(fn, 'w') as f: json.dump(streamers, f, indent=2)
            self.log(f"[SNIPER] Exported {len(streamers)} streamers to {Path(fn).name}")
        except Exception as e:
            self.log(f"[SNIPER] Export failed: {e}")

    def add_streamer(self):
        dlg = QDialog(self); dlg.setWindowTitle("Add Streamer"); dlg.setFixedSize(360,220)
        lo = QVBoxLayout(dlg); lo.setSpacing(12)
        lo.addWidget(QLabel("Streamer Username:"))
        un = QLineEdit(); un.setPlaceholderText("streamer_name"); lo.addWidget(un)
        lo.addWidget(QLabel("Platform:"))
        plat = QComboBox(); plat.addItems(["Kick", "Twitch"]); lo.addWidget(plat)
        bl = QHBoxLayout()
        ok = QPushButton("Add"); ok.setObjectName("gold"); ok.clicked.connect(dlg.accept)
        no = QPushButton("Cancel"); no.clicked.connect(dlg.reject)
        bl.addWidget(ok); bl.addWidget(no); lo.addLayout(bl)
        if dlg.exec():
            u = un.text().strip()
            p = plat.currentText()
            if u:
                streamers = combined.load_streamers() if hasattr(combined, 'load_streamers') else []
                streamers.append({"platform": p, "username": u, "status": "idle", "last_seen": "Never"})
                if hasattr(combined, 'save_streamers'):
                    combined.save_streamers(streamers)
                self.refresh_streamers()
                self.log(f"[SNIPER] Added streamer: {u} ({p})")

    def remove_streamer(self):
        r = self.streamer_list.currentRow()
        if r < 0: return
        streamers = combined.load_streamers() if hasattr(combined, 'load_streamers') else []
        if r < len(streamers):
            u = streamers[r].get("username","")
            del streamers[r]
            if hasattr(combined, 'save_streamers'):
                combined.save_streamers(streamers)
            self.refresh_streamers()
            self.log(f"[SNIPER] Removed streamer: {u}")

    def toggle_sniper(self):
        if self.sniper_running:
            self.sniper_running = False
            self.sniper_tgl.setText("Watch")
            self.sniper_tgl._variant = "success"
            self.sniper_tgl._anim_to(AnimatedButton.VARIANTS["success"]["normal"])
            self.log("[SNIPER] Stopped")
        else:
            self.sniper_running = True
            self.sniper_tgl.setText("Stop Watching")
            self.sniper_tgl._variant = "danger"
            self.sniper_tgl._anim_to(AnimatedButton.VARIANTS["danger"]["normal"])
            self.log("[SNIPER] Watching...")
            if hasattr(combined, 'monitor_streamer_loop'):
                t = threading.Thread(target=combined.monitor_streamer_loop, daemon=True)
                t.start(); self.sniper_threads.append(t)
            self.log("[SNIPER] Active")

# ═══════════════════════════════════════════════════════════════
# LINK AUTOMATION TAB
# ═══════════════════════════════════════════════════════════════

class LinkAutomationTab(QWidget):
    def __init__(self):
        super().__init__()
        lo = QVBoxLayout()
        lo.setContentsMargins(16,16,16,16); lo.setSpacing(12)

        t = QLabel("Link Automation")
        t.setObjectName("title"); lo.addWidget(t)

        # Stats frame
        sg = QGroupBox("Link Stats")
        sl = QHBoxLayout(); sl.setContentsMargins(8,8,8,8); sl.setSpacing(6)
        self.link_stats_labels = []
        for label, color in [("Total","#888"),("Processed","#eab308"),("Success","#10b981"),("Failed","#ef4444"),("Rate","#6366f1")]:
            c = QVBoxLayout(); c.setSpacing(2)
            c.addWidget(QLabel("0"))
            c.addWidget(QLabel(label))
            c.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.link_stats_labels.append(c.itemAt(0).widget())
            sl.addLayout(c)
        sg.setLayout(sl); lo.addWidget(sg)

        # Add link row
        ab = QHBoxLayout(); ab.setSpacing(6)
        self.add_btn = AnimatedButton("+ Add Link", variant="gold"); self.add_btn.clicked.connect(self.add_link); ab.addWidget(self.add_btn)
        self.auto_feed_cb = QCheckBox("Auto-claim from Flood Feed")
        self.auto_feed_cb.setChecked(True)
        self.auto_feed_cb.setStyleSheet("color:#94a3b8;font-size:12px;")
        ab.addWidget(self.auto_feed_cb)
        ab.addStretch()
        lo.addLayout(ab)

        # ═══ Two-panel splitter: Queue (left) + Flood Feed (right) ═══
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        # ── LEFT PANEL: Queue ──
        left_frame = QFrame()
        left_lo = QVBoxLayout(left_frame); left_lo.setContentsMargins(4,4,4,4); left_lo.setSpacing(6)

        self.queue_tbl = QTableWidget()
        self.queue_tbl.setColumnCount(5)
        self.queue_tbl.setHorizontalHeaderLabels(["URL","Added","Status","Result",""])
        self.queue_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.queue_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.queue_tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.queue_tbl.verticalHeader().setVisible(False)
        self.queue_tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.queue_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        left_lo.addWidget(self.queue_tbl, 1)

        ctrl_row = QHBoxLayout()
        self.process_btn = AnimatedButton("Start Automation", variant="success")
        self.process_btn.clicked.connect(self.process_queue)
        ctrl_row.addWidget(self.process_btn)
        self.no_profile_lbl = QLabel("")
        self.no_profile_lbl.setStyleSheet("color:#eab308;font-size:11px;padding:0 6px;")
        ctrl_row.addWidget(self.no_profile_lbl)
        cc_btn = AnimatedButton("Clear Done"); cc_btn.clicked.connect(self.clear_completed); ctrl_row.addWidget(cc_btn)
        self.clear_btn = AnimatedButton("Clear"); self.clear_btn.clicked.connect(self.clear_queue); ctrl_row.addWidget(self.clear_btn)
        ctrl_row.addStretch()
        left_lo.addLayout(ctrl_row)
        splitter.addWidget(left_frame)

        # ── RIGHT PANEL: Flood Feed ──
        right_frame = QFrame()
        right_lo = QVBoxLayout(right_frame); right_lo.setContentsMargins(4,4,4,4); right_lo.setSpacing(6)

        fg = QGroupBox("Flood Feed \u2014 Last 24h Free Drops")
        fgl = QVBoxLayout(fg); fgl.setContentsMargins(8,8,8,8); fgl.setSpacing(6)
        self.feed_list = QListWidget()
        self.feed_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.feed_list.setStyleSheet(
            "QListWidget{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:8px;}"
            "QListWidget::item{border-bottom:1px solid rgba(255,255,255,0.03);}"
        )
        fgl.addWidget(self.feed_list)
        right_lo.addWidget(fg)
        splitter.addWidget(right_frame)

        splitter.setSizes([600, 600])
        lo.addWidget(splitter, 1)

        # Log (always visible 24/7)
        lg = QGroupBox("Log")
        ll = QVBoxLayout(lg); ll.setContentsMargins(8,8,8,8); ll.setSpacing(6)
        self.link_log = QTextEdit()
        self.link_log.setReadOnly(True)
        ll.addWidget(self.link_log)
        lo.addWidget(lg, 1)

        self.setLayout(lo)
        self.refresh_queue()
        self.refresh_flood_feed()
        self.link_timer = QTimer()
        self.link_timer.timeout.connect(self.refresh_queue)
        self.link_timer.start(5000)
        self.feed_timer = QTimer()
        self.feed_timer.timeout.connect(self.refresh_flood_feed)
        self.feed_timer.start(300000)

        # Profile check timer — disable Start Automation if no profiles
        self.profile_timer = QTimer()
        self.profile_timer.timeout.connect(self._check_profiles)
        self.profile_timer.start(3000)
        self._check_profiles()

        # Auto-start Discord watcher (24/7, no UI toggle)
        if hasattr(combined, 'discord_watch_loop'):
            import threading
            t = threading.Thread(target=combined.discord_watch_loop,
                args=(combined.DISCORD_BOT_TOKEN, combined.DISCORD_CHANNEL_ID,
                      lambda msg: self.log(f"[DISCORD] {msg}")), daemon=True)
            t.start()

        # Start auto-processing on init (24/7)
        if hasattr(combined, 'process_queue_loop'):
            t = threading.Thread(target=combined.process_queue_loop, daemon=True)
            t.start()

    def log(self, msg):
        self.link_log.append(msg)
        sb = self.link_log.verticalScrollBar(); sb.setValue(sb.maximum())
        # Notify tray on link capture
        if "[DISCORD] Added" in msg:
            w = self.window()
            if hasattr(w, 'tray') and w.tray.isVisible():
                w.tray.showMessage("Link Captured", msg.split("Added")[-1].strip(), QSystemTrayIcon.MessageIcon.Information, 3000)

    def refresh_queue(self):
        queue = combined.load_link_queue() if hasattr(combined, 'load_link_queue') else []
        self.queue_tbl.setRowCount(len(queue))
        total = len(queue)
        pending = sum(1 for q in queue if q.get("status") == "pending")
        processed = sum(1 for q in queue if q.get("status") in ("done","failed"))
        success = sum(1 for q in queue if q.get("status") == "done")
        failed = sum(1 for q in queue if q.get("status") == "failed")
        rate = f"{success/max(processed,1)*100:.0f}%" if processed else "—"
        self.link_stats_labels[0].setText(str(total))
        self.link_stats_labels[1].setText(str(processed))
        self.link_stats_labels[2].setText(str(success))
        self.link_stats_labels[3].setText(str(failed))
        self.link_stats_labels[4].setText(rate)

        for i, item in enumerate(queue):
            self.queue_tbl.setItem(i,0,QTableWidgetItem(item.get("url","")[:60]))
            self.queue_tbl.setItem(i,1,QTableWidgetItem(item.get("added","")))
            st = item.get("status","pending")
            si = QTableWidgetItem(st)
            si.setForeground(QColor("#10b981" if st=="done" else "#ef4444" if st=="failed" else "#eab308" if st=="processing" else "#64748b"))
            self.queue_tbl.setItem(i,2,si)
            self.queue_tbl.setItem(i,3,QTableWidgetItem(item.get("result","")))
            rb = QPushButton("Remove")
            rb.setStyleSheet("QPushButton{color:#ef4444;font-size:11px;padding:4px 10px;border-radius:6px;}")
            rb.clicked.connect(lambda checked, idx=i: self.remove_link(idx))
            self.queue_tbl.setCellWidget(i,4,rb)

    def add_link(self):
        url, ok = QInputDialog.getText(self, "Add Link", "Enter sweepstakes URL:")
        if not ok or not url.strip(): return
        url = url.strip()
        queue = combined.load_link_queue() if hasattr(combined, 'load_link_queue') else []
        queue.append({"url": url, "added": datetime.now().strftime("%m/%d %H:%M"), "status": "pending", "result": "", "casino": ""})
        if hasattr(combined, 'save_link_queue'):
            combined.save_link_queue(queue)
        self.refresh_queue()
        self.log(f"[LINK] Added: {url[:50]}...")

    def remove_link(self, idx):
        queue = combined.load_link_queue() if hasattr(combined, 'load_link_queue') else []
        if idx < len(queue):
            del queue[idx]
            if hasattr(combined, 'save_link_queue'):
                combined.save_link_queue(queue)
            self.refresh_queue()

    def clear_completed(self):
        queue = combined.load_link_queue() if hasattr(combined, 'load_link_queue') else []
        remaining = [q for q in queue if q.get("status") not in ("done","failed")]
        if hasattr(combined, 'save_link_queue'):
            combined.save_link_queue(remaining)
        self.refresh_queue()
        self.log(f"[LINK] Cleared {len(queue)-len(remaining)} completed items")

    def clear_queue(self):
        if hasattr(combined, 'save_link_queue'):
            combined.save_link_queue([])
        self.refresh_queue()
        self.log("[LINK] Queue cleared")

    def refresh_flood_feed(self):
        self.feed_list.clear()
        posts = combined.state.get("daily_posts", [])
        if not posts:
            posts = combined.fetch_discord_freebies() + combined.fetch_daily_freebies()
            posts.sort(key=lambda x: x.get("created_utc", 0), reverse=True)
            if posts:
                with combined.state_lock:
                    combined.state["daily_posts"] = posts[:50]
        if not posts:
            item = QListWidgetItem("  No recent drops found yet")
            item.setForeground(QColor("#64748b"))
            self.feed_list.addItem(item)
            return
        for post in posts[-50:]:
            widget = QWidget()
            wl = QVBoxLayout(widget); wl.setContentsMargins(10,8,10,8); wl.setSpacing(6)
            top = QHBoxLayout(); top.setContentsMargins(0,0,0,0); top.setSpacing(10)
            name_lbl = QLabel(post.get("casino_name", post.get("casino", "Unknown")))
            name_lbl.setStyleSheet("font-weight:700;color:#eab308;font-size:13px;")
            top.addWidget(name_lbl)
            cu = post.get("created_utc", "")
            if isinstance(cu, (int, float)):
                cu = datetime.fromtimestamp(cu).strftime("%m/%d %H:%M")
            date_lbl = QLabel(str(cu)[:16].replace("T"," "))
            date_lbl.setStyleSheet("color:#64748b;font-size:10px;padding-top:2px;")
            top.addWidget(date_lbl)
            top.addStretch()
            if post.get("sc_amount"):
                sc_lbl = QLabel(f"+{post['sc_amount']} SC")
                sc_lbl.setStyleSheet("color:#10b981;font-weight:700;font-size:12px;")
                top.addWidget(sc_lbl)
            wl.addLayout(top)
            if post.get("title"):
                tl = QLabel(post["title"])
                tl.setStyleSheet("color:#cbd5e1;font-size:11px;")
                tl.setWordWrap(True)
                wl.addWidget(tl)
            if post.get("url"):
                ul = QLabel(f'<a href="{post["url"]}" style="color:#3b82f6;font-size:11px;text-decoration:none;">\U0001f517 Open Link</a>')
                ul.setOpenExternalLinks(True)
                wl.addWidget(ul)
            li = QListWidgetItem()
            li.setSizeHint(widget.sizeHint())
            self.feed_list.addItem(li)
            self.feed_list.setItemWidget(li, widget)

    def _check_profiles(self):
        accts = combined.load_accounts()
        has_profiles = len(accts) > 0
        self.process_btn.setEnabled(has_profiles)
        if not has_profiles:
            self.no_profile_lbl.setText("\u26a0 Add a profile first")
        else:
            self.no_profile_lbl.setText("")

    def process_queue(self):
        # Guard: require at least one profile
        accts = combined.load_accounts()
        if not accts:
            QMessageBox.warning(self, "No Profiles",
                "No casino profiles configured.\n\nGo to the Profiles tab to add your first account before starting automation.")
            return

        # Auto-queue flood feed posts that match profiles
        if self.auto_feed_cb.isChecked():
            posts = combined.state.get("daily_posts", [])
            if not posts:
                posts = combined.fetch_discord_freebies() + combined.fetch_daily_freebies()
            queued = 0
            for post in posts:
                url = post.get("url", "")
                if not url: continue
                domain = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(url).netloc.replace("www.", "")
                for acct_dom in accts:
                    if acct_dom in domain or domain in acct_dom:
                        queue = combined.load_link_queue()
                        if not any(q["url"] == url for q in queue):
                            queue.append({"url": url, "added": datetime.now().strftime("%m/%d %H:%M"),
                                "status": "pending", "result": "", "casino": acct_dom})
                            combined.save_link_queue(queue)
                            queued += 1
                        break
            if queued:
                self.log(f"[LINK] Auto-queued {queued} links from Flood Feed")

        queue = combined.load_link_queue() if hasattr(combined, 'load_link_queue') else []
        if not queue:
            self.log("[LINK] Queue is empty — nothing to process")
            return
        self.log(f"[LINK] Processing {len(queue)} links...")
        self.process_btn.setEnabled(False)
        self.worker = ProcessQueueWorker(queue)
        self.worker.link_done.connect(lambda i, st, rs: self.log(f"[LINK] {st.upper()}: {queue[i]['url'][:40]} -> {rs[:60]}"))
        self.worker.finished.connect(lambda: (self.refresh_queue(), self.process_btn.setEnabled(True)))
        self.worker.start()

# ═══════════════════════════════════════════════════════════════
# SETTINGS TAB
# ═══════════════════════════════════════════════════════════════

class SettingsTab(QWidget):
    check_updates_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        lo = QVBoxLayout(); lo.setContentsMargins(16,16,16,16); lo.setSpacing(10)
        t = QLabel("Settings"); t.setObjectName("title"); lo.addWidget(t)

        # Top row: Bot + Notifications
        top_row = QHBoxLayout()
        bg = QGroupBox("Bot")
        bl = QFormLayout(); bl.setSpacing(6)
        bl.setContentsMargins(8,8,8,8)
        self.hc = QCheckBox("Headless mode")
        self.hc.setChecked(combined.HEADLESS_MODE); bl.addRow(self.hc)
        self.sp = QSpinBox(); self.sp.setRange(10,600); self.sp.setValue(combined.CHECK_INTERVAL); self.sp.setSuffix("s")
        bl.addRow("Interval:",self.sp)
        bg.setLayout(bl); top_row.addWidget(bg)

        ng = QGroupBox("Notifications")
        nl = QVBoxLayout()
        nl.setContentsMargins(8,8,8,8)
        whl = QHBoxLayout(); whl.setSpacing(6)
        self.webhook_input = QLineEdit()
        self.webhook_input.setPlaceholderText("Discord webhook URL")
        whl.addWidget(self.webhook_input)
        test_wh = AnimatedButton("Test"); test_wh.clicked.connect(self.test_webhook); whl.addWidget(test_wh)
        nl.addLayout(whl)
        ng.setLayout(nl); top_row.addWidget(ng)
        lo.addLayout(top_row)

        s = AnimatedButton("Save", variant="gold"); s.clicked.connect(self.save)
        lo.addWidget(s)

        # Data + Advanced row
        mid_row = QHBoxLayout()
        dg = QGroupBox("Data")
        dl = QHBoxLayout(); dl.setSpacing(6)
        dl.setContentsMargins(8,8,8,8)
        exp_btn = AnimatedButton("Export All"); exp_btn.clicked.connect(self.export_data); dl.addWidget(exp_btn)
        imp_btn = AnimatedButton("Import All"); imp_btn.clicked.connect(self.import_data); dl.addWidget(imp_btn)
        cc_btn = AnimatedButton("Clear Cache"); cc_btn.clicked.connect(self.clear_cache); dl.addWidget(cc_btn)
        dg.setLayout(dl); mid_row.addWidget(dg)

        ag2 = QGroupBox("Advanced")
        al2 = QHBoxLayout(); al2.setSpacing(6)
        al2.setContentsMargins(8,8,8,8)
        self.debug_cb = QCheckBox("Debug"); self.debug_cb.setChecked(False); al2.addWidget(self.debug_cb)
        self.verbose_cb = QCheckBox("Verbose"); self.verbose_cb.setChecked(False); al2.addWidget(self.verbose_cb)
        reset_btn = AnimatedButton("Reset All", variant="danger"); reset_btn.clicked.connect(self.reset_all); al2.addWidget(reset_btn)
        ag2.setLayout(al2); mid_row.addWidget(ag2)
        lo.addLayout(mid_row)

        # About + bottom buttons
        bot_row = QHBoxLayout(); bot_row.setSpacing(12)
        ag = QGroupBox("About")
        al = QHBoxLayout(ag); al.setSpacing(14)
        al.setContentsMargins(8,8,8,8)
        lf = BASE_DIR / "license.dat"
        license_info = "No license"
        if lf.exists():
            try:
                with open(lf) as f: ld = json.load(f)
                license_info = f"{ld.get('key','N/A')}  |  {ld.get('tier','Premium')}"
            except: license_info = "Corrupted"
        al.addWidget(QLabel(f"{APP_VERSION}  |  {license_info}"))
        l = QLabel('<a href="https://claimscasino.com/terms" style="color:#FFD700;text-decoration:none;">Terms</a>')
        l.setOpenExternalLinks(True); al.addWidget(l)
        al.addWidget(QLabel("© 2026 Claims Casino"))
        bot_row.addWidget(ag)
        ag.setMinimumHeight(42)

        bb = QHBoxLayout(); bb.setSpacing(8)
        cu = AnimatedButton("Check Updates", variant="gold"); cu.clicked.connect(self.check_updates_requested.emit); bb.addWidget(cu)
        su = AnimatedButton("Community"); su.clicked.connect(lambda: webbrowser.open("https://claimscasino.com/support")); bb.addWidget(su)
        bot_row.addLayout(bb)
        lo.addLayout(bot_row)
        lo.addStretch()
        self.setLayout(lo)

    def save(self):
        combined.HEADLESS_MODE = self.hc.isChecked()
        combined.CHECK_INTERVAL = self.sp.value()
        QMessageBox.information(self,"Saved","Settings saved.")

    def export_data(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Export All Data", str(BASE_DIR / "backup.json"), "JSON Files (*.json)")
        if not fn: return
        try:
            data = {
                "accounts": combined.load_accounts(),
                "schedule": combined.load_claim_schedule(),
                "streamers": combined.load_streamers() if hasattr(combined, 'load_streamers') else [],
                "queue": combined.load_link_queue() if hasattr(combined, 'load_link_queue') else [],
                "exported_at": datetime.now().isoformat()
            }
            with open(fn, 'w') as f: json.dump(data, f, indent=2)
            QMessageBox.information(self, "Exported", f"All data exported to {Path(fn).name}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))

    def import_data(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Import All Data", str(BASE_DIR), "JSON Files (*.json)")
        if not fn: return
        try:
            with open(fn) as f: data = json.load(f)
            if "accounts" in data:
                combined.save_accounts(data["accounts"])
            if "schedule" in data:
                combined.save_claim_schedule(data["schedule"])
            if "streamers" in data and hasattr(combined, 'save_streamers'):
                combined.save_streamers(data["streamers"])
            if "queue" in data and hasattr(combined, 'save_link_queue'):
                combined.save_link_queue(data["queue"])
            QMessageBox.information(self, "Imported", f"Data restored from {Path(fn).name}")
        except Exception as e:
            QMessageBox.warning(self, "Import Failed", str(e))

    def clear_cache(self):
        count = 0
        for f in BASE_DIR.glob("*.dat"):
            try: f.unlink(); count += 1
            except: pass
        for f in BASE_DIR.glob("*.tmp"):
            try: f.unlink(); count += 1
            except: pass
        QMessageBox.information(self, "Cache Cleared", f"Removed {count} temp files")

    def test_webhook(self):
        url = self.webhook_input.text().strip()
        if not url: return
        try:
            r = combined.requests.post(url, json={"content": "Claims Casino test ping"}, timeout=8)
            if r.status_code in (200, 204):
                QMessageBox.information(self, "Webhook", "Test sent successfully")
            else:
                QMessageBox.warning(self, "Webhook", f"HTTP {r.status_code}")
        except Exception as e:
            QMessageBox.warning(self, "Webhook", str(e))

    def reset_all(self):
        if QMessageBox.question(self, "Reset",
            "Clear ALL accounts, schedule, streamers, and queue?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        if QMessageBox.question(self, "Confirm",
            "Are you absolutely sure?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        combined.save_accounts({})
        combined.save_claim_schedule({})
        if hasattr(combined, 'save_streamers'):
            combined.save_streamers([])
        if hasattr(combined, 'save_link_queue'):
            combined.save_link_queue([])
        QMessageBox.information(self, "Reset", "All data cleared")

# ═══════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Claims Casino")
        self.setMinimumSize(900, 600)
        self.resize(1200, 780)

        logo_path = Path(getattr(sys, "_MEIPASS", BASE_DIR)) / "assets" / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        # Start local IPC server for Chrome step recorder
        if hasattr(combined, 'start_ipc_server'):
            combined.start_ipc_server()

        c = QWidget(); self.setCentralWidget(c)
        main_lo = QVBoxLayout(c); main_lo.setContentsMargins(0,0,0,0); main_lo.setSpacing(0)

        # ═══ Custom title bar (64px) ═══
        tb = QFrame()
        tb.setObjectName("titleBar")
        tb.setFixedHeight(64)
        tb.setStyleSheet("#titleBar{background:#0d0d14;}")
        tbl = QHBoxLayout(tb); tbl.setContentsMargins(8,0,8,0); tbl.setSpacing(8)

        logo_lbl = QLabel()
        if logo_path.exists():
            px = QPixmap(str(logo_path)).scaled(36,36,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
            logo_lbl.setPixmap(px)
        else:
            logo_lbl.setText("CC")
            logo_lbl.setStyleSheet("color:#FFD700;font-size:20px;font-weight:700;")
        logo_lbl.setFixedSize(40,40)
        tbl.addWidget(logo_lbl)

        brand_frame = QWidget()
        brand_frame.setStyleSheet("background:transparent;")
        bfl = QVBoxLayout(brand_frame); bfl.setContentsMargins(0, 4, 0, 4); bfl.setSpacing(0)
        brand = QLabel("CLAIMS CASINO")
        brand.setStyleSheet("color:#FFD700;font-size:18px;font-weight:700;letter-spacing:1px;")
        bfl.addWidget(brand)
        sub = QLabel("Automation Suite  " + APP_VERSION)
        sub.setStyleSheet("color:#888;font-size:10px;font-weight:400;")
        bfl.addWidget(sub)
        tbl.addWidget(brand_frame)

        tbl.addStretch()

        # Window control buttons (modern rounded style)
        btn_style = "QPushButton{background:rgba(255,255,255,0.02);color:#aaa;border-radius:8px;font-size:16px;font-weight:600;border:1px solid rgba(255,255,255,0.04);}"
        btn_style_h = "QPushButton:hover{background:rgba(255,255,255,0.06);color:#fff;border-color:rgba(255,215,0,0.15);}"

        min_btn = QPushButton("\u2014")
        min_btn.setFixedSize(42,30)
        min_btn.setStyleSheet(btn_style + btn_style_h)
        min_btn.clicked.connect(self.showMinimized)

        max_btn = QPushButton("\u25a1")
        max_btn.setFixedSize(42,30)
        max_btn.setStyleSheet(btn_style + btn_style_h)
        max_btn.clicked.connect(lambda: self.showMaximized() if not self.isMaximized() else self.showNormal())

        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(42,30)
        close_btn.setStyleSheet("QPushButton{background:rgba(255,255,255,0.02);color:#aaa;border-radius:8px;font-size:15px;font-weight:600;border:1px solid rgba(255,255,255,0.04);}"
                                "QPushButton:hover{background:rgba(239,68,68,0.6);color:#fff;border-color:rgba(239,68,68,0.4);}")
        close_btn.clicked.connect(self.close)

        tbl.addWidget(min_btn); tbl.addWidget(max_btn); tbl.addWidget(close_btn)
        main_lo.addWidget(tb)

        # ═══ Body: sidebar + content ═══
        body = QWidget()
        bl = QHBoxLayout(body); bl.setContentsMargins(0,0,0,0); bl.setSpacing(0)

        # Sidebar: custom layout with nav pinned above, Settings pinned to bottom
        sidebar_w = QWidget()
        sidebar_w.setObjectName("sidebar")
        sl = QVBoxLayout(sidebar_w); sl.setContentsMargins(0,0,0,0); sl.setSpacing(0)

        nav_items = ["\U0001f4cb  License", "\U0001f4ca  Dashboard", "\U0001f464  Profiles", "\U0001f3b0  Daily SC", "\U0001f3ac  Streamer Sniper", "\U0001f517  Link Automation"]
        self.nav_btns = []
        for i, text in enumerate(nav_items):
            b = QPushButton(text)
            b.setCheckable(True)
            b.clicked.connect(lambda checked, idx=i: self.on_page_change(idx))
            sl.addWidget(b)
            self.nav_btns.append(b)

        sl.addStretch()

        sep = QFrame()
        sep.setObjectName("navsep")
        sl.addWidget(sep)

        self.settings_btn = QPushButton("\u2699  Settings")
        self.settings_btn.setCheckable(True)
        self.settings_btn.clicked.connect(lambda: self.on_page_change(6))
        sl.addWidget(self.settings_btn)

        bl.addWidget(sidebar_w)

        self.stack = QStackedWidget()
        self.lt = LicenseTab()
        self.dt = DashboardTab()
        self.pt = ProfilesTab()
        self.dst = DailySCTab()
        self.sst = StreamerSniperTab()
        self.lat = LinkAutomationTab()
        self.ste = SettingsTab()
        # Wire up check updates
        self.ste.check_updates_requested.connect(lambda: self.check_up(silent=False))
        self.stack.addWidget(self.lt)   # 0
        self.stack.addWidget(self.dt)   # 1
        self.stack.addWidget(self.pt)   # 2
        self.stack.addWidget(self.dst)  # 3
        self.stack.addWidget(self.sst)  # 4
        self.stack.addWidget(self.lat)  # 5
        self.stack.addWidget(self.ste)  # 6
        bl.addWidget(self.stack)
        self.on_page_change(0)

        main_lo.addWidget(body)

        sb = QStatusBar(); self.setStatusBar(sb)
        self.sl = QLabel("● OFFLINE")
        self.sl.setStyleSheet("color:#ef4444;font-weight:700;padding:0 12px;")
        sb.addWidget(self.sl)
        self.cl = QLabel("Claims: 0")
        self.cl.setStyleSheet("color:#888;padding:0 12px;")
        sb.addWidget(self.cl)
        self.stl = QLabel("SC: $0.00")
        self.stl.setStyleSheet("color:#FFD700;font-weight:600;padding:0 12px;")
        sb.addWidget(self.stl)
        vl = QLabel(APP_VERSION)
        vl.setStyleSheet("color:#555;padding:0 12px;")
        sb.addPermanentWidget(vl)

        # Tray
        self.tray = QSystemTrayIcon(self)
        if logo_path.exists():
            px = QPixmap(str(logo_path)).scaled(32,32,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
            self.tray.setIcon(QIcon(px))
        else:
            px = QPixmap(32,32); px.fill(QColor("#0d0d14"))
            p = QPainter(px); p.setBrush(QColor("#FFD700")); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(2,2,28,28); p.setFont(QFont("Arial",16,700)); p.setPen(QColor("#0d0d14"))
            p.drawText(px.rect(),Qt.AlignmentFlag.AlignCenter,"CC"); p.end()
            self.tray.setIcon(QIcon(px))

        tm = QMenu()
        tm.addAction("Show", self.show)
        tm.addAction("Hide", self.hide_to_tray)
        tm.addSeparator()
        tm.addAction("Exit", QApplication.quit)
        self.tray.setContextMenu(tm)
        self.tray.setToolTip("Claims Casino")
        self.tray.activated.connect(lambda r: self.show() if r==QSystemTrayIcon.ActivationReason.DoubleClick else None)

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.refresh_st)
        self.status_timer.start(2000)

        QTimer.singleShot(3000, lambda: self.check_up(silent=True))

        # Center on screen
        self.move(QApplication.primaryScreen().geometry().center() - self.rect().center())

    def on_page_change(self, idx):
        if idx < 0 or idx >= self.stack.count(): return
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self.nav_btns):
            btn.setChecked(i == idx)
        self.settings_btn.setChecked(idx == 6)

    def refresh_st(self):
        with combined.state_lock: s = dict(combined.state)
        st = s.get("bot_status","offline")
        if st=="online":
            self.sl.setText("● ONLINE")
            self.sl.setStyleSheet("color:#22c55e;font-weight:700;padding:0 12px;")
        else:
            self.sl.setText("● OFFLINE")
            self.sl.setStyleSheet("color:#ef4444;font-weight:700;padding:0 12px;")
        self.cl.setText(f"Claims: {s.get('claimed',0)}")
        self.stl.setText(f"SC: ${s.get('sc_total',0):.2f}")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() <= 56:
            self.dragPos = e.globalPosition().toPoint()
            e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and self.dragPos is not None:
            self.move(self.pos() + e.globalPosition().toPoint() - self.dragPos)
            self.dragPos = e.globalPosition().toPoint()
            e.accept()

    def mouseReleaseEvent(self, e):
        self.dragPos = None

    def hide_to_tray(self):
        self.hide(); self.tray.show()
        self.tray.showMessage("Claims Casino","Minimized to tray.",QSystemTrayIcon.MessageIcon.Information,2000)

    def closeEvent(self, e):
        if self.tray.isVisible(): self.hide_to_tray(); e.ignore()
        else: e.accept()

    def check_up(self, silent=False):
        try:
            r = combined.requests.get(UPDATE_MANIFEST_URL, timeout=8)
            if r.status_code != 200:
                if not silent: QMessageBox.information(self, "Updater", "Could not check for updates.")
                return
            manifest = r.json()
            tag = manifest.get("version", "v0.0.0")
            dl_url = manifest.get("url", "")
            size_bytes = manifest.get("size", 0)
            if tag <= APP_VERSION or not dl_url:
                if not silent: QMessageBox.information(self, "Updater", "No new updates available.")
                return
            mb = size_bytes / 1048576
            if QMessageBox.question(self, "Updater",
                f"Claims Casino {tag} available ({mb:.1f} MB).\nDownload and install now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
            self.download_update(dl_url, tag)
        except Exception as e:
            if not silent: QMessageBox.warning(self, "Updater", f"Update check failed:\n{e}")

    def download_update(self, url, tag):
        pd = QProgressDialog(f"Updater — Downloading {tag}...", "Cancel", 0, 0, self)
        pd.setWindowTitle("Updater"); pd.setCancelButton(None)
        pd.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        pd.setFixedSize(360, 100); pd.show()
        tmp = BASE_DIR / f"CasinoBot_{tag}.exe"
        try:
            r = combined.requests.get(url, stream=True, timeout=60)
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 65536
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pd.setValue(int(downloaded / total * 100))
                            pd.setLabelText(f"Updater — {downloaded*100//total}%")
            pd.close()
            exe = sys.executable
            ps = (
                f'Start-Sleep -Seconds 2; '
                f'Copy-Item -Path "{tmp}" -Destination "{exe}" -Force; '
                f'Start-Process -FilePath "{exe}"; '
                f'Remove-Item -Path "{tmp}" -Force'
            )
            subprocess.Popen(["powershell", "-Command", ps], creationflags=subprocess.CREATE_NO_WINDOW)
            QApplication.quit()
        except Exception as e:
            pd.close()
            if tmp.exists(): tmp.unlink()
            QMessageBox.warning(self, "Updater", f"Download failed:\n{e}")

# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_SS)

    # Anti-debug check (kill switch)
    if not combined.check_anti_debug():
        mb = QMessageBox(QMessageBox.Icon.Critical, "Security", "Debug environment detected. Application cannot run.")
        mb.exec()
        sys.exit(1)

    # Check license
    lf = BASE_DIR / "license.dat"
    ok = False
    license_key = ""
    if lf.exists():
        try:
            with open(lf) as f: ld = json.load(f)
            license_key = ld.get("key", "")
            hwid = ld.get("hwid", "")
            # Online re-validation (silent, periodic)
            try:
                if hwid:
                    r = combined.requests.post(LICENSE_SERVER_URL, json={"key": license_key, "hwid": hwid}, timeout=3)
                    if r.status_code == 200 and r.json().get("valid"):
                        ok = True
                    # If server says invalid, fall through to local check
                else:
                    ok = combined.validate_license_key(license_key).get("valid")
            except:
                ok = combined.validate_license_key(license_key).get("valid")
        except:
            pass

    if not ok:
        dlg = LicenseDialog()
        if dlg.exec() != QDialog.DialogCode.Accepted: sys.exit(1)

    t = threading.Thread(target=combined.daily_freebies_loop, daemon=True); t.start()
    w = MainWindow(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
