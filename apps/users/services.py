import sys
from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile


def compress_avatar(avatar):
    """
    Rasmni oladi, hajmini kichraytiradi va sifatini optimallashtiradi.
    """
    if not avatar:
        return avatar

    im = Image.open(avatar)

    # 1. RGB ga o'tkazish (PNG bo'lsa)
    if im.mode != 'RGB':
        im = im.convert('RGB')

    # 2. O'lchamni tekshirish (maksimum 800px)
    if im.width > 800:
        output_size = (800, 800)
        im.thumbnail(output_size)

    # 3. Xotiraga yozish (JPEG formatda, 70% sifat)
    output = BytesIO()
    im.save(output, format='JPEG', quality=70)
    output.seek(0)

    # 4. Django File obyektiga aylantirish
    return InMemoryUploadedFile(
        output,
        'ImageField',
        f"{avatar.name.split('.')[0]}.jpg",
        'image/jpeg',
        sys.getsizeof(output),
        None
    )