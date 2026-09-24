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

        # Telefon raqam yoki matnli login
        clean_input = str(username).strip()
        phone_digits = ''.join(filter(str.isdigit, clean_input))

        user = UserModel.objects.filter(phone=clean_input).first()
        if not user and phone_digits:
            user = UserModel.objects.filter(phone=phone_digits).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        UserModel().set_password(password)
        return None
