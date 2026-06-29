from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.upload_view, name='upload'),
    path('results/<int:pk>/', views.results_view, name='results'),
    path('results/<int:pk>/export-pdf/', views.export_pdf_view, name='export_pdf'),
    path('results/<int:pk>/rewrite-suggestions/', views.generate_rewrite_suggestions_view, name='rewrite_suggestions'),  # NEW
    path('reanalyze/<int:pk>/', views.reanalyze_view, name='reanalyze'),
    path('history/', views.HistoryView.as_view(), name='history'),
    path('delete/<int:pk>/', views.delete_view, name='delete'),
    path('resume-versions/', views.resume_versions_view, name='resume_versions'),
    path('resume-versions/<int:pk>/delete/', views.delete_resume_version_view, name='delete_resume_version'),
]