from django.db import models
from django.contrib.auth.models import User


class AnalysisSession(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETE = 'complete'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETE, 'Complete'),
        (STATUS_FAILED, 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    resume_file = models.FileField(upload_to='resumes/')
    job_description = models.TextField()
    job_title = models.CharField(max_length=200)
    company_name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    match_score = models.FloatField(default=0.0)
    weighted_score = models.FloatField(default=0.0)
    ai_feedback = models.TextField(blank=True, default='')
    ai_rewrite_suggestions = models.JSONField(default=dict, blank=True)
    # Async status tracking (Celery)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_message = models.TextField(blank=True, default='')

    # Resume quality + AI feedback
    formatting_feedback = models.JSONField(default=dict, blank=True)
    ai_feedback = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.job_title} @ {self.company_name} ({self.match_score:.1f}%)"

    def get_score_label(self):
        return self._label_for(self.match_score)

    def get_weighted_score_label(self):
        return self._label_for(self.weighted_score)

    @staticmethod
    def _label_for(score):
        if score >= 70:
            return 'success'
        elif score >= 40:
            return 'warning'
        return 'danger'


class KeywordResult(models.Model):
    CATEGORY_CHOICES = [
        ('skill', 'Skill'),
        ('tool', 'Tool'),
        ('qualification', 'Qualification'),
        ('general', 'General'),
    ]

    # Maps each category to the resume section a missing keyword should go in
    SECTION_SUGGESTIONS = {
        'skill': 'Skills section',
        'tool': 'Skills or Tools & Technologies section',
        'qualification': 'Education / Certifications section',
        'general': 'Summary or Experience bullet points',
    }

    session = models.ForeignKey(AnalysisSession, on_delete=models.CASCADE, related_name='keywords')
    keyword = models.CharField(max_length=200)
    found_in_resume = models.BooleanField(default=False)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='general')
    importance_weight = models.FloatField(default=1.0)

    def __str__(self):
        status = '✓' if self.found_in_resume else '✗'
        return f"{status} {self.keyword} [{self.category}]"

    def get_section_suggestion(self):
        return self.SECTION_SUGGESTIONS.get(self.category, 'Experience section')


class ResumeVersion(models.Model):
    """A named, reusable resume PDF a user can pick at upload time."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resume_versions')
    label = models.CharField(max_length=100)            # e.g. "Backend role"
    resume_file = models.FileField(upload_to='resume_versions/')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.label}"

    def save(self, *args, **kwargs):
        # Ensure only one default per user
        if self.is_default:
            ResumeVersion.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    default_resume = models.FileField(upload_to='default_resumes/', blank=True, null=True)
    target_role = models.CharField(max_length=200, blank=True)
    total_analyses = models.IntegerField(default=0)
    email_notifications = models.BooleanField(default=True)  # NEW

    def __str__(self):
        return f"Profile of {self.user.username}"