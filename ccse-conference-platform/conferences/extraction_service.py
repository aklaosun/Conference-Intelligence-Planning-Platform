"""Bounded retrieval of a single public HTML conference page."""
from datetime import datetime, timezone
import ipaddress
import socket
import re
from urllib.parse import urlparse, urljoin, urldefrag
import requests
from bs4 import BeautifulSoup

MAX_BYTES = 2_000_000

def validate_public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use a public HTTP(S) URL without credentials.")
    if parsed.port not in (None, 80, 443):
        raise ValueError("Only standard web ports are supported.")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror:
        raise ValueError("The website hostname could not be resolved.") from None
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Private and non-public website addresses are not allowed.")

def parse_conference_html(html, requested_url, source_url):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    # Preserve class-based strikethroughs defined in embedded stylesheet rules.
    for stylesheet in soup.find_all("style"):
        for selectors, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", stylesheet.get_text()):
            if "line-through" not in declarations.lower():
                continue
            try:
                for element in soup.select(selectors.strip()):
                    element["style"] = element.get("style", "") + ";text-decoration:line-through"
            except Exception:
                # Unsupported CSS selectors do not prevent text extraction.
                continue
    for element in soup(["script", "style", "noscript", "template"]):
        element.decompose()
    for element in soup.find_all(True):
        if element.parent is None:
            continue
        style = element.get("style", "").lower()
        if element.name in ("s", "strike", "del") or "line-through" in style:
            element.replace_with(" [CROSSED OUT: " + element.get_text(" ", strip=True) + "] ")
    links = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        absolute = urldefrag(urljoin(source_url, anchor["href"]))[0]
        if absolute not in seen and urlparse(absolute).scheme in ("http", "https"):
            links.append({"url": absolute, "text": anchor.get_text(" ", strip=True)[:250]})
            seen.add(absolute)
        if len(links) >= 300:
            break
    content = soup.body or soup
    text = "\n".join(line.strip() for line in content.get_text(separator="\n").splitlines() if line.strip())
    if not text:
        raise ValueError("No readable text was found on this webpage.")
    return {"requested_url": requested_url, "source_url": source_url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(), "title": title, "text": text, "links": links}

def fetch_conference_page(url):
    current = url
    with requests.Session() as session:
        session.trust_env = False
        for _ in range(6):
            validate_public_url(current)
            with session.get(current, headers={"User-Agent": "CCSEConferenceResearch/1.0",
                             "Accept": "text/html, application/xhtml+xml"},
                             timeout=(10, 30), allow_redirects=False, stream=True) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location:
                        raise ValueError("Website returned an invalid redirect.")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").lower()
                if not any(t in content_type for t in ("text/html", "application/xhtml+xml")):
                    raise ValueError("The URL did not return an HTML webpage.")
                body = bytearray()
                for chunk in response.iter_content(65536):
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise ValueError("Webpage exceeds the 2 MB retrieval limit.")
                return parse_conference_html(bytes(body), url, current)
    raise ValueError("Too many website redirects.")
