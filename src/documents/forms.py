from django import forms
from django.contrib.auth.models import User
from .models import Tag

class AssignValidationTaskForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    assigned_to = forms.ModelChoiceField(queryset=User.objects.all(), label='Assign to')
    tag = forms.ModelChoiceField(queryset=Tag.objects.all(), label='Choose Tag')
    note = forms.CharField(widget=forms.Textarea, required=False, label='Note')
