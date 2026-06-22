from django.contrib.auth.base_user import BaseUserManager


class CustomUserManager(BaseUserManager):
    """
    Telefon raqamni Login sifatida ishlatish uchun Manager.
    """

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError('Telefon raqam kiritilishi shart')

        # Telefonni tozalash (faqat raqamlar)
        phone = ''.join(filter(str.isdigit, str(phone)))

        user = self.model(phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password, **extra_fields):
        """
        Terminaldan Super Admin yaratish uchun.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        # Super Adminda Organization va Role bo'lmaydi, lekin majburiy maydonlarni to'ldiramiz
        extra_fields.setdefault('role', 'super_admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone, password, **extra_fields)