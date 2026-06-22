from django import forms
from .models import Lead, Stage, LeadSource

INPUT_CLASSES = "w-full px-4 py-2 rounded-lg bg-gray-50 border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary focus:bg-white"


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['full_name', 'phone', 'source', 'interested_course', 'extra_data']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Ism Familiya'}),
            'phone': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': '998901234567'}),
            'source': forms.Select(attrs={'class': INPUT_CLASSES}),
            'interested_course': forms.Select(attrs={'class': INPUT_CLASSES}),
            'extra_data': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 3, 'placeholder': "Qo'shimcha izohlar..."}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        # Organization bo'yicha filter
        if self.organization:
            self.fields['source'].queryset = LeadSource.objects.filter(
                organization=self.organization, is_deleted=False
            )
            from apps.education.models import Course
            self.fields['interested_course'].queryset = Course.objects.filter(
                organization=self.organization, is_deleted=False
            )


class StageForm(forms.ModelForm):
    """Voronka bosqichi formasi"""
    class Meta:
        model = Stage
        fields = ['name', 'order', 'color', 'is_won']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': INPUT_CLASSES, 
                'placeholder': "Masalan: Yangi, Qo'ng'iroq qilindi"
            }),
            'order': forms.NumberInput(attrs={
                'class': INPUT_CLASSES,
                'min': 1
            }),
            'color': forms.TextInput(attrs={
                'class': INPUT_CLASSES,
                'type': 'color',
                'style': 'height: 42px;'
            }),
            'is_won': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 text-primary rounded'
            }),
        }


class LeadSourceForm(forms.ModelForm):
    """Lid manbasi formasi"""
    class Meta:
        model = LeadSource
        fields = ['name', 'utm_source']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': INPUT_CLASSES, 
                'placeholder': 'Instagram, Telegram, Ko\'cha'
            }),
            'utm_source': forms.TextInput(attrs={
                'class': INPUT_CLASSES, 
                'placeholder': 'ig_ads_summer'
            }),
        }


class LeadConvertForm(forms.Form):
    """Lidni o'quvchiga aylantirish formasi"""
    first_name = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Ism'})
    )
    last_name = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Familiya'})
    )
    phone = forms.CharField(
        max_length=20, 
        widget=forms.TextInput(attrs={'class': INPUT_CLASSES})
    )
    password = forms.CharField(
        max_length=100, 
        required=False,
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Parol (bo\'sh qoldirsangiz avtomatik yaratiladi)'})
    )
    
    # Ota-ona ma'lumotlari
    parent_first_name = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Ota-ona ismi'})
    )
    parent_last_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Ota-ona familiyasi'})
    )
    parent_phone = forms.CharField(
        max_length=20, 
        widget=forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': "Ota-ona telefon raqami"})
    )
    relation_type = forms.ChoiceField(
        choices=[
            ('father', 'Otasi'),
            ('mother', 'Onasi'),
            ('guardian', 'Vasiysi'),
            ('relative', 'Qarindoshi'),
        ],
        widget=forms.Select(attrs={'class': INPUT_CLASSES})
    )