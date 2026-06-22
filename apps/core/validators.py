"""
File validation funksiyalari.
Xavfsizlik uchun fayl turini va hajmini tekshirish.
"""
import os
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

def validate_image_extension(value):
    """Faqat rasm fayllari (JPEG, PNG, GIF, WEBP)"""
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    if ext not in valid_extensions:
        raise ValidationError(
            f'Faqat rasm yuklash mumkin! Qo\'llab-quvvatlanadigan formatlar: {", ".join(valid_extensions)}'
        )


def validate_document_extension(value):
    """Hujjatlar (PDF, DOCX, XLSX)"""
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx']
    if ext not in valid_extensions:
        raise ValidationError(
            f'Faqat hujjat yuklash mumkin! Qo\'llab-quvvatlanadigan formatlar: {", ".join(valid_extensions)}'
        )


def validate_receipt_file(value):
    """Chek fayli (PDF yoki rasm)"""
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
    if ext not in valid_extensions:
        raise ValidationError(
            'Chek faqat PDF yoki rasm formatida bo\'lishi kerak!'
        )


def validate_file_size(value, max_size_mb=5):
    """
    Fayl hajmini tekshirish.

    Args:
        value: FileField value
        max_size_mb: Maksimal hajm (MB)
    """
    filesize = value.size
    max_size_bytes = max_size_mb * 1024 * 1024  # MB to bytes

    if filesize > max_size_bytes:
        raise ValidationError(
            f'Fayl hajmi {max_size_mb}MB dan oshmasligi kerak! '
            f'Sizning faylingiz: {filesize / (1024 * 1024):.2f}MB'
        )



@deconstructible
class FileSizeValidator:
    """Custom validator class - serializable for Django migrations"""
    def __init__(self, max_size_mb=5):
        self.max_size_mb = max_size_mb

    def __call__(self, value):
        validate_file_size(value, self.max_size_mb)

    def __eq__(self, other):
        return isinstance(other, FileSizeValidator) and self.max_size_mb == other.max_size_mb


# Material fayllari uchun
def validate_material_file(value):
    """LMS material fayllari"""
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = [
        # Hujjatlar
        '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
        # Rasm
        '.jpg', '.jpeg', '.png', '.gif',
        # Video
        '.mp4', '.avi', '.mov', '.wmv',
        # Audio
        '.mp3', '.wav', '.ogg',
        # Arxiv
        '.zip', '.rar', '.7z'
    ]
    if ext not in valid_extensions:
        raise ValidationError(
            f'Bu fayl turi qo\'llab-quvvatlanmaydi! '
            f'Ruxsat etilgan formatlar: {", ".join(valid_extensions)}'
        )

    # Hajm (maksimal 100MB)
    validate_file_size(value, max_size_mb=100)
