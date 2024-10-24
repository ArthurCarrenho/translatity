# main_window.py
import os
import logging
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QTextEdit, QProgressBar, 
                             QListWidget, QMessageBox, QInputDialog, QLineEdit, QComboBox,
                             QSplitter, QCheckBox, QListWidgetItem)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QColor
from pathlib import Path
from datetime import datetime
from .widgets import DraggableListWidget, FilePreview
from .themes import apply_theme, get_color
from translation.translator import SRTTranslator

class TranslationWorker(QThread):
    progress_update = pyqtSignal(int, int)
    status_update = pyqtSignal(str)
    translation_complete = pyqtSignal(str, str)
    translation_error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, translator, input_file, output_file, input_lang, output_lang, context):
        super().__init__()
        self.translator = translator
        self.input_file = input_file
        self.output_file = output_file
        self.input_lang = input_lang
        self.output_lang = output_lang
        self.context = context
        self.is_cancelled = False

    def run(self):
        try:
            self.translator.translate_file(
                self.input_file,
                self.output_file,
                progress_callback=self.progress_update.emit,
                status_callback=self.status_update.emit,
                input_lang=self.input_lang,
                output_lang=self.output_lang,
                context=self.context,
                cancel_check=self.check_cancelled
            )
            if not self.is_cancelled:
                self.translation_complete.emit(self.input_file, self.output_file)
        except Exception as e:
            self.translation_error.emit(str(e))
        finally:
            self.finished.emit()

    def check_cancelled(self):
        return self.is_cancelled

    def cancel(self):
        self.is_cancelled = True

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Translatity")
        self.setGeometry(100, 100, 1000, 700)
        self.setAcceptDrops(True)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.api_keys = []
        self.file_queue = []
        self.failed_files = set()
        self.is_translation_running = False
        self.settings = QSettings("ArthurCarrenho", "Translatity")
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        # Main layout split
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(splitter)

        # Left panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # File selection
        file_layout = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        self.select_file_button = QPushButton("Select SRT File(s)")
        self.select_file_button.clicked.connect(self.select_files)
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.select_file_button)
        left_layout.addLayout(file_layout)

        # File queue
        self.queue_list = DraggableListWidget(self)
        self.queue_list.items_reordered.connect(self.update_file_queue)
        self.queue_list.item_deleted.connect(self.remove_file_from_queue)
        left_layout.addWidget(QLabel("Translation Queue:"))
        left_layout.addWidget(self.queue_list)

        # Queue management buttons
        queue_buttons_layout = QHBoxLayout()
        
        self.retry_button = QPushButton("Retry Failed Files")
        self.retry_button.clicked.connect(self.retry_failed_files)
        self.retry_button.setEnabled(False)
        queue_buttons_layout.addWidget(self.retry_button)
        
        self.clear_queue_button = QPushButton("Clear Queue")
        self.clear_queue_button.clicked.connect(self.clear_queue)
        queue_buttons_layout.addWidget(self.clear_queue_button)
        
        left_layout.addLayout(queue_buttons_layout)

        # Language selection
        lang_layout = QHBoxLayout()
        self.input_lang = QComboBox()
        self.output_lang = QComboBox()
        languages = ["English", "Portuguese", "Spanish", "French", "German", "Italian", "Japanese", "Korean", "Chinese"]
        self.input_lang.addItems(languages)
        self.output_lang.addItems(languages)
        lang_layout.addWidget(QLabel("From:"))
        lang_layout.addWidget(self.input_lang)
        lang_layout.addWidget(QLabel("To:"))
        lang_layout.addWidget(self.output_lang)
        left_layout.addLayout(lang_layout)

        # Context input
        self.context_input = QTextEdit()
        self.context_input.setPlaceholderText("Enter context for translation (e.g., movie genre, character names)")
        left_layout.addWidget(QLabel("Translation Context:"))
        left_layout.addWidget(self.context_input)

        # Translation button
        self.translate_button = QPushButton("Translate Queue")
        self.translate_button.clicked.connect(self.start_translation_queue)
        left_layout.addWidget(self.translate_button)

        # Progress bar
        self.progress_bar = QProgressBar()
        left_layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready")
        left_layout.addWidget(self.status_label)

        splitter.addWidget(left_panel)

        # Right panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # API Key management
        right_layout.addWidget(QLabel("API Keys:"))
        self.api_key_list = QListWidget()
        self.api_key_list.itemDoubleClicked.connect(self.edit_api_key)
        right_layout.addWidget(self.api_key_list)

        key_buttons_layout = QHBoxLayout()
        self.add_key_button = QPushButton("Add API Key")
        self.add_key_button.clicked.connect(self.add_api_key)
        self.remove_key_button = QPushButton("Remove API Key")
        self.remove_key_button.clicked.connect(self.remove_api_key)
        key_buttons_layout.addWidget(self.add_key_button)
        key_buttons_layout.addWidget(self.remove_key_button)
        right_layout.addLayout(key_buttons_layout)

        # File preview
        self.file_preview = FilePreview()
        right_layout.addWidget(QLabel("File Preview:"))
        right_layout.addWidget(self.file_preview)

        splitter.addWidget(right_panel)

        # Connect queue selection to preview
        self.queue_list.currentItemChanged.connect(self.update_file_preview)

    def select_files(self):
        file_names, _ = QFileDialog.getOpenFileNames(self, "Select SRT File(s)", "", "SRT Files (*.srt)")
        if file_names:
            self.file_queue.extend(file_names)
            self.update_queue_list()
            self.file_label.setText(f"{len(self.file_queue)} file(s) in queue")

    def clear_queue(self):
        if self.queue_list.count() > 0:
            reply = QMessageBox.question(
                self, 
                "Clear Queue", 
                "Are you sure you want to clear the queue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.queue_list.clear()
                self.file_queue.clear()
                self.failed_files.clear()
                self.retry_button.setEnabled(False)
                self.file_label.setText("No file selected")
                self.file_preview.setPlainText("")
                self.progress_bar.setValue(0)
                self.update_status("Queue cleared")

    def update_queue_list(self):
        self.queue_list.clear()
        for i, file in enumerate(self.file_queue):
            item = QListWidgetItem(Path(file).name)
            if i in self.failed_files:
                item.setBackground(get_color('error'))
            self.queue_list.addItem(item)
        self.enable_retry_if_needed()

    def enable_retry_if_needed(self):
        has_failed_files = len(self.failed_files) > 0
        self.retry_button.setEnabled(has_failed_files and not self.is_translation_running)
        if has_failed_files:
            logging.info(f"Retry button enabled. Failed files: {self.failed_files}")

    def retry_failed_files(self):
        if not self.failed_files:
            return

        failed_indices = sorted(list(self.failed_files), reverse=True)
        retry_files = []
        
        for index in failed_indices:
            if index < len(self.file_queue):
                file_path = self.file_queue[index]
                retry_files.append(file_path)
                logging.info(f"Moving failed file for retry: {file_path}")
                del self.file_queue[index]
                item = self.queue_list.takeItem(index)
                if item:
                    item.setBackground(QColor())

        self.file_queue.extend(retry_files)
        self.update_queue_list()
        
        self.failed_files.clear()
        self.retry_button.setEnabled(False)
        
        if not self.is_translation_running:
            self.start_translation_queue()

    def update_file_queue(self):
        new_queue = []
        for i in range(self.queue_list.count()):
            item = self.queue_list.item(i)
            file_path = next((f for f in self.file_queue if Path(f).name == item.text()), None)
            if file_path:
                new_queue.append(file_path)
        self.file_queue = new_queue

    def remove_file_from_queue(self, index):
        if 0 <= index < len(self.file_queue):
            del self.file_queue[index]
            new_failed = set()
            for failed_index in self.failed_files:
                if failed_index > index:
                    new_failed.add(failed_index - 1)
                elif failed_index < index:
                    new_failed.add(failed_index)
            self.failed_files = new_failed
        self.update_queue_list()

    def update_file_preview(self, current, previous):
        if current:
            file_path = self.file_queue[self.queue_list.row(current)]
            self.file_preview.load_file(file_path)

    def start_translation_queue(self):
        if not self.file_queue:
            QMessageBox.warning(self, "Error", "Please select at least one SRT file first.")
            return

        api_keys = self.get_api_keys()
        if not api_keys:
            QMessageBox.warning(self, "Error", "Please add at least one API key.")
            return

        self.is_translation_running = True
        self.translator = SRTTranslator(api_keys)
        self.translator.key_rotator.key_changed.connect(self.highlight_current_api_key)
        self.current_file_index = 0
        self.highlight_current_api_key(0)
        self.translate_button.setText("Cancel Translation")
        self.translate_button.clicked.disconnect()
        self.translate_button.clicked.connect(self.cancel_translation)
        self.retry_button.setEnabled(False)
        self.translate_next_file()

    def translate_next_file(self):
        if self.current_file_index < len(self.file_queue):
            input_file = self.file_queue[self.current_file_index]
            output_file = f"output_{Path(input_file).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt"
            
            self.translation_worker = TranslationWorker(
                self.translator,
                input_file,
                output_file,
                self.input_lang.currentText(),
                self.output_lang.currentText(),
                self.context_input.toPlainText()
            )
            self.translation_worker.progress_update.connect(self.update_progress)
            self.translation_worker.status_update.connect(self.update_status)
            self.translation_worker.translation_complete.connect(self.file_translation_complete)
            self.translation_worker.translation_error.connect(self.translation_error)
            self.translation_worker.finished.connect(self.translation_finished)
            
            self.translation_worker.start()
            self.progress_bar.setValue(0)
            self.update_status(f"Translating: {Path(input_file).name}")
            if self.current_file_index < self.queue_list.count():
                item = self.queue_list.item(self.current_file_index)
                if item:
                    item.setBackground(get_color('highlight'))
        else:
            self.queue_translation_complete()

    def cancel_translation(self):
        if hasattr(self, 'translation_worker'):
            self.translation_worker.cancel()
            self.update_status("Translation cancelled")
            self.translation_cancelled()

    def translation_cancelled(self):
        self.is_translation_running = False
        self.translate_button.setText("Translate Queue")
        self.translate_button.clicked.disconnect()
        self.translate_button.clicked.connect(self.start_translation_queue)
        self.enable_retry_if_needed()
        QMessageBox.information(self, "Translation Cancelled", "The translation process has been cancelled.")

    def file_translation_complete(self, input_file, output_file):
        if self.current_file_index < self.queue_list.count():
            item = self.queue_list.item(self.current_file_index)
            if item:
                item.setBackground(get_color('success'))
        self.update_status(f"Completed: {Path(input_file).name}")

    def translation_error(self, error_message):
        self.update_status(f"Error: {error_message}")
        if self.current_file_index < self.queue_list.count():
            item = self.queue_list.item(self.current_file_index)
            if item:
                item.setBackground(get_color('error'))
                self.failed_files.add(self.current_file_index)
                self.enable_retry_if_needed()
                logging.error(f"Translation failed for file at index {self.current_file_index}: {error_message}")

    def translation_finished(self):
        if hasattr(self, 'translation_worker'):
            self.current_file_index += 1
            if self.current_file_index < len(self.file_queue):
                QTimer.singleShot(100, self.translate_next_file)
            else:
                self.is_translation_running = False
                self.queue_translation_complete()
                self.enable_retry_if_needed()

    def queue_translation_complete(self):
        self.is_translation_running = False
        self.update_status("Translation queue completed")
        self.translate_button.setText("Translate Queue")
        self.translate_button.clicked.disconnect()
        self.translate_button.clicked.connect(self.start_translation_queue)
        
        if self.failed_files:
            message = f"Queue completed with {len(self.failed_files)} failed files. Use 'Retry Failed Files' to attempt translation again."
            self.enable_retry_if_needed()
        else:
            message = "All files in the queue have been translated successfully."
        
        QMessageBox.information(self, "Queue Complete", message)

    def update_progress(self, current, total):
        self.progress_bar.setValue(int((current / total) * 100))

    def update_status(self, status):
        self.status_label.setText(status)

    def load_settings(self):
        self.api_keys = self.settings.value("api_keys", [], type=list)
        self.update_api_key_list()
        self.input_lang.setCurrentText(self.settings.value("input_lang", "English", type=str))
        self.output_lang.setCurrentText(self.settings.value("output_lang", "Portuguese", type=str))
        self.context_input.setPlainText(self.settings.value("context", "", type=str))

    def save_settings(self):
        self.settings.setValue("api_keys", self.api_keys)
        self.settings.setValue("input_lang", self.input_lang.currentText())
        self.settings.setValue("output_lang", self.output_lang.currentText())
        self.settings.setValue("context", self.context_input.toPlainText())

    def update_api_key_list(self):
        self.api_key_list.clear()
        for key in self.api_keys:
            item = QListWidgetItem(self.mask_api_key(key))
            self.api_key_list.addItem(item)

    def add_api_key_to_list(self, key):
        self.api_keys.append(key)
        self.update_api_key_list()

    def mask_api_key(self, key):
        return f"{key[:5]}...{key[-5:]}"

    def add_api_key(self):
        key, ok = QInputDialog.getText(self, "Add API Key", "Enter Gemini API Key:", QLineEdit.EchoMode.Password)
        if ok and key:
            self.add_api_key_to_list(key)
            self.save_settings()

    def edit_api_key(self, item):
        index = self.api_key_list.row(item)
        old_key = self.api_keys[index]
        new_key, ok = QInputDialog.getText(self, "Edit API Key", "Enter new Gemini API Key:", QLineEdit.EchoMode.Password, text=old_key)
        if ok and new_key:
            self.api_keys[index] = new_key
            self.update_api_key_list()
            self.save_settings()

    def remove_api_key(self):
        current_item = self.api_key_list.currentItem()
        if current_item:
            index = self.api_key_list.row(current_item)
            del self.api_keys[index]
            self.update_api_key_list()
            self.save_settings()

    def get_api_keys(self):
        return self.api_keys

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.srt'):
                self.file_queue.append(file_path)
        self.update_queue_list()
        self.file_label.setText(f"{len(self.file_queue)} file(s) in queue")

    def highlight_current_api_key(self, index):
        for i in range(self.api_key_list.count()):
            item = self.api_key_list.item(i)
            if i == index:
                item.setBackground(get_color('highlight'))
            else:
                item.setBackground(get_color('background'))

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)