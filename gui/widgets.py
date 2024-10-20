from PyQt6.QtWidgets import QListWidget, QPlainTextEdit, QMenu
from PyQt6.QtCore import pyqtSignal, Qt

class DraggableListWidget(QListWidget):
    items_reordered = pyqtSignal()
    item_deleted = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def dropEvent(self, event):
        super().dropEvent(event)
        self.items_reordered.emit()

    def show_context_menu(self, position):
        menu = QMenu()
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.mapToGlobal(position))
        if action == delete_action:
            current_item = self.itemAt(position)
            if current_item:
                row = self.row(current_item)
                self.takeItem(row)
                self.item_deleted.emit(row)

class FilePreview(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)

    def load_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.setPlainText(content[:1000] + "..." if len(content) > 1000 else content)
        except Exception as e:
            self.setPlainText(f"Error loading file: {str(e)}")