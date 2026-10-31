"""Server-side validation for reviewed scalar values and editable child rows."""
import copy
import datetime
import json
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from django import forms
from .forms import CandidateCorrectionForm

class ReviewValidationError(ValueError):
    pass

class ReviewStateError(ValueError):
    pass

def plain_values(payload):
    return CandidateCorrectionForm.values_from_payload(payload)

def validate_fields(candidate, values):
    if not isinstance(values, dict):
        raise ReviewValidationError("Reviewed fields must be an object.")
    unknown = set(values) - set(CandidateCorrectionForm.base_fields)
    if unknown:
        raise ReviewValidationError("The review contains unsupported field names.")
    data = {}
    for name, value in values.items():
        if name in ("themes", "target_audience") and isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        elif hasattr(value, "isoformat"):
            value = value.isoformat()
        data[name] = value
    form = CandidateCorrectionForm(data, candidate=candidate)
    if not form.is_valid():
        errors = "; ".join(f"{name}: {' '.join(messages)}" for name, messages in form.errors.items())
        raise ReviewValidationError(errors)
    cleaned = form.cleaned_data
    for name in ("start_date", "end_date"):
        if cleaned.get(name) and cleaned[name].year != cleaned["year"]:
            raise ReviewValidationError("Conference dates must match the edition year.")
    return {name: None if value == "" else value for name, value in cleaned.items()}

def source_map(payload):
    return {str(s.get("id")):s for s in payload.get("sources",[]) if isinstance(s,dict)}

def source_url(row, payload, fallback):
    value = row.get("source_url")
    if not value and row.get("source_id"):
        source = source_map(payload).get(str(row["source_id"]),{})
        value = source.get("source_url") or source.get("url")
    value = value or fallback
    if not value:
        return None
    if not isinstance(value,str) or urlparse(value).scheme not in ("http","https"):
        raise ReviewValidationError("Source links must use HTTP or HTTPS.")
    try:
        return forms.URLField(max_length=200).clean(value)
    except forms.ValidationError:
        raise ReviewValidationError("A source URL is invalid or longer than 200 characters.") from None

def evidence_text(value):
    if value is None:
        return ""
    return value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)

def reviewed_rows(rows, kind, payload, fallback, *, legacy=False):
    if not isinstance(rows,list) or len(rows)>200:
        raise ReviewValidationError(f"{kind} must be a list of at most 200 objects.")
    output = []
    for number, row in enumerate(rows,1):
        if not isinstance(row,dict):
            raise ReviewValidationError(f"{kind} row {number} must be an object.")
        try:
            if kind=="deadlines":
                clean = {
                    "type":forms.CharField(max_length=64).clean(row.get("type")),
                    "date":forms.DateField().clean(row.get("date")),
                    "time":forms.TimeField(required=False).clean(row.get("time")),
                    "timezone":forms.CharField(max_length=64,required=False).clean(row.get("timezone")) or None,
                }
            else:
                raw_amount = row.get("amount")
                if isinstance(raw_amount,bool):
                    raise forms.ValidationError("Amount must be a decimal number.")
                amount = forms.DecimalField(max_digits=8,decimal_places=2,min_value=0).clean(raw_amount)
                currency = row.get("currency") or ("USD" if legacy else "")
                if not isinstance(currency,str) or len(currency)!=3 or not currency.isalpha():
                    raise forms.ValidationError("Supply an explicit three-letter currency code.")
                clean = {
                    "category":forms.CharField(max_length=128).clean(row.get("category")),
                    "rate_type":forms.CharField(max_length=64).clean(row.get("rate_type")),
                    "amount":amount,
                    "currency":currency.upper(),
                }
        except (forms.ValidationError, InvalidOperation, TypeError, ValueError) as exc:
            message = " ".join(exc.messages) if isinstance(exc,forms.ValidationError) else "Invalid row values."
            raise ReviewValidationError(f"{kind} row {number}: {message}") from None
        clean["source_url"] = source_url(row,payload,fallback)
        clean["evidence"] = evidence_text(row.get("evidence"))
        output.append(clean)
    return output

def json_ready(value):
    if isinstance(value,dict):
        return {k:json_ready(v) for k,v in value.items()}
    if isinstance(value,list):
        return [json_ready(v) for v in value]
    if isinstance(value,(datetime.date,datetime.time,datetime.datetime,Decimal)):
        return str(value) if isinstance(value,Decimal) else value.isoformat()
    return value

def validate_packet(candidate, packet):
    if not isinstance(packet,dict):
        raise ReviewValidationError("Supply a JSON review object.")
    if packet.get("candidate_id") != candidate.pk:
        raise ReviewValidationError("The review candidate ID does not match this record.")
    if packet.get("expected_status") != "needs_review":
        raise ReviewStateError("Only a pending candidate can be reviewed.")
    action = packet.get("requested_action")
    if action not in ("approve","reject"):
        raise ReviewValidationError("Choose approve or reject.")
    notes = packet.get("reviewer_notes","")
    if not isinstance(notes,str) or len(notes)>5000:
        raise ReviewValidationError("Reviewer notes must be text under 5000 characters.")
    if action=="reject":
        if not notes.strip():
            raise ReviewValidationError("Enter a rejection reason.")
        return {"action":action,"notes":notes.strip()}
    if packet.get("confirmed") is not True:
        raise ReviewValidationError("Confirm that you checked the sources before approval.")
    reviewed = packet.get("reviewed_values")
    if not isinstance(reviewed,dict) or not isinstance(reviewed.get("fields"),dict):
        raise ReviewValidationError("Reviewed values must include fields, deadlines, and registration_prices.")
    values = {}
    for name, entry in reviewed["fields"].items():
        if not isinstance(entry,dict) or "value" not in entry:
            raise ReviewValidationError("Each reviewed field needs a value.")
        values[name] = entry["value"]
    fields = validate_fields(candidate,values)
    decisions = packet.get("conflict_decisions",[])
    conflicts = candidate.raw_payload.get("conflicts",[])
    if not isinstance(decisions,list) or len(decisions)!=len(conflicts):
        raise ReviewValidationError("Resolve and document every conflict.")
    for decision in decisions:
        if not isinstance(decision,dict) or not isinstance(decision.get("decision_and_evidence"),str) or not decision["decision_and_evidence"].strip():
            raise ReviewValidationError("Every conflict needs a decision and supporting evidence.")
    deadlines = reviewed_rows(reviewed.get("deadlines"),"deadlines",candidate.raw_payload,candidate.requested_url)
    prices = reviewed_rows(reviewed.get("registration_prices"),"registration_prices",candidate.raw_payload,candidate.requested_url)
    replace_rows = packet.get("replace_existing_rows",False)
    if type(replace_rows) is not bool:
        raise ReviewValidationError("replace_existing_rows must be boolean.")
    return {"action":action,"fields":fields,"deadlines":deadlines,"registration_prices":prices,
            "notes":notes.strip(),"conflict_decisions":decisions,"replace_existing_rows":replace_rows}

