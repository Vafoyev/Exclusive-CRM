from django.core.management.base import BaseCommand
from django.conf import settings
from apps.users.models import User
import telebot # pip install pyTelegramBotAPI
import logging

# Telebotni sozlash
# DIQQAT: settings.py da TELEGRAM_BOT_TOKEN bo'lishi kerak
try:
    bot = telebot.TeleBot(settings.TELEGRAM_BOT_TOKEN, parse_mode='HTML')
except Exception:
    bot = None
    print("TELEGRAM_BOT_TOKEN topilmadi yoki xato.")

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Telegram botni ishga tushirish'

    def handle(self, *args, **options):
        if not bot:
            self.stdout.write(self.style.ERROR("Bot tokeni topilmadi!"))
            return

        self.stdout.write(self.style.SUCCESS("Bot ishga tushdi..."))

        @bot.message_handler(commands=['start'])
        def send_welcome(message):
            chat_id = message.chat.id
            username = message.from_user.username
            
            # Userni topishga harakat qilamiz (agar telefon raqamini ulashgan bo'lsa)
            # Hozircha shunchaki salom beramiz va telefon so'raymiz
            
            keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            button = telebot.types.KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)
            keyboard.add(button)
            
            bot.send_message(
                chat_id, 
                "Assalomu alaykum! Smart Edu tizimiga xush kelibsiz.\nIltimos, shaxsingizni tasdiqlash uchun telefon raqamingizni yuboring.",
                reply_markup=keyboard
            )

        @bot.message_handler(content_types=['contact'])
        def handle_contact(message):
            if message.contact is not None:
                phone = message.contact.phone_number
                chat_id = message.chat.id
                
                # Formatlash (+ belgisi bo'lsa olib tashlash, yoki moslash)
                if phone.startswith('+'):
                    phone = phone[1:]
                
                # Userni qidirish
                try:
                    user = User.objects.get(phone=phone)
                    user.telegram_id = chat_id
                    user.save()
                    
                    bot.send_message(chat_id, f"Rahmat, {user.first_name}! Siz tizimga muvaffaqiyatli ulandingiz. Endi bildirishnomalarni shu yerda olasiz.")
                    self.stdout.write(self.style.SUCCESS(f"User linked: {user.phone} -> {chat_id}"))
                    
                except User.DoesNotExist:
                    bot.send_message(chat_id, "Kechirasiz, bu raqam tizimda topilmadi. Administratorga murojaat qiling.")
                    self.stdout.write(self.style.WARNING(f"User not found for phone: {phone}"))

        # Botni cheksiz ishlatish
        bot.infinity_polling()
