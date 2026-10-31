"""CSV reporting shared by the browser export and an opt-in weekly email job."""
import csv
from io import StringIO
from decimal import Decimal
from django.db.models import Q
from .models import ConferenceEdition
from .planning_models import ConferencePlan,budget_totals

def safe_cell(value):
    if value is None:return ''
    if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):return "'"+value
    return value

def planning_csv():
    stream=StringIO(newline='')
    writer=csv.writer(stream)
    writer.writerow(['Conference','Year','Planning status','Owner','Objectives','Currency','Estimated total',
        'Known estimated subtotal','Missing estimates','Actual total','Known actual subtotal','Missing actuals',
        'Outcome summary','Attendees','Contacts','Partnerships','Follow-up date','Follow-up completed',
        'Actual cost per attendee','Actual cost per contact'])
    editions=ConferenceEdition.objects.filter(Q(plan__isnull=False)|Q(outcome__isnull=False)).select_related('conference','plan__stage','plan__owner','outcome').prefetch_related('plan__budget_lines')
    for edition in editions:
        plan=getattr(edition,'plan',None)
        outcome=getattr(edition,'outcome',None)
        groups=budget_totals(line for line in plan.budget_lines.all() if line.active) if plan else []
        for totals in groups or [None]:
            value=lambda key:totals.get(key) if totals else None
            known=lambda kind:value(kind+'_known') if totals and value(kind+'_missing')!=totals['count'] else None
            def per_count(name):
                count=getattr(outcome,name,None)
                total=value('actual_total')
                return (total/Decimal(count)).quantize(Decimal('.01')) if total is not None and count else None
            row=[edition.conference.name,edition.year,plan.stage.name if plan else 'Not planned',(plan.owner.get_full_name() or plan.owner.username) if plan and plan.owner else '',
                plan.objective if plan else '',value('currency'),value('estimated_total'),known('estimated'),value('estimated_missing'),
                value('actual_total'),known('actual'),value('actual_missing'),getattr(outcome,'summary',None),
                getattr(outcome,'attendees',None),getattr(outcome,'contacts',None),getattr(outcome,'partnerships',None),
                getattr(outcome,'follow_up_date',None),getattr(outcome,'follow_up_completed',None),per_count('attendees'),per_count('contacts')]
            writer.writerow([safe_cell(v) for v in row])
    return stream.getvalue()
