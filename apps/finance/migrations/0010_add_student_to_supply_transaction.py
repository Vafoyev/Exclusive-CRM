# Generated manually on 2026-03-05

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_user_xp_total'),  # Latest users migration
        ('finance', '0009_remove_cashsubmission_amount_other_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplytransaction',
            name='student',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='supply_received', to='users.user', verbose_name="O'quvchi", limit_choices_to={'role': 'student'}),
        ),
    ]
