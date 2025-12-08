import os
import sys
import random
import requests
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageQt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QMessageBox, QGridLayout,
    QProgressBar
)
from PySide6.QtCore import Qt, QSize, QThread, Signal, Slot
from PySide6.QtGui import QPixmap, QFont
import qtmodern.styles
import qtmodern.windows

# ------------------------------------------------------
# إعداد المسار
if getattr(sys, 'frozen', False):
    # عند التشغيل كـ EXE، نستخدم المجلد الذي تم تجميع البرنامج فيه
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ------------------------------------------------------
# إعداد أحجام الصور
SIZE_MAP = {
    "SD (512x512)": (512, 512),
    "HD (768x768)": (768, 768),
    "FHD (1024x1024)": (1024, 1024)
}

# ------------------------------------------------------
# فئة العامل (الخيط) لتوليد الصور
class ImageWorker(QThread):
    # إشارات (Signals) للتواصل مع الواجهة الرئيسية
    result_ready = Signal(list, str) # قائمة بالصور والمسار وحجم الصورة
    error_occurred = Signal(str) # رسالة خطأ
    progress_update = Signal(int) # تحديث التقدم (رقم الصورة الحالية)

    def __init__(self, prompt: str, size_label: str, count: int = 4):
        super().__init__()
        self.prompt = prompt
        self.size_label = size_label
        self.count = count

    def run(self):
        """تنفيذ عملية التوليد التي تحظر الواجهة في خيط منفصل."""
        images = []
        width, height = SIZE_MAP.get(self.size_label, (768, 768))

        style_modifiers_groups = [
            ["dynamic wide-angle shot", "low-angle perspective", "high-angle perspective", "close-up macro"],
            ["cinematic volumetric lighting", "soft studio lighting", "dramatic neon light", "sunset golden hour"],
            ["vibrant colors and detailed", "monochromatic moody atmosphere", "futuristic aesthetic", "minimalist and clean"]
        ]
        
        quality_modifiers = "professional photography, octane render, trending on artstation, ultra quality, 8k"

        print(f"\n=====================================")
        print(f"🔄 بدء توليد {self.count} صور بحجم {width}x{height}...")

        for i in range(self.count):
            self.progress_update.emit(i + 1)
            
            try:
                print(f"  [صورة {i+1}/{self.count}] ...")

                random_seed = random.randint(1000000, 9999999)
                
                modifier_parts = [random.choice(group) for group in style_modifiers_groups]
                
                unique_prompt = f"{self.prompt}, {', '.join(modifier_parts)}, {quality_modifiers}, seed:{random_seed}"

                # *** NOTE: Pollinations API might be slow or unstable, causing timeouts ***
                url = f"https://image.pollinations.ai/prompt/{unique_prompt}"
                response = requests.get(url, timeout=60)
                response.raise_for_status()
                
                image = Image.open(BytesIO(response.content))
                
                # إنشاء QPixmap بأمان لاستخدامه في خيط الواجهة
                qimage = ImageQt.ImageQt(image.resize((width, height)))
                pixmap = QPixmap.fromImage(qimage)
                
                # **الحفظ التلقائي**
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                image_path = os.path.join(OUTPUT_DIR, f"{timestamp}_{self.size_label.split(' ')[0]}_{i+1}.png")
                image.save(image_path)
                
                images.append((image_path, pixmap))
                
            except requests.exceptions.RequestException as req_err:
                error_msg = f"❌ خطأ في الاتصال (صورة {i+1}): {req_err}"
                print(error_msg)
                # نرسل الخطأ، ثم نرسل الصور التي تم توليدها حتى الآن
                self.error_occurred.emit(error_msg)
                self.result_ready.emit(images, self.size_label) 
                return
            except Exception as e:
                error_msg = f"❌ خطأ غير متوقع (صورة {i+1}): {e}"
                print(error_msg)
                self.error_occurred.emit(error_msg)
                self.result_ready.emit(images, self.size_label)
                return
        
        print(f"=====================================\n")
        self.result_ready.emit(images, self.size_label)

# ------------------------------------------------------
# فئة النافذة الرئيسية
class ImageGeneratorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("✨ AI Image Creator Pro - YASSIR HOUM Edition")
        self.resize(1100, 750)
        
        self.size_var = list(SIZE_MAP.keys())[1]
        self.image_cache = []
        self.worker_thread = None

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)

        self.create_controls()
        self.create_progress_bar()
        self.create_preview_area()
        self.create_footer()

    def create_progress_bar(self):
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(4)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("جاري التحميل... يرجى الانتظار ⏳ | الصورة %v من %m")
        self.progress_bar.setStyleSheet("QProgressBar { background-color: #333333; color: white; border: 1px solid #FFD700; border-radius: 5px; } QProgressBar::chunk { background-color: #00A388; }")
        self.progress_bar.hide()
        
        self.main_layout.addWidget(self.progress_bar)

    def open_output_folder(self):
        """يفتح مجلد outputs في مستكشف الملفات."""
        try:
            path = os.path.realpath(OUTPUT_DIR)
            
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin':
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')

        except Exception as e:
            QMessageBox.critical(self, "خطأ في فتح المجلد", 
                                 f"فشل فتح المجلد: {OUTPUT_DIR}\nالخطأ: {e}")

    def create_controls(self):
        control_frame = QWidget()
        control_layout = QVBoxLayout(control_frame) 

        name_label = QLabel("YASSIR HOUM")
        name_label.setFont(QFont("Arial", 24, QFont.Weight.Black))
        name_label.setStyleSheet("color: #FFD700;")
        control_layout.addWidget(name_label)
        
        title_label = QLabel("AI Image Creator Pro")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #BB86FC;")
        control_layout.addWidget(title_label)

        input_row = QWidget()
        input_layout = QHBoxLayout(input_row)
        input_layout.setContentsMargins(0, 5, 0, 5) 

        self.prompt_entry = QLineEdit()
        self.prompt_entry.setPlaceholderText("الوصف التفصيلي للصورة...")
        self.prompt_entry.setFont(QFont("Arial", 12))
        self.prompt_entry.setMinimumHeight(35)
        input_layout.addWidget(self.prompt_entry, 3) 

        self.size_combo = QComboBox()
        self.size_combo.addItems(list(SIZE_MAP.keys()))
        self.size_combo.setCurrentText(self.size_var)
        self.size_combo.setMinimumWidth(150)
        self.size_combo.setMinimumHeight(35)
        input_layout.addWidget(self.size_combo, 1) 
        
        self.generate_btn = QPushButton("🎨 توليد الصور (4)")
        self.generate_btn.clicked.connect(self.on_generate)
        self.generate_btn.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.generate_btn.setMinimumWidth(180)
        self.generate_btn.setMinimumHeight(35)
        input_layout.addWidget(self.generate_btn, 1)
        
        control_layout.addWidget(input_row)
        
        folder_btn = QPushButton("📂 فتح مجلد الحفظ (outputs)")
        folder_btn.clicked.connect(self.open_output_folder)
        folder_btn.setFont(QFont("Arial", 10))
        folder_btn.setStyleSheet("QPushButton { background-color: #333333; border: 1px solid #555555; }")
        
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(folder_btn, 1)
        folder_layout.addStretch(1)
        
        control_layout.addLayout(folder_layout)

        self.main_layout.addWidget(control_frame)


    def create_preview_area(self):
        self.preview_area = QWidget()
        self.preview_layout = QGridLayout(self.preview_area)
        self.preview_layout.setSpacing(20)
        
        # رسالة بداية - يتم إضافتها كعنصر تابع لـ self.preview_area مباشرة
        self.initial_label = QLabel("أدخل الوصف واضغط 'توليد' للبدء...")
        self.initial_label.setFont(QFont("Arial", 18))
        self.initial_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_layout.addWidget(self.initial_label, 0, 0, 2, 2)
        
        self.main_layout.addWidget(self.preview_area, 1) 

    def create_footer(self):
        footer_label = QLabel("© 2024 AI Powered | API: Pollinations | Theme: Modern Dark")
        footer_label.setFont(QFont("Arial", 9, QFont.Weight.Normal, italic=True))
        footer_label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        self.main_layout.addWidget(footer_label)

    @Slot()
    def on_generate(self):
        prompt = self.prompt_entry.text().strip()
        size_label = self.size_combo.currentText()
        
        if not prompt:
            QMessageBox.warning(self, "تحذير", "يرجى إدخال وصف أولاً!")
            return

        # 1. مسح الصور القديمة وإظهار رسالة البداية مؤقتاً
        self.clear_preview_area() 
        self.initial_label.hide() # إخفاء رسالة البداية فقط، لا نحذفها
        
        self.generate_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        
        # إنشاء وتشغيل الخيط العامل
        self.worker_thread = ImageWorker(prompt, size_label)
        self.worker_thread.result_ready.connect(self.handle_generation_finished)
        self.worker_thread.error_occurred.connect(self.handle_error)
        self.worker_thread.progress_update.connect(self.update_progress)
        self.worker_thread.start()

    @Slot(int)
    def update_progress(self, current_count):
        self.progress_bar.setValue(current_count)

    @Slot(str)
    def handle_error(self, message):
        # إظهار رسالة الخطأ في الواجهة
        QMessageBox.critical(self, "خطأ في التوليد", message)
        # لا تفعل شيئًا آخر هنا، سيتم التعامل مع الإيقاف في handle_generation_finished

    @Slot(list, str)
    def handle_generation_finished(self, results, size_label):
        """يُستدعى هذا Slot في الخيط الرئيسي بعد انتهاء العامل (أو عند حدوث خطأ فيه)."""
        
        self.progress_bar.hide()
        self.generate_btn.setEnabled(True)
        
        if not results:
            # إذا لم يتم توليد أي صور على الإطلاق بسبب خطأ اتصال في الصورة الأولى
            self.initial_label.show() # إظهار رسالة البداية مجدداً
            return

        # إذا تم توليد صورة واحدة على الأقل، يتم عرضها
        for i, (path, pixmap) in enumerate(results):
            row = i // 2
            col = i % 2
            self.display_thumbnail(path, pixmap, row, col)

        QMessageBox.information(self, "✅ تم بنجاح", f"تم توليد {len(results)} صور ({size_label}) وتم حفظها في مجلد outputs.")

    def display_thumbnail(self, path, pixmap, row, col):
        thumbnail = pixmap.scaled(QSize(400, 400), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        lbl = QLabel()
        lbl.setPixmap(thumbnail)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        lbl.setToolTip("اضغط للعرض بالحجم الكامل")

        lbl.mousePressEvent = lambda event: self.show_full_image(path)
        
        self.preview_layout.addWidget(lbl, row, col)
        
        self.image_cache.append(lbl)

    def show_full_image(self, path):
        win = QMainWindow(self)
        win.setWindowTitle("🖼️ عرض الصورة الكاملة")

        im = Image.open(path)
        qimage = ImageQt.ImageQt(im)
        pixmap = QPixmap.fromImage(qimage)

        screen = QApplication.primaryScreen()
        if screen:
             max_size = screen.availableSize() * 0.9
        else:
             max_size = QSize(1200, 900)

        scaled_pixmap = pixmap.scaled(max_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        lbl = QLabel()
        lbl.setPixmap(scaled_pixmap)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        win.setCentralWidget(lbl)
        win.adjustSize()
        
        mw = qtmodern.windows.ModernWindow(win)
        mw.show()
        
    def clear_preview_area(self):
        """يحذف جميع الصور المصغرة المعروضة، دون حذف initial_label."""
        self.image_cache.clear()
        
        # تمرير عكسي لإزالة جميع العناصر من شبكة العرض
        for i in reversed(range(self.preview_layout.count())):
            layout_item = self.preview_layout.itemAt(i)
            widget = layout_item.widget()
            
            # **هنا التعديل الهام:** نضمن أننا لا نحذف initial_label
            if widget is not self.initial_label and widget is not None:
                widget.deleteLater()
                # إزالة العنصر من التخطيط (ضروري لعدم ترك فجوات)
                self.preview_layout.removeItem(layout_item)
            
        # إخفاء initial_label إذا كانت ظاهرة (لأننا سنبدأ العرض)
        self.initial_label.hide()


# ------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # تطبيق الثيم الحديث
    qtmodern.styles.dark(app)
    
    window = ImageGeneratorWindow()
    mw = qtmodern.windows.ModernWindow(window)
    mw.show()

    sys.exit(app.exec())