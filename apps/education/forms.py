from django import forms
from apps.users.models import User
from .models import Course, Room, Group
from .services.scheduling import check_schedule_conflict

# Umumiy dizayn klasslari
INPUT_CLASSES = "w-full px-4 py-2 rounded-lg bg-gray-50 border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary focus:bg-white"


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'price', 'duration_months', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'M: General English'}),
            'price': forms.NumberInput(attrs={'class': INPUT_CLASSES}),
            'duration_months': forms.NumberInput(attrs={'class': INPUT_CLASSES}),
            'description': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-primary'}),
        }


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'capacity', 'has_projector']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'M: 1-xona'}),
            'capacity': forms.NumberInput(attrs={'class': INPUT_CLASSES}),
            'has_projector': forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-primary'}),
        }


class GroupForm(forms.ModelForm):
    DAYS_CHOICES = (
        (1, 'Dush'),
        (2, 'Sesh'),
        (3, 'Chor'),
        (4, 'Pay'),
        (5, 'Juma'),
        (6, 'Shan'),
        (7, 'Yak'),
    )
    
    # Oddiy checkbox maydonlari
    day_1 = forms.BooleanField(required=False, label='Dush')
    day_2 = forms.BooleanField(required=False, label='Sesh')
    day_3 = forms.BooleanField(required=False, label='Chor')
    day_4 = forms.BooleanField(required=False, label='Pay')
    day_5 = forms.BooleanField(required=False, label='Juma')
    day_6 = forms.BooleanField(required=False, label='Shan')

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields['course'].queryset = Course.objects.filter(organization=self.organization, is_deleted=False)
            self.fields['teacher'].queryset = User.objects.filter(organization=self.organization, role='teacher', is_deleted=False)
            self.fields['room'].queryset = Room.objects.filter(organization=self.organization, is_deleted=False)
        
        # Agar tahrirlash bo'lsa, mavjud kunlarni belgilash
        if self.instance and self.instance.pk and self.instance.schedule_days:
            for day in self.instance.schedule_days:
                field_name = f'day_{day}'
                if field_name in self.fields:
                    self.fields[field_name].initial = True

    class Meta:
        model = Group
        fields = ['name', 'course', 'teacher', 'room', 'start_date', 'start_time', 'end_time', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'M: IELTS-A'}),
            'course': forms.Select(attrs={'class': INPUT_CLASSES}),
            'teacher': forms.Select(attrs={'class': INPUT_CLASSES}),
            'room': forms.Select(attrs={'class': INPUT_CLASSES}),
            'start_date': forms.DateInput(attrs={'class': INPUT_CLASSES, 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': INPUT_CLASSES, 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': INPUT_CLASSES, 'type': 'time'}),
            'status': forms.Select(attrs={'class': INPUT_CLASSES}),
        }

    def clean(self):
        cleaned_data = super().clean()
        
        # Checkbox qiymatlarini yig'ib, schedule_days listini yaratish
        days = []
        for i in range(1, 7):
            if cleaned_data.get(f'day_{i}'):
                days.append(i)
        
        # Kamida bitta kun tanlangan bo'lishi kerak
        if not days:
            raise forms.ValidationError("Kamida bitta dars kunini tanlang!")
        
        # schedule_days ga saqlash
        cleaned_data['schedule_days'] = days

        # Ma'lumotlarni olamiz
        room = cleaned_data.get('room')
        teacher = cleaned_data.get('teacher')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if room and teacher and days and start_time and end_time:
            org = self.organization or (self.instance.organization if self.instance.pk else None)

            msg = check_schedule_conflict(
                organization=org,
                room=room,
                teacher=teacher,
                days=days,
                start_time=start_time,
                end_time=end_time,
                exclude_group_id=self.instance.pk
            )

            if msg:
                raise forms.ValidationError(msg)

        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Checkbox qiymatlarini schedule_days ga o'tkazish
        days = []
        for i in range(1, 7):
            if self.cleaned_data.get(f'day_{i}'):
                days.append(i)
        instance.schedule_days = days
        if commit:
            instance.save()
        return instance


# ===========================================
# MATERIALS LMS FORMS
# ===========================================

class MaterialForm(forms.ModelForm):
    """Material yuklash formasi"""
    
    class Meta:
        from apps.education.materials import Material
        model = Material
        fields = [
            'category', 'title', 'description', 'material_type',
            'file', 'external_url', 'thumbnail',
            'access_type', 'groups',
            'is_published', 'is_featured'
        ]
        widgets = {
            'category': forms.Select(attrs={'class': INPUT_CLASSES}),
            'title': forms.TextInput(attrs={
                'class': INPUT_CLASSES,
                'placeholder': 'Material sarlavhasi'
            }),
            'description': forms.Textarea(attrs={
                'class': INPUT_CLASSES,
                'rows': 3,
                'placeholder': 'Qisqa tavsif...'
            }),
            'material_type': forms.Select(attrs={'class': INPUT_CLASSES}),
            'file': forms.FileInput(attrs={
                'class': INPUT_CLASSES,
                'accept': '.pdf,.doc,.docx,.mp4,.mp3,.zip,.pptx'
            }),
            'external_url': forms.URLInput(attrs={
                'class': INPUT_CLASSES,
                'placeholder': 'https://youtube.com/...'
            }),
            'thumbnail': forms.FileInput(attrs={
                'class': INPUT_CLASSES,
                'accept': 'image/*'
            }),
            'access_type': forms.Select(attrs={'class': INPUT_CLASSES}),
            'groups': forms.SelectMultiple(attrs={
                'class': INPUT_CLASSES,
                'size': 5
            }),
            'is_published': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 rounded border-gray-300 text-primary focus:ring-primary'
            }),
            'is_featured': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 rounded border-gray-300 text-amber-500 focus:ring-amber-500'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        from apps.education.materials import MaterialCategory
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        if organization:
            self.fields['category'].queryset = MaterialCategory.objects.filter(
                organization=organization, is_deleted=False
            )
            self.fields['groups'].queryset = Group.objects.filter(
                organization=organization, is_deleted=False
            )
        
        # Ixtiyoriy maydonlar
        self.fields['category'].required = False
        self.fields['description'].required = False
        self.fields['file'].required = False
        self.fields['external_url'].required = False
        self.fields['thumbnail'].required = False
        self.fields['groups'].required = False