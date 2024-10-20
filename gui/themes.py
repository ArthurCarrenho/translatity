from PyQt6.QtGui import QColor

def get_color(name, is_dark_mode=False):
    colors = {
        'background': QColor('#2b2b2b') if is_dark_mode else QColor('#ffffff'),
        'text': QColor('#ffffff') if is_dark_mode else QColor('#000000'),
        'highlight': QColor('#4a4a4a') if is_dark_mode else QColor('#fff700'),
        'success': QColor('#006400') if is_dark_mode else QColor('#90EE90'),
        'error': QColor('#8B0000') if is_dark_mode else QColor('#FFB6C1'),
    }
    return colors.get(name, QColor('#000000'))

def apply_theme(window, is_dark_mode):
    if is_dark_mode:
        window.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #ffffff; }
            QTextEdit, QPlainTextEdit, QListWidget { background-color: #363636; border: 1px solid #545454; }
            QPushButton { background-color: #4a4a4a; border: 1px solid #646464; padding: 5px; }
            QPushButton:hover { background-color: #5a5a5a; }
            QProgressBar { border: 1px solid #646464; }
            QProgressBar::chunk { background-color: #3a3a3a; }
            QComboBox { background-color: #4a4a4a; border: 1px solid #646464; }
            QComboBox QAbstractItemView { background-color: #2b2b2b; border: 1px solid #646464; }
        """)
    else:
        window.setStyleSheet("")