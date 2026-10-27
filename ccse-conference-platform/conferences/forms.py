from django import forms
from django.forms import inlineformset_factory

from .models import (
    AttendanceFormat,
    Conference,
    ConferenceEdition,
    Deadline,
    InformationStatus,
    RegistrationPrice,
    VerificationStatus,
)


class ListField(forms.CharField):
    def prepare_value(self, value):
        if isinstance(value, (list, tuple)):
            return ", ".join(str(v) for v in value)
        return value

    def to_python(self, value):
        value = super().to_python(value)
        if not value:
            return []
        return [part.strip() for part in value.split(",") if part.strip()]


class DateInput(forms.DateInput):
    input_type = "date"


class TimeInput(forms.TimeInput):
    input_type = "time"


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class ConferenceForm(BootstrapMixin, forms.ModelForm):
    themes = ListField(required=False, help_text="Separate with commas")
    target_audience = ListField(required=False, help_text="Separate with commas")

    class Meta:
        model = Conference
        fields = ["name", "organizer", "website", "themes", "target_audience", "cac_relevant", "cdsa_relevant"]
        labels = {"cac_relevant": "CAC relevant", "cdsa_relevant": "CDSA relevant"}


class EditionForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = ConferenceEdition
        fields = [
            "year", "start_date", "end_date", "start_time", "timezone", "location",
            "attendance_format", "information_status", "verification_status", "source_url",
        ]
        widgets = {
            "start_date": DateInput(),
            "end_date": DateInput(),
            "start_time": TimeInput(),
        }

    def clean(self):
        data = super().clean()
        start = data.get("start_date")
        end = data.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date can't be before the start date.")
        return data


class DeadlineForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Deadline
        fields = ["type", "date", "time", "timezone", "source_url", "is_active"]
        widgets = {"date": DateInput(), "time": TimeInput()}
        labels = {"is_active": "Current"}


class RegistrationPriceForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = RegistrationPrice
        fields = ["category", "rate_type", "amount", "currency", "source_url", "is_active"]
        labels = {"is_active": "Current"}


DeadlineFormSet = inlineformset_factory(
    ConferenceEdition, Deadline, form=DeadlineForm, extra=1, can_delete=True
)

PriceFormSet = inlineformset_factory(
    ConferenceEdition, RegistrationPrice, form=RegistrationPriceForm, extra=1, can_delete=True
)


class ConferenceSearchForm(BootstrapMixin, forms.Form):
    CENTER_CHOICES = [("", "Any center"), ("cac", "CAC"), ("cdsa", "CDSA"), ("both", "CAC and CDSA")]

    q = forms.CharField(required=False, label="Search")
    center = forms.ChoiceField(required=False, choices=CENTER_CHOICES)
    year = forms.IntegerField(required=False)
    information_status = forms.ChoiceField(
        required=False, choices=[("", "Any info status")] + list(InformationStatus.choices)
    )
    verification_status = forms.ChoiceField(
        required=False, choices=[("", "Any verification")] + list(VerificationStatus.choices)
    )
    attendance_format = forms.ChoiceField(
        required=False, choices=[("", "Any format")] + list(AttendanceFormat.choices)
    )
    upcoming_only = forms.BooleanField(required=False, label="Upcoming only")


class CandidateCorrectionForm(BootstrapMixin, forms.Form):
    conference_name = forms.CharField(max_length=255)
    organizer = forms.CharField(max_length=255, required=False)
    year = forms.IntegerField(min_value=1900, max_value=2100)
    start_date = forms.DateField(required=False, widget=DateInput())
    end_date = forms.DateField(required=False, widget=DateInput())
    start_time = forms.TimeField(required=False, widget=TimeInput())
    timezone = forms.CharField(max_length=64, required=False)
    location = forms.CharField(max_length=255, required=False)
    attendance_format = forms.ChoiceField(
        required=False, choices=[("", "---------")] + list(AttendanceFormat.choices)
    )
    themes = ListField(required=False, help_text="Separate with commas")
    target_audience = ListField(required=False, help_text="Separate with commas")

    def __init__(self, *args, candidate=None, **kwargs):
        self.candidate = candidate
        if candidate is not None and "initial" not in kwargs:
            kwargs["initial"] = self.values_from_payload(candidate.raw_payload)
        super().__init__(*args, **kwargs)

    @classmethod
    def values_from_payload(cls, payload):
        fields = payload.get("fields", {}) or {}
        values = {}
        for name in cls.base_fields:
            entry = fields.get(name)
            if isinstance(entry, dict):
                values[name] = entry.get("value")
            elif entry is not None:
                values[name] = entry
        return values

    def clean(self):
        data = super().clean()
        start = data.get("start_date")
        end = data.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date can't be before the start date.")
        return data

    def edited_fields(self):
        original = self.values_from_payload(self.candidate.raw_payload) if self.candidate else {}
        changes = {}
        for name, new_value in self.cleaned_data.items():
            if new_value in ("", None, []) and original.get(name) in ("", None, []):
                continue
            old_value = original.get(name)
            if self._normalize(new_value) != self._normalize(old_value):
                changes[name] = None if new_value in ("", []) and name not in ("themes", "target_audience") else new_value
        return changes

    @staticmethod
    def _normalize(value):
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            return [str(v).strip() for v in value]
        if hasattr(value, "isoformat"):
            text = value.isoformat()
            return text[:5] if len(text) == 8 and text[2] == ":" else text
        text = str(value).strip()
        return text[:5] if len(text) == 8 and text[2] == ":" else text


class RejectForm(BootstrapMixin, forms.Form):
    confirm = forms.BooleanField(required=True, label="Yes, reject this suggestion")
