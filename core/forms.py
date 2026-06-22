from django import forms
from .models import AnalysisSession, ResumeVersion


class ResumeVersionForm(forms.ModelForm):
    class Meta:
        model = ResumeVersion
        fields = ['label', 'resume_file', 'is_default']
        widgets = {
            'label': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Backend Developer Resume',
            }),
            'resume_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf',
            }),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_resume_file(self):
        f = self.cleaned_data.get('resume_file')
        if f:
            if not f.name.endswith('.pdf'):
                raise forms.ValidationError('Only PDF files are accepted.')
            if f.size > 5 * 1024 * 1024:
                raise forms.ValidationError('File size must not exceed 5 MB.')
        return f

class UploadForm(forms.ModelForm):
    resume_version = forms.ModelChoiceField(
        queryset=ResumeVersion.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select mb-2'}),
        label='Use a saved resume version',
        empty_label='— Upload a new resume instead —',
    )

    class Meta:
        model = AnalysisSession
        fields = ['resume_file', 'job_title', 'company_name', 'job_description']
        widgets = {
            'job_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Senior Python Developer',
            }),
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Google',
            }),
            'job_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'Paste the full job description here...',
            }),
            'resume_file': forms.FileInput(attrs={
                'class': 'd-none',
                'accept': '.pdf',
                'id': 'resumeFileInput',
            }),
        }
        labels = {
            'resume_file': 'Resume (PDF)',
            'job_title': 'Job Title',
            'company_name': 'Company Name',
            'job_description': 'Job Description',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['resume_version'].queryset = ResumeVersion.objects.filter(user=user)
        self.fields['resume_file'].required = False  # validated in clean()

    def clean(self):
        cleaned = super().clean()
        resume_file = cleaned.get('resume_file')
        resume_version = cleaned.get('resume_version')

        if not resume_file and not resume_version:
            raise forms.ValidationError(
                'Please either upload a PDF or select a saved resume version.'
            )
        if resume_file:
            if not resume_file.name.endswith('.pdf'):
                self.add_error('resume_file', 'Only PDF files are accepted.')
            elif resume_file.size > 5 * 1024 * 1024:
                self.add_error('resume_file', 'File size must not exceed 5 MB.')
        return cleaned
    
    
class ReanalyzeForm(forms.ModelForm):
    """Used when re-running analysis on an existing session — JD/title/company
    can be edited, but the resume file itself is NOT re-uploaded."""

    class Meta:
        model = AnalysisSession
        fields = ['job_title', 'company_name', 'job_description']
        widgets = {
            'job_title': forms.TextInput(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'job_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
            }),
        }