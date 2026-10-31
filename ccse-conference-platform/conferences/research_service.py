"""Bounded multi-page research, provenance, conflicts, and repeat-run monitoring.

No function in this module approves or writes trusted conference records.
"""
import copy
import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone
from urllib.parse import urlparse, urldefrag
import requests
from pydantic import ValidationError
from .ai_service import (
    GeminiProvider, MAX_TEXT, PROMPT_VERSION, CandidateValidationError,
    ProviderError, create_candidate_payload, normalized,
)
from .extraction_service import fetch_conference_page

MAX_PAGES = 5
PIPELINE_VERSION = "1.0"
CRITICAL_FIELDS = {"year", "start_date", "end_date", "start_time", "timezone", "location", "attendance_format"}

@dataclass
class ResearchRun:
    candidate: object
    created: bool

def canonical_url(url):
    return urldefrag(url.strip())[0].rstrip("/")

def select_companion_links(page, year=None, limit=2):
    """Follow relevant first-hop links on the same hostname, excluding other editions."""
    host = urlparse(page["source_url"]).hostname
    ranked = []
    for index, link in enumerate(page.get("links", [])):
        url = link["url"]
        parsed = urlparse(url)
        label = (link.get("text", "") + " " + parsed.path).lower()
        if parsed.scheme not in ("http", "https") or parsed.hostname != host:
            continue
        if parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            continue
        if canonical_url(url) == canonical_url(page["source_url"]):
            continue
        path_years = re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", parsed.path)
        if year and any(int(y) != year for y in path_years):
            continue
        if re.search(r"\.(?:pdf|zip|png|jpg|jpeg|ics|docx?)$", parsed.path, re.I):
            continue
        if any(word in label for word in ("registration", "register", "fees", "pricing")):
            priority = 0
        elif any(word in label for word in ("call for papers", "cfp", "important-dates", "deadlines", "call-for-papers")):
            priority = 1
        elif any(word in label for word in ("program", "venue")):
            priority = 2
        else:
            continue
        ranked.append((priority, index, url))
    selected = []
    seen = set()
    for _, _, url in sorted(ranked):
        key = canonical_url(url)
        if key not in seen:
            selected.append(url)
            seen.add(key)
        if len(selected) >= limit:
            break
    return selected if limit else []

def validate_options(url, expected_year, source_urls, max_pages):
    if not isinstance(url, str) or not url.strip():
        raise CandidateValidationError("A conference URL is required.")
    if expected_year is not None and (type(expected_year) is not int or not 1900 <= expected_year <= 2200):
        raise CandidateValidationError("Edition year must be an integer between 1900 and 2200.")
    if type(max_pages) is not int or not 1 <= max_pages <= MAX_PAGES:
        raise CandidateValidationError("max_pages must be between 1 and 5.")
    if source_urls is not None and (not isinstance(source_urls, list) or
            len(source_urls) > MAX_PAGES - 1 or any(not isinstance(u, str) or not u.strip() for u in source_urls)):
        raise CandidateValidationError("source_urls must contain at most four URL strings.")
    if source_urls and len({canonical_url(u) for u in source_urls} - {canonical_url(url)}) > max_pages - 1:
        raise CandidateValidationError("The requested source URLs exceed max_pages; raise the limit or remove URLs.")

def collect_pages(url, *, expected_year=None, follow_links=True, source_urls=None, max_pages=3):
    validate_options(url, expected_year, source_urls, max_pages)
    root = fetch_conference_page(url)
    warnings = []
    pages = [root]
    seen = {canonical_url(root["source_url"]), canonical_url(url)}
    # Explicit source URLs are a user-selected list; automatic links stay on the same hostname.
    urls = list(source_urls or [])
    if follow_links:
        urls += select_companion_links(root, expected_year, limit=max_pages - 1)
    for child_url in urls:
        if len(pages) >= max_pages:
            break
        if canonical_url(child_url) in seen:
            continue
        seen.add(canonical_url(child_url))
        try:
            page = fetch_conference_page(child_url)
        except (ValueError, requests.RequestException):
            warnings.append(f"Companion page could not be retrieved: {child_url}. Its facts were not analyzed.")
            continue
        if canonical_url(page["source_url"]) in {canonical_url(p["source_url"]) for p in pages}:
            continue
        # An automatic same-host link must not redirect to an unrelated host.
        if child_url not in (source_urls or []) and urlparse(page["source_url"]).hostname != urlparse(root["source_url"]).hostname:
            warnings.append(f"Skipped automatic companion link that redirected to another hostname: {child_url}.")
            continue
        pages.append(page)
    return pages, warnings

def facts_key(value):
    if isinstance(value, str):
        return normalized(value).casefold()
    return json.dumps(value, sort_keys=True)

def attach_source(payload, page, source_id):
    data = copy.deepcopy(payload)
    source = data["sources"][0]
    source.update(id=source_id, analyzed_text=page["text"][:MAX_TEXT],
                  content_sha256=hashlib.sha256(page["text"].encode()).hexdigest())
    for item in data["fields"].values():
        if item["value"] is not None:
            item["source_id"] = source_id
    for key in ("deadlines", "registration_prices"):
        for row in data[key]:
            row["source_id"] = source_id
    return data

def merge_payloads(payloads):
    result = copy.deepcopy(payloads[0])
    result["sources"] = []
    result["conflicts"] = []
    result["warnings"] = []
    for payload in payloads:
        result["sources"].extend(payload["sources"])
        result["warnings"].extend(payload["warnings"])
    for name, field in result["fields"].items():
        values = [copy.deepcopy(p["fields"][name]) for p in payloads if p["fields"][name]["value"] is not None]
        if not values:
            continue
        field.update(values[0])
        alternatives = []
        for value in values:
            if not any(facts_key(value["value"]) == facts_key(a["value"]) for a in alternatives):
                alternatives.append(value)
        if len(alternatives) > 1:
            result["conflicts"].append({"kind": "field", "field": name, "alternatives": alternatives})
            result["warnings"].append(f"{name}: sources disagree; review every alternative before approval.")
            field["alternatives"] = alternatives
            if name in CRITICAL_FIELDS:
                field.update(value=None, evidence=None, source_id=None)
        else:
            field["corroborating_sources"] = sorted({v["source_id"] for v in values})
    for group in ("deadlines", "registration_prices"):
        rows = []
        seen = {}
        by_identity = {}
        for payload in payloads:
            for original in payload[group]:
                row = copy.deepcopy(original)
                if group == "deadlines":
                    identity = re.sub(r"[^a-z0-9]+", "_", row["type"].casefold()).strip("_")
                    value_key = (row["date"], row.get("time"), (row.get("timezone") or "").casefold())
                else:
                    identity = (facts_key(row["category"]), facts_key(row["rate_type"]), row["currency"])
                    value_key = str(Decimal(row["amount"]).normalize())
                if group == "deadlines":
                    compatible = next((r for r in by_identity.get(str(identity), [])
                        if r["date"] == row["date"]
                        and all(not r.get(k) or not row.get(k) or str(r[k]).casefold() == str(row[k]).casefold()
                                for k in ("time", "timezone"))), None)
                    if compatible is not None:
                        for key in ("time", "timezone"):
                            if not compatible.get(key) and row.get(key):
                                compatible[key] = row[key]
                        compatible.setdefault("additional_evidence", []).append(
                            {"source_id":row["source_id"], "source_url":row["source_url"], "evidence":row["evidence"]})
                        continue
                exact = (str(identity), str(value_key))
                if exact in seen:
                    existing = seen[exact]
                    existing.setdefault("additional_evidence", []).append(
                        {"source_id": row["source_id"], "source_url": row["source_url"], "evidence": row["evidence"]})
                    continue
                seen[exact] = row
                rows.append(row)
                by_identity.setdefault(str(identity), []).append(row)
        conflicting_ids = set()
        for identity, alternatives in by_identity.items():
            if len(alternatives) > 1:
                result["conflicts"].append({"kind": group, "identity": identity, "alternatives": copy.deepcopy(alternatives)})
                result["warnings"].append(f"{group}: sources give conflicting values for {identity}; suggestions were withheld until a reviewer selects an alternative.")
                conflicting_ids.update(id(row) for row in alternatives)
        result[group] = [row for row in rows if id(row) not in conflicting_ids]
    # Remove per-page absence warnings only when another source fills that gap.
    result["warnings"] = list(dict.fromkeys(w for w in result["warnings"]
        if not (w.startswith("registration_prices: no supported") and result["registration_prices"])
        and not any(w == f"{name}: not established from this page." and field["value"] is not None
                    for name, field in result["fields"].items())))
    start = result["fields"]["start_date"]["value"]
    end = result["fields"]["end_date"]["value"]
    if start and end and end < start:
        for key in ("start_date", "end_date"):
            result["fields"][key].update(value=None, evidence=None, source_id=None)
        result["warnings"].append("Merged conference date range was inconsistent and was cleared for human review.")
    result["schema_version"] = "1.1"
    result["extraction"]["page_count"] = len(result["sources"])
    result["extraction"]["analyzed_characters"] = sum(len(s["analyzed_text"]) for s in result["sources"])
    return result

def candidate_summary(payload):
    f = payload["fields"]
    return {
        "conference_name": f["conference_name"]["value"], "year": f["year"]["value"],
        "start_date": f["start_date"]["value"], "end_date": f["end_date"]["value"],
        "location": f["location"]["value"], "attendance_format": f["attendance_format"]["value"],
        "source_count": len(payload["sources"]), "deadline_count": len(payload["deadlines"]),
        "registration_price_count": len(payload["registration_prices"]),
        "conflict_count": len(payload.get("conflicts", [])),
        "missing_fields": [name for name, field in f.items() if field["value"] is None],
    }

def compare_candidates(previous, current):
    if not previous:
        return {"previous_candidate_id": None, "fields": [], "deadlines_changed": False,
                "registration_prices_changed": False}
    old = previous.raw_payload
    changes = []
    for name, field in current["fields"].items():
        before = old.get("fields", {}).get(name, {}).get("value")
        if facts_key(before) != facts_key(field["value"]):
            changes.append({"field": name, "before": before, "after": field["value"]})
    def values(payload, key):
        excluded = {"evidence", "source_id", "source_url", "additional_evidence"}
        return sorted(json.dumps({k:v for k,v in r.items() if k not in excluded},sort_keys=True)
                      for r in payload.get(key, []))
    return {"previous_candidate_id": previous.pk, "fields": changes,
            "deadlines_changed": values(old, "deadlines") != values(current, "deadlines"),
            "registration_prices_changed": values(old, "registration_prices") != values(current, "registration_prices")}

def research_and_stage(url, expected_year=None, *, provider=None, follow_links=True,
                       source_urls=None, max_pages=3, force=False):
    from .models import ExtractionCandidate
    provider = provider or GeminiProvider()
    pages, warnings = collect_pages(url, expected_year=expected_year, follow_links=follow_links,
                                   source_urls=source_urls, max_pages=max_pages)
    config = {"follow_links": follow_links, "source_urls": source_urls or [], "max_pages": max_pages,
              "expected_year": expected_year, "model": provider.model, "provider": type(provider).__name__, "prompt_version": PROMPT_VERSION,
              "pipeline_version": PIPELINE_VERSION}
    signature = hashlib.sha256(json.dumps({"config": config,
        "pages": [{"url":p["source_url"], "text":p["text"]} for p in pages], "warnings":warnings},
        sort_keys=True).encode()).hexdigest()
    query = ExtractionCandidate.objects.filter(requested_url=url)
    if expected_year is not None:
        query = query.filter(raw_payload__fields__year__value=expected_year)
    previous = query.order_by("-submitted_at", "-pk").first()
    if not force and previous and previous.raw_payload.get("monitoring", {}).get("content_fingerprint") == signature:
        return ResearchRun(previous, False)
    payloads = []
    edition_year = expected_year
    for index, page in enumerate(pages):
        try:
            payload = create_candidate_payload(page, provider, edition_year, allow_missing_year=index > 0)
            if index == 0:
                edition_year = payload["fields"]["year"]["value"] or expected_year
            # Missing-year companion dates still cannot cross into another edition.
            if index and edition_year:
                for name in ("start_date", "end_date"):
                    value = payload["fields"][name]["value"]
                    if value and int(value[:4]) != edition_year:
                        raise CandidateValidationError("Companion page contains dates from another edition.")
            payloads.append(attach_source(payload, page, f"source_{index + 1}"))
        except (CandidateValidationError, ValidationError):
            if index == 0:
                raise
            warnings.append(f"Companion page failed edition/structure validation and was excluded: {page['source_url']}.")
        # Provider errors are intentionally fatal: do not save a deceptively complete partial run.
    merged = merge_payloads(payloads)
    merged["warnings"] = list(dict.fromkeys(merged["warnings"] + warnings))
    merged["extracted_at"] = datetime.now(timezone.utc).isoformat()
    merged["summary"] = candidate_summary(merged)
    merged["changes"] = compare_candidates(previous, merged)
    merged["monitoring"] = {"content_fingerprint": signature, "config": config,
                            "previous_candidate_id": previous.pk if previous else None}
    candidate = ExtractionCandidate.objects.create(schema_version=merged["schema_version"],
        requested_url=url, raw_payload=merged, status=ExtractionCandidate.Status.NEEDS_REVIEW)
    return ResearchRun(candidate, True)
