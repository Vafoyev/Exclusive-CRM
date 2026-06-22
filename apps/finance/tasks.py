from celery import shared_task
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_monthly_fees_task():
    """
    Har oyning 1-sanasida barcha faol o'quvchilardan
    oylik to'lovni avtomatik tarzda yechib oladigan vazifa.
    """
    try:
        logger.info("Oylik to'lovlarni avtomatik yechish jarayoni boshlandi...")
        call_command('process_monthly_fees')
        logger.info("Oylik to'lovlarni avtomatik yechish muvaffaqiyatli yakunlandi.")
    except Exception as e:
        logger.error(f"Oylik to'lovlarni yechishda xatolik yuz berdi: {str(e)}")
