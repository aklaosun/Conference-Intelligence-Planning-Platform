from django import forms
from django.contrib.auth.models import User
from .planning_models import ConferencePlan,BudgetLine,OutcomeReport,SelectionCriterion,CriterionRating
from .access_models import ROLE_CHOICES

class PlanForm(forms.ModelForm):
    class Meta:
        model=ConferencePlan
        fields=['stage','owner','objective','notes']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['owner'].queryset=User.objects.filter(is_active=True).order_by('username')
        for name in ['objective','notes']:self.fields[name].max_length=10000

class BudgetForm(forms.ModelForm):
    class Meta:
        model=BudgetLine
        fields=['category','description','currency','estimated','actual','source_url']
    def clean_currency(self):
        value=self.cleaned_data['currency'].strip().upper()
        if len(value)!=3 or not value.isascii() or not value.isalpha():raise forms.ValidationError('Use a three-letter currency code.')
        return value

class OutcomeForm(forms.ModelForm):
    class Meta:
        model=OutcomeReport
        fields=['summary','attendees','contacts','partnerships','follow_up','follow_up_date','follow_up_completed']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for name in ['summary','follow_up']:self.fields[name].max_length=10000

class CriterionForm(forms.ModelForm):
    class Meta:
        model=SelectionCriterion
        fields=['center','name','description','weight','approved','active']
    def clean(self):
        data=super().clean()
        if data.get('approved') and data.get('weight') is None:self.add_error('weight','Approved criteria need an explicit weight.')
        return data

class RatingForm(forms.ModelForm):
    class Meta:
        model=CriterionRating
        fields=['criterion','rating','rationale','source_url']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['criterion'].queryset=SelectionCriterion.objects.filter(active=True)
        self.fields['rationale'].max_length=10000

class InvitationForm(forms.Form):
    email=forms.EmailField()
    role=forms.ChoiceField(choices=ROLE_CHOICES)

class ReportSubscriptionForm(forms.ModelForm):
    class Meta:
        from .planning_models import ReportSubscription
        model=ReportSubscription
        fields=['name','email','weekday','enabled']
    def clean_email(self):return self.cleaned_data['email'].lower()
