"""Human-owned planning, itemized budgets, evaluation and outcomes."""
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator,MaxValueValidator
from django.db import models


class PlanningStage(models.Model):
    code=models.SlugField(max_length=40,unique=True)
    name=models.CharField(max_length=80)
    position=models.PositiveIntegerField(default=0)
    class Meta: ordering=['position','name']
    def __str__(self):return self.name


class ConferencePlan(models.Model):
    edition=models.OneToOneField('ConferenceEdition',on_delete=models.CASCADE,related_name='plan')
    stage=models.ForeignKey(PlanningStage,on_delete=models.PROTECT)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='conference_plans')
    objective=models.TextField(blank=True)
    notes=models.TextField(blank=True)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='+')
    updated_at=models.DateTimeField(auto_now=True)
    def __str__(self):return str(self.edition)


class BudgetLine(models.Model):
    CATEGORIES=[('registration','Registration'),('travel','Travel'),('lodging','Lodging'),('other','Other')]
    plan=models.ForeignKey(ConferencePlan,on_delete=models.CASCADE,related_name='budget_lines')
    category=models.CharField(max_length=20,choices=CATEGORIES)
    description=models.CharField(max_length=180)
    currency=models.CharField(max_length=3)
    estimated=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True,validators=[MinValueValidator(0)])
    actual=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True,validators=[MinValueValidator(0)])
    source_url=models.URLField(blank=True)
    active=models.BooleanField(default=True)
    class Meta: ordering=['category','id']
    def __str__(self):return self.description


def budget_totals(lines):
    groups={}
    for line in lines:
        row=groups.setdefault(line.currency,{'currency':line.currency,'estimated_known':Decimal('0'),
            'actual_known':Decimal('0'),'estimated_missing':0,'actual_missing':0,'count':0})
        row['count']+=1
        for name in ('estimated','actual'):
            value=getattr(line,name)
            if value is None:row[name+'_missing']+=1
            else:row[name+'_known']+=value
    for row in groups.values():
        row['estimated_total']=None if row['estimated_missing'] else row['estimated_known']
        row['actual_total']=None if row['actual_missing'] else row['actual_known']
    return list(groups.values())


class OutcomeReport(models.Model):
    edition=models.OneToOneField('ConferenceEdition',on_delete=models.CASCADE,related_name='outcome')
    summary=models.TextField()
    attendees=models.PositiveIntegerField(null=True,blank=True)
    contacts=models.PositiveIntegerField(null=True,blank=True)
    partnerships=models.PositiveIntegerField(null=True,blank=True)
    follow_up=models.TextField(blank=True)
    follow_up_date=models.DateField(null=True,blank=True)
    follow_up_completed=models.BooleanField(default=False)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='+')
    updated_at=models.DateTimeField(auto_now=True)


class SelectionCriterion(models.Model):
    CENTERS=[('CAC','CAC'),('CDSA','CDSA'),('CCSE','CCSE wide')]
    center=models.CharField(max_length=4,choices=CENTERS)
    name=models.CharField(max_length=120)
    description=models.TextField(blank=True)
    weight=models.DecimalField(max_digits=5,decimal_places=2,null=True,blank=True,
        validators=[MinValueValidator(Decimal('0.01')),MaxValueValidator(100)])
    approved=models.BooleanField(default=False)
    active=models.BooleanField(default=True)
    class Meta:
        ordering=['center','id']
        constraints=[models.UniqueConstraint(fields=['center','name'],name='unique_center_criterion')]
    def __str__(self):return f'{self.center}: {self.name}'


class CriterionRating(models.Model):
    edition=models.ForeignKey('ConferenceEdition',on_delete=models.CASCADE,related_name='ratings')
    criterion=models.ForeignKey(SelectionCriterion,on_delete=models.PROTECT)
    rating=models.PositiveSmallIntegerField(validators=[MinValueValidator(1),MaxValueValidator(5)])
    rationale=models.TextField()
    source_url=models.URLField(blank=True)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='+')
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['edition','criterion'],name='unique_edition_criterion_rating')]


def evaluation_scores(edition,criteria=None):
    criteria=list(criteria if criteria is not None else SelectionCriterion.objects.filter(active=True))
    ratings={r.criterion_id:r for r in edition.ratings.all()}
    rows=[]
    for center in ['CAC','CDSA','CCSE']:
        group=[c for c in criteria if c.center==center]
        if not group:continue
        ready=all(c.approved and c.weight is not None for c in group)
        complete=ready and all(c.pk in ratings for c in group)
        score=None
        if complete:
            denominator=sum(c.weight for c in group)
            if denominator>0:
                score=(sum(c.weight*Decimal(ratings[c.pk].rating)/5 for c in group)*100/denominator).quantize(Decimal('.1'))
        rows.append({'center':center,'score':score,'criteria_ready':ready,'missing':sum(c.pk not in ratings for c in group),'count':len(group)})
    return rows


class ActivityEvent(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True)
    action=models.CharField(max_length=80)
    edition=models.ForeignKey('ConferenceEdition',on_delete=models.SET_NULL,null=True,blank=True)
    description=models.CharField(max_length=255)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:ordering=['-created_at','-id']


class ReportSubscription(models.Model):
    name=models.CharField(max_length=100)
    email=models.EmailField(unique=True)
    weekday=models.PositiveSmallIntegerField(default=0,validators=[MaxValueValidator(6)])
    enabled=models.BooleanField(default=False)
    class Meta:ordering=['name']


class ReportDelivery(models.Model):
    subscription=models.ForeignKey(ReportSubscription,on_delete=models.CASCADE)
    period=models.DateField()
    sent_at=models.DateTimeField(null=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['subscription','period'],name='unique_report_week')]
