from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

UserModel = get_user_model()


class PhoneBackend(ModelBackend):
    """
    Telefon raqamni tozalab autentifikatsiya qilish.
    Foydalanuvchi +998 90 123 45 67 kiritsa, 998901234567 ga aylantiriladi.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None:
            return None

        # Telefon raqamni tozalash (faqat raqamlar)
        phone = ''.join(filter(str.isdigit, str(username)))

        try:
            user = UserModel.objects.get(phone=phone)
        except UserModel.DoesNotExist:
            UserModel().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
