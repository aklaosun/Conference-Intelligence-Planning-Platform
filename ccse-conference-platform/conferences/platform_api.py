"""Same-origin JSON interface for the React website and Electron client."""
import hashlib
import hmac
import json
import os,re,threading
from functools import wraps
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User,Group
from django.core.paginator import Paginator
from django.db import transaction,connection,DatabaseError
from django.db.models import Q,Count
from django.forms.models import model_to_dict
from django.http import JsonResponse,HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404,render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET,require_POST,require_http_methods
from .models import Conference,ConferenceEdition,Deadline,RegistrationPrice,ExtractionCandidate
from .permissions import can_edit,can_review
from .planning_models import (PlanningStage,ConferencePlan,BudgetLine,OutcomeReport,SelectionCriterion,
    CriterionRating,ActivityEvent,ReportSubscription,budget_totals,evaluation_scores)
from .access_models import AccessInvitation,LoginThrottle,ROLE_GROUPS
from .platform_forms import PlanForm,BudgetForm,OutcomeForm,CriterionForm,RatingForm,InvitationForm,ReportSubscriptionForm


def error(message,status=400):return JsonResponse({'error':message},status=status)
def body(request):
    if len(request.body)>150000:raise ValueError('Request is too large.')
    value=json.loads(request.body)
    if not isinstance(value,dict):raise ValueError('Expected a JSON object.')
    return value
def checked(form):
    if not form.is_valid():raise ValueError('; '.join(f'{k}: {" ".join(v)}' for k,v in form.errors.items()))
    return form
def api(view):
    @wraps(view)
    def wrapped(request,*args,**kwargs):
        if not request.user.is_authenticated:return error('Sign in to continue.',401)
        try:return view(request,*args,**kwargs)
        except (ValueError,TypeError,json.JSONDecodeError) as exc:return error(str(exc))
    return wrapped
def event(user,action,description,edition=None):
    ActivityEvent.objects.create(user=user,action=action,description=description[:255],edition=edition)
def user_data(user):
    return {'id':user.pk,'username':user.username,'name':user.get_full_name() or user.username,'email':user.email,
        'can_edit':can_edit(user),'can_review':can_review(user),'can_research':user.has_perm('conferences.add_extractioncandidate'),
        'is_admin':user.is_superuser,'roles':list(user.groups.values_list('name',flat=True))}


@ensure_csrf_cookie
@require_GET
def session(request):
    return JsonResponse({'authenticated':request.user.is_authenticated,'csrf_token':get_token(request),
        'local_demo':getattr(settings,'LOCAL_DESKTOP',False),
        'user':user_data(request.user) if request.user.is_authenticated else None})

_bootstrap_lock=threading.Lock()

@csrf_exempt
@require_POST
def desktop_bootstrap(request):
    # One-shot bearer authentication is available only inside the personal desktop
    # service. The token is generated per process and never included in a URL/file.
    if not getattr(settings,'LOCAL_DESKTOP',False):return error('Not found.',404)
    if request.META.get('REMOTE_ADDR') not in ['127.0.0.1','::1']:return error('Local access only.',403)
    with _bootstrap_lock:
        expected=os.environ.get('CCSE_DESKTOP_BOOTSTRAP_TOKEN','')
        supplied=request.headers.get('X-Desktop-Bootstrap','')
        if not expected or not hmac.compare_digest(supplied.encode(),expected.encode()):return error('Invalid launch token.',403)
        user=User.objects.filter(username='desktop-owner',is_superuser=True,is_active=True).first()
        if user is None:return error('Local owner is unavailable.',503)
        login(request,user)
        os.environ.pop('CCSE_DESKTOP_BOOTSTRAP_TOKEN',None)
    return JsonResponse({'ok':True})

@api
@require_http_methods(['GET','POST'])
def local_settings(request):
    if not getattr(settings,'LOCAL_DESKTOP',False):return error('Not found.',404)
    if not request.user.is_superuser:return error('Local owner access is required.',403)
    if request.method=='POST':
        data=body(request)
        key=data.get('api_key','')
        model=data.get('model','')
        if not isinstance(key,str) or not isinstance(model,str):return error('The key and model must be text.')
        key=key.strip();model=model.strip()
        if not re.fullmatch(r'gemini-[a-z0-9.-]{2,100}',model):return error('Enter a Gemini model name such as gemini-3.5-flash-lite.')
        if key and (len(key)<20 or len(key)>512 or any(c.isspace() for c in key)):
            return error('Copy the complete API key; masked values and spaces are not valid.')
        if not key:key=os.environ.get('GEMINI_API_KEY','')
        text='# Private local backend configuration. Never share this file.\nGEMINI_API_KEY='+key+'\nGEMINI_MODEL='+model+'\n'
        temporary=settings.DESKTOP_DATA_DIR/'backend.env.tmp'
        temporary.write_text(text,encoding='utf-8');temporary.chmod(0o600)
        temporary.replace(settings.DESKTOP_CONFIG)
        os.environ['GEMINI_API_KEY']=key;os.environ['GEMINI_MODEL']=model
    return JsonResponse({'configured':bool(os.environ.get('GEMINI_API_KEY')),
        'model':os.environ.get('GEMINI_MODEL','gemini-3.5-flash-lite'),
        'data_folder':str(settings.DESKTOP_DATA_DIR)})

@require_POST
def sign_in(request):
    try:data=body(request)
    except (ValueError,TypeError):return error('Invalid sign-in request.')
    username=str(data.get('username',''))[:150]
    password=data.get('password','')
    if not isinstance(password,str) or len(password)>4096:return error('Invalid sign-in request.')
    identity=username.casefold()+'|'+request.META.get('REMOTE_ADDR','')
    key=hmac.new(settings.SECRET_KEY.encode(),identity.encode(),hashlib.sha256).hexdigest()
    now=timezone.now()
    with transaction.atomic():
        attempt,_=LoginThrottle.objects.select_for_update().get_or_create(key=key)
        if now-attempt.window_started>timezone.timedelta(minutes=10):
            attempt.failures=0;attempt.window_started=now;attempt.save()
        if attempt.failures>=8:return error('Too many attempts. Try again in ten minutes.',429)
        user=authenticate(request,username=username,password=password)
        if user is None:
            attempt.failures+=1;attempt.save(update_fields=['failures'])
            return error('Username or password did not match.',400)
        attempt.delete()
    login(request,user)
    return JsonResponse({'authenticated':True,'csrf_token':get_token(request),'user':user_data(user)})

@require_POST
def sign_out(request):
    logout(request)
    return JsonResponse({'ok':True,'csrf_token':get_token(request)})


def edition_data(e):
    plan=getattr(e,'plan',None)
    prices=[{'id':p.pk,'category':p.category,'rate_type':p.rate_type,'amount':p.amount,'currency':p.currency,
        'source_url':p.source_url,'evidence':p.evidence} for p in e.registration_prices.all() if p.is_active]
    deadlines=[{'id':d.pk,'type':d.type,'date':d.date,'time':d.time,'timezone':d.timezone,'source_url':d.source_url,
        'evidence':d.evidence} for d in e.deadlines.all() if d.is_active]
    return {'id':e.pk,'conference_id':e.conference_id,'conference':e.conference.name,'year':e.year,
        'start_date':e.start_date,'end_date':e.end_date,'location':e.location,'format':e.attendance_format,
        'information_status':e.get_information_status_display(),'verification_status':e.get_verification_status_display(),
        'source_url':e.source_url,'last_verified_at':e.last_verified_at,'deadlines':deadlines,'prices':prices,
        'legacy_sources':e.field_sources.get('legacy_imports',[]),'planning_status':plan.stage.name if plan else 'Not planned'}
def conference_data(c):
    return {'id':c.pk,'name':c.name,'organizer':c.organizer,'website':c.website,'themes':c.themes,
        'audience':c.target_audience,'centers':[name for name,flag in [('CAC',c.cac_relevant),('CDSA',c.cdsa_relevant)] if flag],
        'editions':[edition_data(e) for e in c.editions.all()]}
def editions_query():
    return ConferenceEdition.objects.select_related('conference','plan__stage').prefetch_related('deadlines','registration_prices')


@api
@require_GET
def overview(request):
    today=timezone.localdate()
    editions=editions_query()
    count=editions.count()
    dated=editions.filter(start_date__isnull=False).count()
    known_prices=editions.filter(registration_prices__is_active=True).distinct().count()
    upcoming=editions.filter(start_date__gte=today).order_by('start_date')[:8]
    deadlines=Deadline.objects.filter(is_active=True,date__gte=today,date__lte=today+timezone.timedelta(days=60)).select_related('edition__conference').order_by('date')[:10]
    return JsonResponse({'today':today,'conference_count':Conference.objects.count(),'edition_count':count,
        'pending_count':ExtractionCandidate.objects.filter(status='needs_review').count(),
        'unverified_count':editions.exclude(verification_status='VERIFIED').count(),
        'missing_dates':count-dated,'unknown_prices':count-known_prices,'date_coverage':round(100*dated/count) if count else 0,
        'upcoming':[edition_data(e) for e in upcoming],
        'deadlines':[{'id':d.pk,'conference_id':d.edition.conference_id,'conference':str(d.edition),'type':d.type,'date':d.date,'timezone':d.timezone} for d in deadlines],
        'plans':ConferencePlan.objects.count(),'outcomes':OutcomeReport.objects.count(),
        'years':list(editions.values('year').annotate(count=Count('id')).order_by('year')),
        'activity':[{'action':a.action,'description':a.description,'at':a.created_at,'user':a.user.get_username() if a.user else 'Former user'} for a in ActivityEvent.objects.select_related('user')[:8]]})


@api
@require_GET
def catalog(request):
    from .views import filtered_conferences
    _,query=filtered_conferences(request.GET)
    page=Paginator(query.prefetch_related('editions__deadlines','editions__registration_prices','editions__plan__stage'),12).get_page(request.GET.get('page'))
    return JsonResponse({'count':page.paginator.count,'pages':page.paginator.num_pages,'page':page.number,
        'results':[conference_data(c) for c in page],'years':list(ConferenceEdition.objects.order_by('-year').values_list('year',flat=True).distinct())})

@api
@require_GET
def detail(request,pk):
    c=get_object_or_404(Conference.objects.prefetch_related('editions__deadlines','editions__registration_prices','editions__plan__stage'),pk=pk)
    return JsonResponse(conference_data(c))


def plan_data(edition):
    plan=getattr(edition,'plan',None)
    lines=list(plan.budget_lines.filter(active=True)) if plan else []
    outcome=getattr(edition,'outcome',None)
    ratings=list(edition.ratings.select_related('criterion'))
    return {'edition':edition_data(edition),'plan':model_to_dict(plan,fields=['stage','owner','objective','notes']) if plan else None,
        'budget_lines':[dict(model_to_dict(line,fields=['category','description','currency','estimated','actual','source_url']),id=line.pk) for line in lines],
        'totals':budget_totals(lines),'outcome':model_to_dict(outcome,exclude=['edition','updated_by']) if outcome else None,
        'ratings':[model_to_dict(r,fields=['id','criterion','rating','rationale','source_url']) for r in ratings],
        'scores':evaluation_scores(edition),'stages':list(PlanningStage.objects.values('id','name','code')),
        'owners':[{'id':u.pk,'name':u.get_full_name() or u.username} for u in User.objects.filter(is_active=True)],
        'criteria':list(SelectionCriterion.objects.filter(active=True).values('id','center','name','description','weight','approved'))}


@api
@require_GET
def plans(request):
    rows=editions_query().order_by('-year','conference__name')
    return JsonResponse({'results':[{'edition':edition_data(e),'totals':budget_totals(e.plan.budget_lines.filter(active=True)) if getattr(e,'plan',None) else []} for e in rows]})


@api
@require_http_methods(['GET','POST'])
def plan(request,pk):
    edition=get_object_or_404(editions_query(),pk=pk)
    if request.method=='GET':return JsonResponse(plan_data(edition))
    if not can_edit(request.user):return error('Coordinator or editor access is required.',403)
    data=body(request)
    raw_lines=data.get('budget_lines',[])
    if not isinstance(raw_lines,list) or len(raw_lines)>100:raise ValueError('Supply at most 100 budget lines.')
    existing=getattr(edition,'plan',None)
    form=checked(PlanForm(data.get('plan',{}),instance=existing))
    forms=[];seen=set()
    for values in raw_lines:
        if not isinstance(values,dict):raise ValueError('Each budget line must be an object.')
        line_id=values.get('id')
        if line_id:
            if line_id in seen:raise ValueError('A budget line was supplied twice.')
            seen.add(line_id)
            instance=BudgetLine.objects.filter(pk=line_id,plan=existing,active=True).first() if existing else None
            if instance is None:raise ValueError('This budget line does not belong to this plan.')
        else:instance=None
        forms.append(checked(BudgetForm(values,instance=instance)))
    with transaction.atomic():
        saved=form.save(commit=False);saved.edition=edition;saved.updated_by=request.user;saved.save()
        retained=[]
        for child in forms:
            line=child.save(commit=False);line.plan=saved;line.active=True;line.save();retained.append(line.pk)
        saved.budget_lines.filter(active=True).exclude(pk__in=retained).update(active=False)
        event(request.user,'plan_updated',f'Updated planning and {len(retained)} budget lines for {edition}.',edition)
    edition=editions_query().get(pk=pk)
    return JsonResponse(plan_data(edition))


@api
@require_POST
def outcome(request,pk):
    if not can_edit(request.user):return error('Coordinator or editor access is required.',403)
    edition=get_object_or_404(ConferenceEdition,pk=pk)
    form=checked(OutcomeForm(body(request),instance=getattr(edition,'outcome',None)))
    with transaction.atomic():
        saved=form.save(commit=False);saved.edition=edition;saved.updated_by=request.user;saved.save()
        event(request.user,'outcome_updated',f'Recorded outcomes and follow-up for {edition}.',edition)
    return JsonResponse(plan_data(editions_query().get(pk=pk)))


@api
@require_http_methods(['GET','POST'])
def criteria(request):
    if request.method=='POST':
        if not request.user.is_superuser:return error('Administrator access is required.',403)
        data=body(request)
        instance=get_object_or_404(SelectionCriterion,pk=data['id']) if data.get('id') else None
        form=checked(CriterionForm(data,instance=instance))
        form.save()
        event(request.user,'criteria_updated','Updated selection criteria and approval status.')
    return JsonResponse({'results':list(SelectionCriterion.objects.values())})


@api
@require_POST
def rating(request,pk):
    if not can_edit(request.user):return error('Coordinator or editor access is required.',403)
    edition=get_object_or_404(ConferenceEdition,pk=pk)
    data=body(request)
    instance=CriterionRating.objects.filter(edition=edition,criterion_id=data.get('criterion')).first()
    form=checked(RatingForm(data,instance=instance))
    saved=form.save(commit=False);saved.edition=edition;saved.updated_by=request.user;saved.save()
    event(request.user,'evaluation_updated',f'Updated a source-backed evaluation for {edition}.',edition)
    return JsonResponse(plan_data(editions_query().get(pk=pk)))


@api
@require_GET
def deadlines(request):
    today=timezone.localdate()
    query=Deadline.objects.filter(is_active=True).select_related('edition__conference')
    scope=request.GET.get('scope','upcoming')
    if scope=='upcoming':query=query.filter(date__gte=today)
    elif scope=='overdue':query=query.filter(date__lt=today).filter(Q(edition__start_date__gte=today)|Q(edition__start_date__isnull=True))
    elif scope!='all':return error('Unknown deadline filter.')
    return JsonResponse({'results':[{'id':d.pk,'conference':str(d.edition),'conference_id':d.edition.conference_id,
        'edition_id':d.edition_id,'type':d.type,'date':d.date,'time':d.time,'timezone':d.timezone,'source_url':d.source_url,
        'days':(d.date-today).days} for d in query.order_by('date')[:300]],
        'follow_ups':[{'id':o.pk,'conference':str(o.edition),'conference_id':o.edition.conference_id,
            'date':o.follow_up_date,'text':o.follow_up} for o in OutcomeReport.objects.filter(follow_up_completed=False,follow_up_date__isnull=False).select_related('edition__conference')]})


@api
@require_GET
def reports(request):
    plans=ConferencePlan.objects.select_related('edition__conference','stage','owner').prefetch_related('budget_lines')
    return JsonResponse({'plans':[{'id':p.pk,'edition_id':p.edition_id,'conference_id':p.edition.conference_id,'conference':str(p.edition),
        'status':p.stage.name,'owner':p.owner.get_full_name() or p.owner.username if p.owner else 'Unassigned',
        'totals':budget_totals(p.budget_lines.filter(active=True))} for p in plans],
        'outcomes':[{'conference':str(o.edition),'conference_id':o.edition.conference_id,'summary':o.summary,
            'attendees':o.attendees,'contacts':o.contacts,'partnerships':o.partnerships,'follow_up_date':o.follow_up_date,
            'follow_up_completed':o.follow_up_completed} for o in OutcomeReport.objects.select_related('edition__conference')],
        'subscriptions':list(ReportSubscription.objects.values('id','name','email','weekday','enabled')) if request.user.is_superuser else []})

@api
@require_GET
def export_planning(request):
    from .reporting import planning_csv
    response=HttpResponse(planning_csv(),content_type='text/csv; charset=utf-8')
    response['Content-Disposition']='attachment; filename="conference-planning-outcomes.csv"'
    return response

@api
@require_http_methods(['GET','POST'])
def subscriptions(request):
    if not request.user.is_superuser:return error('Administrator access is required.',403)
    if request.method=='POST':
        data=body(request)
        instance=get_object_or_404(ReportSubscription,pk=data['id']) if data.get('id') else None
        form=checked(ReportSubscriptionForm(data,instance=instance))
        if form.cleaned_data['enabled'] and not getattr(settings,'WORKSPACE_EMAIL_ENABLED',False):
            return error('Configure and enable SMTP on the server before enabling report emails.')
        saved=form.save()
        event(request.user,'report_subscription_updated',f'Updated report subscription {saved.pk}.')
    return JsonResponse({'results':list(ReportSubscription.objects.values('id','name','email','weekday','enabled')),
        'email_enabled':getattr(settings,'WORKSPACE_EMAIL_ENABLED',False)})


@api
@require_http_methods(['GET','POST'])
def team(request):
    if not request.user.is_superuser:return error('Administrator access is required.',403)
    created_url=None
    if request.method=='POST':
        data=body(request)
        action=data.get('action','invite')
        if action=='invite':
            form=checked(InvitationForm(data))
            if User.objects.filter(email__iexact=form.cleaned_data['email']).exists():raise ValueError('An account already uses this email. Manage that existing account instead.')
            invitation,token=AccessInvitation.issue(user=request.user,**form.cleaned_data)
            created_url=request.build_absolute_uri('/app/#/join/'+token)
            event(request.user,'access_invited',f'Created {invitation.role} invitation for {invitation.email}.')
        elif action=='revoke':
            invitation=get_object_or_404(AccessInvitation,pk=data.get('id'))
            invitation.revoked_at=timezone.now();invitation.save(update_fields=['revoked_at'])
            event(request.user,'invitation_revoked',f'Revoked an invitation for {invitation.email}.')
        elif action in ['role','active']:
            target=get_object_or_404(User,pk=data.get('id'))
            if target.pk==request.user.pk or target.is_superuser or target.is_staff:raise ValueError('Privileged accounts must be managed through the administrator workflow.')
            if action=='role':
                role=data.get('role')
                if role not in ROLE_GROUPS:raise ValueError('Unknown access role.')
                target.groups.set([Group.objects.get(name=ROLE_GROUPS[role])])
            else:
                if type(data.get('active')) is not bool:raise ValueError('Active status must be true or false.')
                target.is_active=data['active'];target.save(update_fields=['is_active'])
            event(request.user,'access_updated',f'Updated access for {target.username}.')
        else:raise ValueError('Unknown account action.')
    return JsonResponse({'invitation_url':created_url,
        'users':[dict(user_data(u),active=u.is_active) for u in User.objects.prefetch_related('groups').order_by('username')],
        'invitations':[{'id':i.pk,'email':i.email,'role':i.role,'expires_at':i.expires_at,'usable':i.usable,
            'used':bool(i.used_at),'revoked':bool(i.revoked_at)} for i in AccessInvitation.objects.order_by('-created_at')[:100]]})


@ensure_csrf_cookie
@require_http_methods(['GET','POST'])
def invitation(request,token):
    invitation=get_object_or_404(AccessInvitation,token_hash=AccessInvitation.digest(token))
    if not invitation.usable:return error('This invitation has expired, was revoked, or has already been used.',410)
    if request.method=='GET':return JsonResponse({'email':invitation.email,'role':invitation.role,'expires_at':invitation.expires_at,'csrf_token':get_token(request)})
    try:
        form=checked(UserCreationForm(body(request)))
        with transaction.atomic():
            locked=AccessInvitation.objects.select_for_update().get(pk=invitation.pk)
            if not locked.usable:return error('This invitation has already been used.',410)
            if User.objects.filter(email__iexact=locked.email).exists():return error('This email already has an account.')
            user=form.save(commit=False);user.email=locked.email;user.save()
            user.groups.add(Group.objects.get(name=ROLE_GROUPS[locked.role]))
            locked.used_at=timezone.now();locked.save(update_fields=['used_at'])
            event(user,'invitation_accepted',f'Joined with {locked.role} access.')
        login(request,user)
        return JsonResponse({'authenticated':True,'user':user_data(user),'csrf_token':get_token(request)})
    except (ValueError,TypeError):return error('Choose an unused username and matching strong passwords.')


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:cursor.execute('SELECT 1')
    except DatabaseError:return JsonResponse({'service':'ccse-conference-platform','status':'unavailable'},status=503)
    return JsonResponse({'service':'ccse-conference-platform','status':'ok'})

@ensure_csrf_cookie
@require_GET
def application(request):
    return render(request,'conferences/application.html',workspace_assets())

def workspace_assets():
    from pathlib import Path
    manifest=Path(settings.BASE_DIR)/'conferences/static/workspace/.vite/manifest.json'
    entry={}
    if manifest.is_file():
        entries=json.loads(manifest.read_text())
        entry=next((v for v in entries.values() if v.get('isEntry')), {})
    return {'workspace_js':'workspace/'+entry['file'] if entry else None,'workspace_css':['workspace/'+f for f in entry.get('css',[])]}
