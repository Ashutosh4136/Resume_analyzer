import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.http import JsonResponse, HttpResponse
from django.contrib import messages

from .models import AnalysisSession, KeywordResult, UserProfile, ResumeVersion
from .forms import UploadForm, ReanalyzeForm, ResumeVersionForm
from .services import run_analysis, AnalysisError
from .notifications import send_analysis_complete_email


@login_required
def upload_view(request):
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES, user=request.user)

        if form.is_valid():
            session = form.save(commit=False)
            session.user = request.user

            resume_version = form.cleaned_data.get('resume_version')
            if resume_version and not form.cleaned_data.get('resume_file'):
                session.resume_file = resume_version.resume_file

            session.save()

            try:
                run_analysis(session)
                profile, _ = UserProfile.objects.get_or_create(user=request.user)
                profile.total_analyses += 1
                profile.save(update_fields=['total_analyses'])
                send_analysis_complete_email(session, request=request)
            except AnalysisError as exc:
                messages.warning(request, str(exc))
                return redirect('core:results', pk=session.pk)
            except Exception as exc:
                messages.error(request, f'Analysis failed: {exc}')
                session.delete()
                return render(request, 'core/upload.html', {'form': form})

            return redirect('core:results', pk=session.pk)
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = UploadForm(user=request.user)

    resume_versions = ResumeVersion.objects.filter(user=request.user)
    return render(request, 'core/upload.html', {
        'form': form,
        'resume_versions': resume_versions,
    })


@login_required
def reanalyze_view(request, pk):
    session = get_object_or_404(AnalysisSession, pk=pk, user=request.user)

    if request.method == 'POST':
        form = ReanalyzeForm(request.POST, instance=session)
        if form.is_valid():
            session = form.save()
            try:
                run_analysis(session)
                send_analysis_complete_email(session, request=request)
            except AnalysisError as exc:
                messages.warning(request, str(exc))
                return redirect('core:results', pk=session.pk)
            except Exception as exc:
                messages.error(request, f'Re-analysis failed: {exc}')
                return render(request, 'core/reanalyze.html', {'form': form, 'session': session})

            messages.success(request, 'Re-analysis complete — results updated!')
            return redirect('core:results', pk=session.pk)
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = ReanalyzeForm(instance=session)

    return render(request, 'core/reanalyze.html', {'form': form, 'session': session})


@login_required
def results_view(request, pk):
    session = get_object_or_404(AnalysisSession, pk=pk, user=request.user)
    all_keywords = session.keywords.all().order_by('-importance_weight', 'keyword')

    matched = [kw for kw in all_keywords if kw.found_in_resume]
    missing = [kw for kw in all_keywords if not kw.found_in_resume]

    # Attach a section suggestion to each missing keyword for the template
    missing_with_suggestions = [
        {'keyword': kw, 'suggestion': kw.get_section_suggestion()}
        for kw in missing
    ]

    analysis_incomplete = not all_keywords.exists()

    def _colors_for(score):
        if score >= 70:
            return '#198754', '#d1e7dd'
        elif score >= 40:
            return '#ffc107', '#fff3cd'
        return '#dc3545', '#f8d7da'

    chart_color, chart_bg = _colors_for(session.match_score)
    w_chart_color, w_chart_bg = _colors_for(session.weighted_score)

    context = {
    'session': session,
        'matched': matched,
        'missing': missing,
        'missing_with_suggestions': missing_with_suggestions,
        'chart_color': chart_color,
        'chart_bg': chart_bg,
        'w_chart_color': w_chart_color,
        'w_chart_bg': w_chart_bg,
        'score_json': json.dumps(round(session.match_score, 1)),
        'weighted_score_json': json.dumps(round(session.weighted_score, 1)),
        'analysis_incomplete': analysis_incomplete,
        'ai_feedback': session.ai_feedback,
    }
    return render(request, 'core/results.html', context)


class HistoryView(LoginRequiredMixin, ListView):
    model = AnalysisSession
    template_name = 'core/history.html'
    context_object_name = 'sessions'
    paginate_by = 10

    def get_queryset(self):
        return AnalysisSession.objects.filter(user=self.request.user)


@login_required
def delete_view(request, pk):
    session = get_object_or_404(AnalysisSession, pk=pk, user=request.user)

    if request.method == 'DELETE':
        if session.resume_file:
            try:
                session.resume_file.delete(save=False)
            except Exception:
                pass
        session.delete()
        return JsonResponse({'status': 'ok'})

    return render(request, 'core/confirm_delete.html', {'session': session})


# ---------------------------------------------------------------------------
# Resume version management
# ---------------------------------------------------------------------------

@login_required
def resume_versions_view(request):
    versions = ResumeVersion.objects.filter(user=request.user)

    if request.method == 'POST':
        form = ResumeVersionForm(request.POST, request.FILES)
        if form.is_valid():
            version = form.save(commit=False)
            version.user = request.user
            version.save()
            messages.success(request, f'Saved resume version "{version.label}".')
            return redirect('core:resume_versions')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = ResumeVersionForm()

    return render(request, 'core/resume_versions.html', {
        'form': form,
        'versions': versions,
    })


@login_required
def delete_resume_version_view(request, pk):
    version = get_object_or_404(ResumeVersion, pk=pk, user=request.user)
    if request.method in ('POST', 'DELETE'):
        if version.resume_file:
            try:
                version.resume_file.delete(save=False)
            except Exception:
                pass
        version.delete()
        if request.method == 'DELETE':
            return JsonResponse({'status': 'ok'})
        messages.success(request, 'Resume version deleted.')
    return redirect('core:resume_versions')


# ---------------------------------------------------------------------------
# PDF export
# ---------------------------------------------------------------------------

@login_required
def export_pdf_view(request, pk):
    from .pdf_export import generate_results_pdf
    session = get_object_or_404(AnalysisSession, pk=pk, user=request.user)
    pdf_buffer = generate_results_pdf(session)

    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    filename = f"resume_analysis_{session.job_title.replace(' ', '_')}_{session.pk}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response