#!/usr/bin/env python3
"""
NCERT & NCTB Automated Textbook Downloader
==========================================
Downloads textbook PDFs from:
  1. NCERT (National Council of Educational Research and Training - India)
     - Target: Classes 1 to 12 (+ Vocational Education portal)
     - Languages: English Version & Bengali Version (where available)
     - Structure: NCERT / {N}. Class-{Roman} / {Subject}-C{ClassNum} / {BookTitle}-C{ClassNum} /
                  {BookTitle}-C{ClassNum}-{ChapterLabel}-{orig}.pdf
     - Method: Complete book ZIP download and automatic extraction to chapter PDFs.
  2. NCTB (National Curriculum and Textbook Board - Bangladesh)
     - Target: Pre-Primary, Primary, Secondary, Higher Secondary, Ibtedayi, Dakhil, Vocational, Ethnic Minority
     - Academic Year: Configurable & strictly filtered (e.g. AY2026, AY25-26, AY26-27)
     - Naming: C{n}, IC{n}, DC{n}, VC{n}, C0/GC (Pre-Primary), EMC & CC/GC/MC/SC/TC (Ethnic Minority)
     - Method: Direct download via eGovCloud with Google Drive fallback.

Resumable: Skips already downloaded books.
"""

import os
import sys
import re
import ssl
import time
import shutil
import zipfile
import argparse
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

# ------------------------------------------------------------------------------
# Default Academic Years
# ------------------------------------------------------------------------------
DEFAULT_ACADEMIC_YEAR = "2026"
DEFAULT_NCERT_ACADEMIC_YEAR = "2026-2027"

# ------------------------------------------------------------------------------
# SSL Configuration for Secure and Unverified Government Endpoints
# ------------------------------------------------------------------------------
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ------------------------------------------------------------------------------
# Standard Request Headers
# ------------------------------------------------------------------------------
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

# ------------------------------------------------------------------------------
# Target Portal URLs
# ------------------------------------------------------------------------------
NCERT_BASE_URL = 'https://ncert.nic.in/textbook.php?ln=en'
NCERT_VOCATIONAL_URL = 'https://ncert.nic.in/vocational.php'
NCERT_ZIP_BASE = 'https://ncert.nic.in/textbook/pdf/{code}dd.zip'
NCERT_CHAP_BASE = 'https://ncert.nic.in/textbook/pdf/{code}{part}.pdf'
NCERT_VOC_ZIP_BASE = 'https://ncert.nic.in/vocational/pdf/{code}dd.zip'
NCERT_VOC_CHAP_BASE = 'https://ncert.nic.in/vocational/pdf/{code}{part}.pdf'

NCTB_START_URL = 'https://nctb.gov.bd/pages/static-pages/695b97ffc4774958d7b70329'
NCTB_LISTENING_URL = 'https://nctb.gov.bd/pages/static-pages/6922de8f933eb65569e1b977'
NCTB_HOME_URL = 'https://nctb.gov.bd'
NCTB_BASE_URL = 'https://nctb.gov.bd'

NCTB_YEAR_URLS = {
    '2026': 'https://nctb.gov.bd/pages/static-pages/695b97ffc4774958d7b70329',
    '2025-2026': 'https://nctb.gov.bd/pages/static-pages/695b97ffc4774958d7b70329',
    '2026-2027': 'https://nctb.gov.bd/pages/static-pages/695b97ffc4774958d7b70329',
    '2025': 'https://nctb.gov.bd/pages/static-pages/6922df2c933eb65569e20586',
    '2024': 'https://nctb.gov.bd/pages/static-pages/6922de68933eb65569e1a70c',
    '2023': 'https://nctb.gov.bd/pages/static-pages/6922dd35933eb65569e13f12',
    '2022': 'https://nctb.gov.bd/pages/static-pages/6922dce3933eb65569e12943',
    '2021': 'https://nctb.gov.bd/pages/static-pages/6922dbc9933eb65569e0c85a',
    '2020': 'https://nctb.gov.bd/pages/static-pages/6922dd7f933eb65569e15431',
    '2019': 'https://nctb.gov.bd/pages/static-pages/6922db65933eb65569e09ead',
    '2018': 'https://nctb.gov.bd/pages/static-pages/6922dfc9933eb65569e23fcb',
    '2017': 'https://nctb.gov.bd/pages/static-pages/6922dfc9933eb65569e23fcb',
}

# ------------------------------------------------------------------------------
# Mappings
# ------------------------------------------------------------------------------
ROMAN_CLASS_MAP = {
    1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI',
    7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X', 11: 'XI', 12: 'XII',
    13: 'XI-XII', 14: 'XI-XII'
}

STAGE_FOLDER_MAP = {
    'Pre-Primary': '1. Pre-Primary',
    'Primary': '2. Primary',
    'Secondary': '3. Secondary',
    'Higher Secondary': '4. Higher Secondary',
    'Ibtedayi': '5. Ibtedayi',
    'Dakhil': '6. Dakhil',
    'Vocational': '7. Vocational',
    'Ethnic Minority': '8. Ethnic Minority',
}

STAGE_CLASS_PREFIX = {
    'Primary': 'GC',
    'Secondary': 'GC',
    'Higher Secondary': 'GC',
    'Ibtedayi': 'IC',
    'Dakhil': 'DC',
    'Vocational': 'VC',
}

STAGE_FULL_CLASS_NAME = {
    'Primary': 'General Class',
    'Secondary': 'General Class',
    'Higher Secondary': 'General Class',
    'Ibtedayi': 'Ibtedayi Class',
    'Dakhil': 'Dakhil Class',
    'Vocational': 'Vocational Class',
}

ETHNIC_PREFIX_MAP = {
    'Chakma': 'CC',
    'Garo': 'GC',
    'Marma': 'MC',
    'Sadri': 'SC',
    'Tripura': 'TC',
}

NCERT_PART_LABELS = {
    'ps': 'Prelims',
    'a1': 'A1',
    'a2': 'A2',
    'an': 'Answers',
    'ax': 'Appendix',
    'gl': 'Glossary',
    'sm': 'SM',
    'wc': 'WC',
    'cc': 'CC',
    'bt': 'BT',
    'tn': 'TN',
    'lp': 'LP',
    'rf': 'RF',
    'in': 'IN',
    'qa': 'QA',
    'pp': 'PP',
    'gs': 'GS',
}

BN_DIGITS = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')


def normalize_digits(text: str) -> str:
    """Convert Bengali numerals to ASCII digits."""
    return text.translate(BN_DIGITS)


def sanitize_filename(name: str) -> str:
    """Sanitize string for safe folder and file names across all operating systems."""
    name = re.sub(r'&nbsp;?', ' ', name)
    name = re.sub(r'<[^>]+>', '', name)
    name = re.sub(r'[/\\:*?\"<>|]', '_', name)
    return ' '.join(name.split()).strip('. ')


def fetch_url(url: str, timeout: int = 25, retries: int = 3) -> str:
    """Fetch URL text content with automatic retry and curl fallback on TLS reset."""
    if not url.startswith('http'):
        url = urllib.parse.urljoin(NCTB_BASE_URL, url)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception:
            try:
                import subprocess
                res = subprocess.run(
                    ['curl', '-sL', '--max-time', str(timeout), '-A', HEADERS['User-Agent'], url],
                    capture_output=True, text=True, errors='ignore'
                )
                if res.returncode == 0 and len(res.stdout) > 200:
                    return res.stdout
            except Exception:
                pass
            if attempt == retries - 1:
                return ""
            time.sleep(1.5 * (attempt + 1))
    return ""


def download_stream(url: str, dest_path: str, timeout: int = 45) -> bool:
    """Download a file with 1MB chunked streaming (and curl fallback on TLS reset)."""
    tmp_path = dest_path + '.tmp'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
            if resp.status != 200:
                return False
            with open(tmp_path, 'wb') as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1000:
            os.replace(tmp_path, dest_path)
            return True
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        try:
            import subprocess
            res = subprocess.run(
                ['curl', '-sL', '--fail', '--max-time', str(timeout), '-A', HEADERS['User-Agent'], url, '-o', tmp_path],
                capture_output=True
            )
            if res.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1000:
                os.replace(tmp_path, dest_path)
                return True
        except Exception:
            pass
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    return False


def search_web_for_book_links(query: str, max_results: int = 5) -> list:
    """Search DuckDuckGo HTML for fallback PDF/Drive/archive URLs when saved links fail."""
    search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    html = fetch_url(search_url, timeout=15, retries=1)
    if not html:
        return []

    raw_hrefs = re.findall(r'class=[\"\']result__a[\"\'][^>]*href=[\"\']([^\"\']+)[\"\']', html, re.I)
    if not raw_hrefs:
        raw_hrefs = re.findall(r'href=[\"\']([^\"\']*uddg=[^\"\']+)[\"\']', html, re.I)

    urls = []
    for href in raw_hrefs:
        if 'uddg=' in href:
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            target = parsed.get('uddg', [''])[0]
        else:
            target = href
        if target.startswith('http') and target not in urls:
            urls.append(target)

    # Prioritize direct PDFs, Google Drive, eGovCloud, and official portals
    def _rank(u: str) -> int:
        ul = u.lower()
        if ul.endswith('.pdf'):
            return 0
        if 'drive.google.com' in ul or 'egovcloud' in ul:
            return 1
        if 'nctb.gov.bd' in ul or 'ncert.nic.in' in ul:
            return 2
        return 3

    urls.sort(key=_rank)
    return urls[:max_results]


def download_gdrive(file_id: str, dest_path: str, timeout: int = 90) -> bool:
    """Download file from Google Drive, handling modern form confirmations and tokens."""
    tmp_path = dest_path + '.tmp'
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with opener.open(req, timeout=timeout) as resp:
            first_chunk = resp.read(2048)
            if b'%PDF' in first_chunk or resp.headers.get('Content-Disposition'):
                with open(tmp_path, 'wb') as f:
                    f.write(first_chunk)
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1000:
                    os.replace(tmp_path, dest_path)
                    return True
            else:
                html = (first_chunk + resp.read()).decode('utf-8', errors='ignore')

                # Strategy A: Modern Google Drive download form
                action_m = re.search(r'action=[\"\']([^\"\']+)[\"\']', html)
                inputs = dict(re.findall(r'<input\b[^>]*name=[\"\']([^\"\']+)[\"\'][^>]*value=[\"\']([^\"\']*)[\"\']', html))
                if action_m and inputs:
                    action = action_m.group(1)
                    if not action.startswith('http'):
                        action = 'https://drive.usercontent.google.com/download'
                    query = '&'.join([f"{k}={v}" for k, v in inputs.items()])
                    download_url = f"{action}?{query}"
                    req2 = urllib.request.Request(download_url, headers=HEADERS)
                    with opener.open(req2, timeout=timeout) as resp2, open(tmp_path, 'wb') as f2:
                        while True:
                            chunk = resp2.read(1024 * 1024)
                            if not chunk:
                                break
                            f2.write(chunk)
                    if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1000:
                        os.replace(tmp_path, dest_path)
                        return True

                # Strategy B: Legacy confirm token
                confirm_match = re.search(r'confirm=([0-9A-Za-z_]+)', html)
                if confirm_match:
                    token = confirm_match.group(1)
                    confirm_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm={token}"
                    req3 = urllib.request.Request(confirm_url, headers=HEADERS)
                    with opener.open(req3, timeout=timeout) as resp3, open(tmp_path, 'wb') as f3:
                        while True:
                            chunk = resp3.read(1024 * 1024)
                            if not chunk:
                                break
                            f3.write(chunk)
                    if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1000:
                        os.replace(tmp_path, dest_path)
                        return True
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    return False


# ==============================================================================
# NCTB SUBJECT CLASSIFIER
# ==============================================================================

def classify_nctb_subject(title: str) -> str:
    """Categorize NCTB book title into clean, standardized subject folder names."""
    t_low = title.lower()

    if any(k in t_low for k in ['গণিত', 'উচ্চতর গণিত', 'math', 'mathematics', 'higher math', 'আঙ্কিক']):
        return 'Mathematics'
    if any(k in t_low for k in ['english', 'for today', 'grammar', 'composition', 'writing', 'listening']):
        return 'English'
    if any(k in t_low for k in [
        'বাংলাদেশ ও বিশ্বপরিচয়', 'বাংলাদেশ ও বিশ্ব পরিচয়',
        'bangladesh and global studies', 'global studies'
    ]):
        return 'Bangladesh and Global Studies'
    if any(k in t_low for k in ['বাংলা', 'সাহিত্য', 'সহপাঠ', 'ব্যাকরণ', 'নির্মিতি', 'আমার বাংলা বই', 'ভাষার']):
        return 'Bangla'
    if any(k in t_low for k in ['গার্হস্থ্য', 'গার্হস্থ্যবিজ্ঞান', 'home science']):
        return 'Home Science'
    if any(k in t_low for k in ['কৃষি', 'কৃষিশিক্ষা', 'agriculture', 'কৃষি শিক্ষা']):
        return 'Agriculture'
    if any(k in t_low for k in ['তথ্য ও যোগাযোগ প্রযুক্তি', 'কম্পিউটার', 'ict', 'computer', 'information and communication', 'ক্যাড', 'cad']):
        return 'ICT & Computer'
    if any(k in t_low for k in ['শারীরিক শিক্ষা', 'স্বাস্থ্য', 'খেলাধুলা', 'physical', 'health']):
        return 'Physical Education & Health'
    if any(k in t_low for k in ['চারু ও কারুকলা', 'চারু', 'কারু', 'আঁকিবুঁকি', 'arts and crafts', 'art', 'craft']):
        return 'Arts & Crafts'
    if any(k in t_low for k in ['সংগীত', 'সঙ্গীত', 'music']):
        return 'Music'
    if any(k in t_low for k in ['কর্ম ও জীবনমুখী', 'কর্ম', 'work and life', 'career', 'work']):
        return 'Career & Life Skills'
    if any(k in t_low for k in ['পদার্থবিজ্ঞান', 'পদার্থ', 'physics']):
        return 'Physics'
    if any(k in t_low for k in ['রসায়ন', 'রসায়ন', 'chemistry']):
        return 'Chemistry'
    if any(k in t_low for k in ['জীববিজ্ঞান', 'জীব', 'biology', 'botany', 'zoology']):
        return 'Biology'
    if any(k in t_low for k in ['বিজ্ঞান', 'science', 'সাধারণ বিজ্ঞান', 'general science']):
        return 'Science'
    if any(k in t_low for k in [
        'ইতিহাস', 'ভূগোল', 'পরিবেশ', 'পৌরনীতি', 'নাগরিকতা',
        'অর্থনীতি', 'সমাজবিজ্ঞান', 'সমাজকর্ম',
        'social', 'history', 'geography', 'economics', 'civics'
    ]):
        return 'Social Science & Humanities'
    if any(k in t_low for k in [
        'ব্যবসায়', 'ব্যবসা', 'হিসাববিজ্ঞান', 'ফিন্যান্স', 'ব্যাংকিং',
        'business', 'accounting', 'finance', 'ব্যবস্থাপনা', 'উদ্যোগ'
    ]):
        return 'Business & Commerce'
    if any(k in t_low for k in [
        'ধর্ম', 'ইসলাম', 'কুরআন', 'হাদিস', 'ফিকহ', 'আকাইদ', 'হিন্দুধর্ম',
        'বৌদ্ধধর্ম', 'খ্রিস্টধর্ম', 'moral', 'religion', 'islam', 'hindu',
        'buddhist', 'christian', 'তাজভিদ', 'আরবি'
    ]):
        return 'Religion & Ethics'

    return 'General'


# ==============================================================================
# NCERT CRAWLER & DOWNLOADER
# ==============================================================================

def format_ncert_pdf_name(book_folder_name: str, orig_filename: str, ay_tag: str = 'AY26-27') -> str:
    """Format NCERT chapter PDF as {BookName}-(GC|VC){Class}-{ChapterLabel}-AY26-27-{orig_stem}.pdf."""
    m_cls = re.search(r'-((?:GC|VC|C)\d+(?:-\d+)?)$', book_folder_name)
    if m_cls:
        cls_tag = m_cls.group(1)
        book_name = book_folder_name[:m_cls.start()]
    else:
        cls_tag = 'GC0'
        book_name = book_folder_name

    stem = os.path.splitext(orig_filename)[0].rstrip('.')
    if orig_filename.startswith(f"{book_name}-{cls_tag}-"):
        return orig_filename

    m_code = re.match(
        r'^([a-z0-9]+?)(p[12]\d{2}|[0-9]{2}|ps|bt|a1|a2|an|ax|cc|gl|sm|tn|lp|rf|in|wc|qa|pp|gs)$',
        stem,
        re.I
    )
    if m_code:
        suffix = m_code.group(2).lower()
        if suffix.isdigit():
            chap_label = f"Ch{int(suffix):02d}"
        elif re.match(r'^p([12])(\d{2})$', suffix):
            pm = re.match(r'^p([12])(\d{2})$', suffix)
            chap_label = f"P{pm.group(1)}-Ch{int(pm.group(2)):02d}"
        else:
            chap_label = NCERT_PART_LABELS.get(suffix, suffix.upper())
    else:
        chap_label = 'File'

    return f"{book_name}-{cls_tag}-{chap_label}-{ay_tag}-{stem}.pdf"


def get_ncert_books(include_vocational: bool = False):
    """Parse textbook.php?ln=en JavaScript code and optionally the NCERT Vocational Education portal."""
    print(f"[*] Crawling NCERT catalog from {NCERT_BASE_URL} ...")
    html = fetch_url(NCERT_BASE_URL)
    books = []

    if not html:
        print("[!] Could not load NCERT webpage.")
    else:
        scripts = re.findall(r'<script\b[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
        if len(scripts) < 18:
            print("[!] NCERT script tag structure changed.")
        else:
            s17 = scripts[17]
            clean_s17 = re.sub(r'/\*.*?\*/', '', s17, flags=re.DOTALL)
            clean_s17 = '\n'.join([re.sub(r'//.*$', '', l) for l in clean_s17.split('\n')])

            pattern = r'if\s*\(\s*\(document\.test\.tclass\.value\s*==\s*[\"\']?(\d+)[\"\']?\)\s*&&\s*\(document\.test\.tsubject\.options\[sind\]\.text\s*==\s*[\"\']([^\"\']+)[\"\']\)\s*\)\s*\{([^}]+)\}'
            matches = re.findall(pattern, clean_s17, re.DOTALL)

            non_eng_bengali_tags = {
                'hindi', 'urdu', 'marathi', 'sanskrit', 'gujarati', 'gujrati', 'punjabi',
                'sindhi', 'malayalam', 'konkani', 'bodo', 'dogri', 'kannada', 'kashmiri',
                'maithili', 'maithli', 'manipuri', 'nepali', 'odia', 'oriya', 'santhali',
                'tamil', 'telugu', 'assamese'
            }

            def classify_language(subj: str, title: str, code: str):
                t_low = title.lower()
                c_low = code.lower()
                if 'bengali' in t_low or 'bangla' in t_low or re.match(r'^[a-z]bn[a-z0-9]', c_low):
                    return True, 'Bengali Version'
                for lang in non_eng_bengali_tags:
                    if f'({lang})' in t_low:
                        return False, lang
                if '(english)' in t_low or subj.strip().lower() == 'english' or re.match(r'^[a-z]e[a-z0-9]', c_low):
                    return True, 'English Version'
                if any(k in t_low for k in [
                    'mathematics', 'science', 'physics', 'chemistry', 'biology', 'history',
                    'geography', 'economics', 'english', 'computer', 'accountancy', 'business',
                    'sociology', 'political', 'psychology', 'technology', 'vocational', 'health'
                ]):
                    return True, 'English Version'
                return False, 'Other'

            seen_codes = set()
            for cls_str, subj, block in matches:
                # Skip partial 'Vocational' trade entries in textbook.php (handled properly via vocational.php when include_vocational=True;
                # keeps Class 6-8 'Vocational Education' (Kaushal Bodh) and Class 9 'Skill Education' (Kaushal Vikas))
                if subj.strip().lower() == 'vocational':
                    continue
                cls_num = int(cls_str)
                texts = dict(re.findall(r'document\.test\.tbook\.options\[(\d+)\]\.text\s*=\s*[\"\']([^\"\']+)[\"\']', block))
                raw_vals = re.findall(r'document\.test\.tbook\.options\[(\d+)\]\.value\s*=\s*[\"\']textbook\.php\?([^\"\'=]+)=([^\"\'&]+)[\"\']', block)

                for idx, code, rng in raw_vals:
                    code = code.strip()
                    title = texts.get(idx, 'Unknown').strip()
                    if title.startswith('..') or not title:
                        continue

                    is_target, lang = classify_language(subj, title, code)
                    if is_target and code not in seen_codes:
                        seen_codes.add(code)
                        books.append({
                            'source': 'NCERT',
                            'class_num': cls_num,
                            'subject': sanitize_filename(subj.strip()),
                            'title': sanitize_filename(title),
                            'code': code,
                            'range': rng.strip(),
                            'lang': lang,
                            'zip_url': NCERT_ZIP_BASE.format(code=code)
                        })

    if include_vocational:
        voc_books = get_ncert_vocational_books()
        existing_keys = {b['code'] for b in books}
        for vb in voc_books:
            if vb['code'] not in existing_keys:
                books.append(vb)
                existing_keys.add(vb['code'])

    print(f"[✓] NCERT books discovered: {len(books)} (English: {sum(1 for b in books if b['lang']=='English Version')}, Bengali: {sum(1 for b in books if b['lang']=='Bengali Version')})")
    return books


def get_ncert_vocational_books():
    """Crawl NCERT Vocational portal (https://ncert.nic.in/vocational.php) for Classes IX-XII."""
    print(f"[*] Crawling NCERT Vocational Education from {NCERT_VOCATIONAL_URL} ...")
    html = fetch_url(NCERT_VOCATIONAL_URL, timeout=30)
    if not html:
        print("[!] Could not load NCERT Vocational webpage.")
        return []

    clean_js = re.sub(r'/\*.*?\*/', '', html, flags=re.DOTALL)
    clean_js = '\n'.join([re.sub(r'//.*$', '', l) for l in clean_js.split('\n')])

    pattern = r'if\s*\(\s*\(document\.test\.tclass\.value\s*==\s*[\"\']?(\d+)[\"\']?\)\s*&&\s*\(document\.test\.tsubject\.options\[sind\]\.text\s*==\s*[\"\']([^\"\']+)[\"\']\)\s*\)\s*\{([^}]+)\}'
    matches = re.findall(pattern, clean_js, re.DOTALL)

    tclass_to_num = {'2': 9, '5': 10, '3': 11, '4': 12}
    prefix_to_num = {'i': 9, 'j': 10, 'k': 11, 'l': 12, 'g': 7}

    voc_books = []
    seen_codes = set()

    for cls_str, subj, block in matches:
        texts = dict(re.findall(r'document\.test\.tbook\.options\[(\d+)\]\.text\s*=\s*[\"\']([^\"\']+)[\"\']', block))
        raw_vals = re.findall(r'document\.test\.tbook\.options\[(\d+)\]\.value\s*=\s*[\"\']vocational\.php\?([^\"\'=]+)=([^\"\'&]+)[\"\']', block)

        for idx, code, rng in raw_vals:
            code = code.strip()
            title = texts.get(idx, '').strip()
            if not title or title.startswith('..'):
                continue

            c_low = code.lower()
            t_low = title.lower()
            # Filter out Hindi-medium vocational books (note: jhde1 in Class 10 IT-ITeS is English despite 'jh' prefix)
            if '(hindi)' in t_low or any(w in t_low for w in (
                'kshamta', 'shamta', 'taknisian', 'krshak', 'samanya',
                'suraksha', 'saundarya', 'kashidakaar', 'trani'
            )):
                continue

            cls_num = prefix_to_num.get(c_low[0], tclass_to_num.get(cls_str, 9))
            if cls_num not in (9, 10, 11, 12):
                continue

            if code not in seen_codes:
                seen_codes.add(code)
                voc_books.append({
                    'source': 'NCERT',
                    'class_num': cls_num,
                    'subject': sanitize_filename(subj.strip()),
                    'title': sanitize_filename(title),
                    'code': code,
                    'range': rng.strip(),
                    'lang': 'English Version',
                    'is_vocational_portal': True,
                    'zip_url': NCERT_VOC_ZIP_BASE.format(code=code),
                    'chap_base': NCERT_VOC_CHAP_BASE,
                })

    print(f"[✓] NCERT Vocational books (IX-XII, English) discovered: {len(voc_books)}")
    return voc_books


def _parse_class_num(token: str) -> int:
    roman_to_int = {'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10, 'XI': 11, 'XII': 12}
    t = token.strip().upper()
    if t in roman_to_int:
        return roman_to_int[t]
    try:
        return int(t)
    except ValueError:
        return 9


def get_standard_ncert_dir(book: dict, base_dir: str = '.') -> str:
    """Format folder path: NCERT/Academic Year 2026-2027/{N}. General Class-{Roman}/{Subject}-GC{ClassNum}/{BookTitle}-GC{ClassNum}."""
    cls_num = book['class_num']
    if cls_num in [13, 14]:
        cls_str = "11-12"
        roman = "XI-XII"
        cls_prefix_num = "11-12"
    else:
        cls_str = str(cls_num)
        roman = ROMAN_CLASS_MAP.get(cls_num, str(cls_num))
        cls_prefix_num = str(cls_num)

    raw_subject = book.get('subject', 'General').strip()
    subj_low = raw_subject.lower()
    if 'math' in subj_low:
        subj_name = 'Mathematics'
    elif 'english' in subj_low:
        subj_name = 'English'
    elif 'fine art' in subj_low or 'arts' in subj_low or 'graphics' in subj_low:
        subj_name = 'Arts'
    elif 'physical education' in subj_low or 'health' in subj_low:
        subj_name = 'Physical Education'
    elif 'world around' in subj_low:
        subj_name = 'The World Around Us'
    elif 'political' in subj_low:
        subj_name = 'Political Science'
    elif 'computer' in subj_low or 'informatics' in subj_low:
        subj_name = 'Computer Science'
    elif 'home science' in subj_low:
        subj_name = 'Home Science'
    elif 'social science' in subj_low:
        subj_name = 'Social Science'
    elif 'vocational' in subj_low or 'skill' in subj_low:
        subj_name = 'Vocational Education'
    elif subj_low in ['science', 'general science']:
        subj_name = 'Science'
    else:
        subj_name = raw_subject

    is_voc_portal = bool(book.get('is_vocational_portal'))
    short_prefix = 'VC' if is_voc_portal else 'GC'
    class_folder = f"{cls_prefix_num}. {'Vocational Class' if is_voc_portal else 'General Class'}-{roman}"

    title = book['title']
    part_match = re.search(r'Part[\s-]*([IVX]+|\d+)', title, re.IGNORECASE) or re.search(r'[-–\s]([IVX]+|\d+)$', title)
    part_str = ''
    clean_title = title
    if part_match:
        p_val = part_match.group(1).upper()
        if p_val in ['I', '1']:
            part_str = '-P1'
        elif p_val in ['II', '2']:
            part_str = '-P2'
        elif p_val in ['III', '3']:
            part_str = '-P3'
        clean_title = re.sub(r'[\s-]*Part[\s-]*[IVX0-9]+', '', clean_title, flags=re.IGNORECASE).strip()

    clean_title = re.sub(r'[/\\:*?\"<>|]', '', clean_title).strip()
    clean_title = re.sub(r'\s*\((?:Bengali|English)\)', '', clean_title, flags=re.IGNORECASE).strip()

    lang_tag = '(Bengali)' if book['lang'] == 'Bengali Version' else '(English)'
    if subj_name == 'English':
        book_folder_name = f"{clean_title}{part_str}-{short_prefix}{cls_str}"
    else:
        book_folder_name = f"{clean_title} {lang_tag}{part_str}-{short_prefix}{cls_str}"

    book_folder_name = re.sub(r'\s+', ' ', book_folder_name).strip()
    subject_folder_name = f"{subj_name}-{short_prefix}{cls_str}"

    if is_voc_portal:
        return os.path.join(base_dir, 'NCERT', f'Academic Year {DEFAULT_NCERT_ACADEMIC_YEAR}', '13. Vocational Education', class_folder, subject_folder_name, book_folder_name)

    return os.path.join(base_dir, 'NCERT', f'Academic Year {DEFAULT_NCERT_ACADEMIC_YEAR}', class_folder, subject_folder_name, book_folder_name)


def scan_existing_ncert_codes(base_dir: str = 'NCERT') -> dict:
    """Scan the NCERT directory to register any previously downloaded book codes (old or renamed)."""
    code_map = {}
    if not os.path.exists(base_dir):
        return code_map

    suffix_re = r'(?:p[12]\d{2}|[0-9]{2}|ps|bt|a1|a2|an|ax|cc|gl|sm|tn|lp|rf|in|wc|qa|pp|gs)'
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if not f.lower().endswith('.pdf'):
                continue
            stem = f[:-4].rstrip('.')
            # Match either raw code (aejm101) or renamed (...-aejm101)
            last_part = stem.split('-')[-1]
            m = re.match(rf'^([a-z0-9]+?){suffix_re}$', last_part, re.IGNORECASE)
            if m:
                code_map.setdefault(m.group(1).lower(), root)
    return code_map


def download_ncert_book(book: dict, base_dir: str, existing_codes: dict) -> bool:
    """Download NCERT complete book zip/PDF, extract, flatten, and standardize PDF names."""
    target_dir = get_standard_ncert_dir(book, base_dir)
    book_folder_name = os.path.basename(target_dir)
    book_code = book['code'].lower()

    if not book.get('is_vocational_portal') and book_code in existing_codes:
        existing_path = existing_codes[book_code]
        print(f"[SKIP] NCERT [{book['title']}] - Already exists in {existing_path}")
        return True

    if os.path.exists(target_dir):
        existing_pdfs = [
            f for f in os.listdir(target_dir)
            if f.lower().endswith('.pdf') and os.path.getsize(os.path.join(target_dir, f)) > 1000
        ]
        if len(existing_pdfs) >= 3 or (book.get('direct_url') and len(existing_pdfs) >= 1):
            print(f"[SKIP] NCERT [{book['title']}] - Already exists ({len(existing_pdfs)} PDFs).")
            return True

    os.makedirs(target_dir, exist_ok=True)
    cls_roman = ROMAN_CLASS_MAP.get(book['class_num'], str(book['class_num']))

    # Direct single-PDF vocational book support
    if book.get('direct_url') and book['direct_url'].lower().endswith('.pdf'):
        orig_name = os.path.basename(urllib.parse.urlparse(book['direct_url']).path) or f"{book_code}.pdf"
        dest_name = format_ncert_pdf_name(book_folder_name, orig_name)
        dest_path = os.path.join(target_dir, dest_name)
        print(f"[NCERT] Downloading [Class-{cls_roman}] {book['title']} ...")
        if download_stream(book['direct_url'], dest_path, timeout=90):
            print(f"[✓] NCERT [Class-{cls_roman}] {book['title']} -> Saved {dest_name}")
            return True
        print(f"[✗] NCERT [Class-{cls_roman}] Failed: {book['title']}")
        return False

    zip_url = book['zip_url']
    tmp_zip = os.path.join(target_dir, f"{book['code']}_temp.zip")

    print(f"[NCERT] Downloading [Class-{cls_roman}] {book['title']} ({book['lang']}) ...")
    success = download_stream(zip_url, tmp_zip, timeout=90) if zip_url else False

    if success and os.path.exists(tmp_zip):
        try:
            with zipfile.ZipFile(tmp_zip, 'r') as zf:
                zf.extractall(target_dir)
            os.remove(tmp_zip)

            # Flatten nested subfolders
            for item in os.listdir(target_dir):
                item_path = os.path.join(target_dir, item)
                if os.path.isdir(item_path):
                    for sub_root, sub_dirs, sub_files in os.walk(item_path):
                        for f in sub_files:
                            src_f = os.path.join(sub_root, f)
                            dst_f = os.path.join(target_dir, f)
                            if not os.path.exists(dst_f):
                                shutil.move(src_f, dst_f)
                    try:
                        shutil.rmtree(item_path)
                    except Exception:
                        pass

            # Rename extracted PDFs to {BookName}-C{Class}-{Chapter}-{orig}.pdf
            for f in os.listdir(target_dir):
                if f.lower().endswith('.pdf'):
                    new_name = format_ncert_pdf_name(book_folder_name, f)
                    if new_name != f:
                        src_f = os.path.join(target_dir, f)
                        dst_f = os.path.join(target_dir, new_name)
                        if not os.path.exists(dst_f):
                            os.replace(src_f, dst_f)

            extracted_count = len([f for f in os.listdir(target_dir) if f.lower().endswith('.pdf')])
            print(f"[✓] NCERT [Class-{cls_roman}] {book['title']} -> Extracted {extracted_count} chapters.")
            return True
        except Exception:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)

    # Fallback to chapter-wise download if zip is unavailable
    parts = ['ps']
    try:
        max_chap = int(book['range'].split('-')[1])
        for ch in range(1, max_chap + 1):
            parts.append(f"{ch:02d}")
    except Exception:
        parts.extend([f"{i:02d}" for i in range(1, 20)])
    parts.extend(['a1', 'a2', 'an', 'ax'])

    chap_base = book.get('chap_base', NCERT_CHAP_BASE)
    downloaded = 0
    for p in parts:
        orig_name = f"{book['code']}{p}.pdf"
        renamed_name = format_ncert_pdf_name(book_folder_name, orig_name)
        chap_url = chap_base.format(code=book['code'], part=p)
        chap_path = os.path.join(target_dir, renamed_name)
        if os.path.exists(chap_path) and os.path.getsize(chap_path) > 1000:
            downloaded += 1
            continue
        if download_stream(chap_url, chap_path, timeout=30):
            downloaded += 1

    if downloaded > 0:
        print(f"[✓] NCERT [Class-{cls_roman}] {book['title']} -> {downloaded} chapters downloaded.")
        return True

    print(f"[✗] NCERT [Class-{cls_roman}] Failed: {book['title']}")
    return False


# ==============================================================================
# NCTB CRAWLER & DOWNLOADER (WITH STRICT ACADEMIC YEAR FILTERING)
# ==============================================================================

def _format_hs_ay_tag(academic_year: str) -> str:
    """Convert '2025-2026' -> 'AY25-26', '2026-2027' -> 'AY26-27', or '2026' -> 'AY2026'."""
    m = re.match(r'^(\d{4})-(\d{4})$', academic_year.strip())
    if m:
        return f"AY{m.group(1)[2:]}-{m.group(2)[2:]}"
    if academic_year.startswith('AY'):
        return academic_year
    return f"AY{academic_year}"


def _matches_academic_year(page_text: str, requested_year: str) -> bool:
    """Strictly verify whether a scraped NCTB page belongs to the requested academic year."""
    norm = normalize_digits(page_text)
    req = normalize_digits(requested_year).strip()

    # Extract 4-digit years (2015..2035) mentioned in the page title/header
    years_found = re.findall(r'\b(20[1-3]\d)\b', norm)
    if not years_found:
        # If the portal page itself doesn't stamp a year in title, allow only if we entered from that year's portal
        return True

    if '-' in req:
        # Exact range like 2025-2026
        parts = req.split('-')
        return all(p in years_found for p in parts)

    # Single year: match exact year, OR shared 2017/2018 archive
    if req == '2017' and NCTB_YEAR_URLS.get('2017') == NCTB_YEAR_URLS.get('2018'):
        return '2017' in years_found or '2018' in years_found
    return req in years_found


def _find_nctb_portal_url_for_year(academic_year: str, allow_web_search: bool = True) -> str:
    """Find the NCTB textbook portal URL: saved archive links -> homepage -> web search fallback."""
    req_year = normalize_digits(academic_year).strip()
    if req_year in NCTB_YEAR_URLS:
        return NCTB_YEAR_URLS[req_year]

    # Fallback 1: Crawl NCTB homepage / textbook menu for links mentioning the requested academic year
    home_html = fetch_url(NCTB_HOME_URL)
    if home_html:
        anchors = re.findall(r'<a\b[^>]*href=[\"\']([^\"\']+)[\"\'][^>]*>(.*?)</a>', home_html, re.DOTALL | re.IGNORECASE)
        for href, txt in anchors:
            clean_txt = normalize_digits(re.sub(r'<[^>]+>', ' ', txt))
            if req_year in clean_txt and ('পাঠ্যপুস্তক' in clean_txt or 'textbook' in clean_txt.lower() or 'বই' in clean_txt):
                return urllib.parse.urljoin(NCTB_BASE_URL, href)

    # Fallback 2: Search the web for NCTB static-pages URL for this academic year
    if allow_web_search:
        print(f"[*] Year {req_year} not in saved links; searching the web for NCTB archive URL...")
        found = search_web_for_book_links(f'site:nctb.gov.bd/pages/static-pages {req_year} পাঠ্যপুস্তক')
        for u in found:
            if 'nctb.gov.bd/pages/static-pages/' in u:
                print(f"[✓] Found NCTB archive URL via web search: {u}")
                return u

    return NCTB_START_URL


def get_nctb_books(academic_year: str = DEFAULT_ACADEMIC_YEAR, allow_web_search: bool = True):
    """Crawl NCTB static pages hierarchy and extract books strictly for the requested academic year."""
    req_year = normalize_digits(academic_year).strip()
    start_url = _find_nctb_portal_url_for_year(req_year, allow_web_search=allow_web_search)
    print(f"[*] Crawling NCTB catalog (Academic Year: {req_year}) from {start_url} ...")

    start_html = fetch_url(start_url)
    if not start_html:
        print("[!] Could not load NCTB main page.")
        return []

    start_tables = re.findall(r'<table\b[^>]*>(.*?)</table>', start_html, re.DOTALL | re.IGNORECASE)
    if not start_tables:
        print("[!] NCTB table structure not found.")
        return []

    level_links = []
    for tbl in start_tables:
        for h in re.findall(r'href=[\"\']([^\"\']+)[\"\']', tbl):
            if h not in level_links:
                level_links.append(h)

    class_urls = []
    for h in level_links:
        html = fetch_url(h)
        tables = re.findall(r'<table\b[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)
        has_direct_books = False
        for tbl in tables:
            for u in re.findall(r'href=[\"\']([^\"\']+)[\"\']', tbl):
                u_low = u.lower()
                if 'drive.google.com' in u_low or 'egovcloud' in u_low or u_low.endswith('.pdf'):
                    has_direct_books = True
                elif 'static-pages' in u and u not in class_urls:
                    class_urls.append(u)
        if has_direct_books and h not in class_urls:
            class_urls.append(h)

    print(f"[*] Found {len(class_urls)} NCTB class/category pages to inspect.")
    all_books = []

    for page_url in class_urls:
        html = fetch_url(page_url)
        if not html:
            continue

        title_m = re.findall(r'<title>(.*?)</title>', html, re.IGNORECASE)
        raw_page_title = title_m[0].split('|')[0].strip() if title_m else 'General'
        if raw_page_title == 'পাতা' or 'জাতীয় শিক্ষাক্রম' in raw_page_title:
            headings = re.findall(r'<h[1-4]\b[^>]*>(.*?)</h[1-4]>', html, re.DOTALL | re.IGNORECASE)
            for h in headings:
                clean_h = re.sub(r'<[^>]+>', '', h).strip()
                if any(k in clean_h for k in ['শ্রেণি', 'স্তর', 'দাখিল', 'মাধ্যমিক', 'কারিগরি', 'প্রাথমিক', 'শিক্ষাবর্ষ']):
                    raw_page_title = clean_h
                    break

        # Strict academic year check against page title & main heading
        if not _matches_academic_year(raw_page_title, req_year):
            continue

        stage = "General"
        if "ক্ষুদ্র নৃ" in raw_page_title:
            stage = "Ethnic Minority"
        elif "প্রাক প্রাথমিক" in raw_page_title:
            stage = "Pre-Primary"
        elif "প্রাথমিক" in raw_page_title:
            stage = "Primary"
        elif "ইবতেদায়ি" in raw_page_title:
            stage = "Ibtedayi"
        elif "দাখিল" in raw_page_title:
            stage = "Dakhil"
        elif any(k in raw_page_title for k in ["কারিগরি", "ভোকেশনাল"]) or "vocational" in raw_page_title.lower():
            stage = "Vocational"
        elif "উচ্চ মাধ্যমিক" in raw_page_title:
            stage = "Higher Secondary"
        elif "মাধ্যমিক" in raw_page_title:
            stage = "Secondary"

        book_ay = req_year
        if stage == "Higher Secondary":
            norm_title = normalize_digits(raw_page_title)
            if "2025-2026" in norm_title or ("2025" in norm_title and "2026" in norm_title):
                book_ay = "2025-2026"
            elif "2026-2027" in norm_title or ("2026" in norm_title and "2027" in norm_title):
                book_ay = "2026-2027"
            elif "2025" in norm_title:
                book_ay = "2025-2026"
            elif "2026" in norm_title:
                book_ay = "2026-2027"

        if stage == "Pre-Primary":
            class_folder = "Pre-Primary"
        else:
            class_folder = sanitize_filename(raw_page_title)

        for bn_cls, en_cls in [
            ("প্রথম শ্রেণি", "Class 1"), ("১ম শ্রেণি", "Class 1"),
            ("দ্বিতীয় শ্রেণি", "Class 2"), ("২য় শ্রেণি", "Class 2"),
            ("তৃতীয় শ্রেণি", "Class 3"), ("৩য় শ্রেণি", "Class 3"),
            ("চতুর্থ শ্রেণি", "Class 4"), ("৪র্থ শ্রেণি", "Class 4"),
            ("পঞ্চম শ্রেণি", "Class 5"), ("৫ম শ্রেণি", "Class 5"),
            ("ষষ্ঠ শ্রেণি", "Class 6"), ("৬ষ্ঠ শ্রেণি", "Class 6"),
            ("সপ্তম শ্রেণি", "Class 7"), ("৭ম শ্রেণি", "Class 7"),
            ("অষ্টম শ্রেণি", "Class 8"), ("৮ম শ্রেণি", "Class 8"),
            ("নবম দশম শ্রেণি", "Class 9-10"), ("৯ম-১০ম শ্রেণি", "Class 9-10"),
            ("নবম শ্রেণি", "Class 9"), ("৯ম শ্রেণি", "Class 9"),
            ("দশম শ্রেণি", "Class 10"), ("১০ম শ্রেণি", "Class 10"), ("১০ শ্রেণি", "Class 10"),
            ("একাদশ দ্বাদশ শ্রেণি", "Class 11-12"), ("উচ্চ মাধ্যমিক শ্রেণি", "Class 11-12")
        ]:
            if bn_cls in raw_page_title:
                class_folder = en_cls
                break

        if stage == "General":
            m_st = re.match(r'^Class\s+(\d+)', class_folder)
            if m_st:
                c_n = int(m_st.group(1))
                if 1 <= c_n <= 5:
                    stage = "Primary"
                elif 6 <= c_n <= 10:
                    stage = "Secondary"
                elif c_n >= 11:
                    stage = "Higher Secondary"

        tables = re.findall(r'<table\b[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)
        if stage == "Ethnic Minority":
            default_level = "Pre-Primary" if "প্রাক" in raw_page_title else "Primary"
            lang_cols_map = {
                'চাকমা': 'Chakma',
                'মারমা': 'Marma',
                'গারো': 'Garo',
                'সাদরি': 'Sadri',
                'ত্রিপুরা': 'Tripura'
            }
            for tbl in tables:
                rows = re.findall(r'<tr\b[^>]*>(.*?)</tr>', tbl, re.DOTALL | re.IGNORECASE)
                if not rows:
                    continue
                header_cells = [re.sub(r'<[^>]+>', ' ', c).strip() for c in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', rows[0], re.DOTALL | re.IGNORECASE)]
                col_to_lang = {}
                for idx, col in enumerate(header_cells):
                    for bn_lang, en_lang in lang_cols_map.items():
                        if bn_lang in col:
                            col_to_lang[idx] = en_lang
                            break
                current_cls = default_level
                for r in rows[1:]:
                    tds = re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', r, re.DOTALL | re.IGNORECASE)
                    td_texts = [re.sub(r'<[^>]+>', ' ', c).strip() for c in tds]
                    for txt in td_texts:
                        if '১ম শ্রেণি' in txt or 'প্রথম শ্রেণি' in txt:
                            current_cls = 'Class 1'
                        elif '২য় শ্রেণি' in txt or 'দ্বিতীয় শ্রেণি' in txt:
                            current_cls = 'Class 2'
                        elif '৩য় শ্রেণি' in txt or 'তৃতীয় শ্রেণি' in txt:
                            current_cls = 'Class 3'
                    title = None
                    for txt in td_texts:
                        if any(t in txt for t in ['আমার বই', 'এসো লিখতে শিখি', 'আমার বাংলা বই', 'গণিত']):
                            title = txt
                            break
                    if not title:
                        continue
                    subj = classify_nctb_subject(title)
                    for c_idx, lang_name in col_to_lang.items():
                        if c_idx < len(tds):
                            links = re.findall(r'href=[\"\']([^\"\']+)[\"\']', tds[c_idx])
                            if links:
                                all_books.append({
                                    'source': 'NCTB',
                                    'stage': 'Ethnic Minority',
                                    'academic_year': req_year,
                                    'class_folder': current_cls,
                                    'subject': subj,
                                    'title': title,
                                    'lang': lang_name,
                                    'links': links
                                })
            continue

        for tbl in tables:
            rows = re.findall(r'<tr\b[^>]*>(.*?)</tr>', tbl, re.DOTALL | re.IGNORECASE)
            for r in rows[1:]:
                tds = re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', r, re.DOTALL | re.IGNORECASE)
                if len(tds) >= 5:
                    b_title = sanitize_filename(tds[1])
                    b_links = re.findall(r'href=[\"\']([^\"\']+)[\"\']', tds[2])
                    e_title = sanitize_filename(tds[3])
                    e_links = re.findall(r'href=[\"\']([^\"\']+)[\"\']', tds[4])

                    if b_title and b_links and 'ডাউনলোড' not in b_title:
                        subj_b = classify_nctb_subject(b_title)
                        all_books.append({
                            'source': 'NCTB',
                            'stage': stage,
                            'academic_year': book_ay,
                            'root_academic_year': req_year,
                            'class_folder': class_folder,
                            'subject': subj_b,
                            'title': b_title,
                            'lang': 'Bangla Version',
                            'links': b_links
                        })

                    if e_title and e_links and 'ডাউনলোড' not in e_title and (e_links != b_links or re.search(r'[A-Za-z]', e_title)):
                        subj_e = classify_nctb_subject(e_title)
                        all_books.append({
                            'source': 'NCTB',
                            'stage': stage,
                            'academic_year': book_ay,
                            'root_academic_year': req_year,
                            'class_folder': class_folder,
                            'subject': subj_e,
                            'title': e_title,
                            'lang': 'English Version',
                            'links': e_links
                        })

                elif len(tds) >= 2:
                    if len(tds) >= 3:
                        book_title = sanitize_filename(tds[1])
                        links = re.findall(r'href=[\"\']([^\"\']+)[\"\']', tds[2])
                    else:
                        book_title = sanitize_filename(tds[0])
                        links = re.findall(r'href=[\"\']([^\"\']+)[\"\']', tds[1])
                    if book_title and links and 'ডাউনলোড' not in book_title:
                        lang = "Bangla Version"
                        if "ইংলিশ ভার্সন" in book_title or "ইংরেজি ভার্সন" in book_title or "english version" in book_title.lower() or "ইংরেজি ভার্সন" in raw_page_title or "english version" in raw_page_title.lower():
                            lang = "English Version"
                            book_title = re.sub(r'\s*\((?:ইংলিশ ভার্সন|ইংরেজি ভার্সন|English Version)\)', '', book_title, flags=re.IGNORECASE).strip()
                        subj = classify_nctb_subject(book_title)

                        current_class_folder = class_folder
                        if stage == 'Pre-Primary':
                            if any(k in book_title for k in ['গল্পের বই', 'এসো আঁকিবুঁকি']):
                                current_class_folder = 'Age 4'
                            elif any(k in book_title for k in ['আমার বই', 'এসো লিখতে শিখি']):
                                current_class_folder = 'Age 5'

                        all_books.append({
                            'source': 'NCTB',
                            'stage': stage,
                            'academic_year': book_ay,
                            'root_academic_year': req_year,
                            'class_folder': current_class_folder,
                            'subject': subj,
                            'title': book_title,
                            'lang': lang,
                            'links': links
                        })

    print(f"[✓] NCTB books discovered for AY{req_year}: {len(all_books)}")
    return all_books


def get_standard_nctb_dest(book: dict, base_dir: str = '.') -> tuple:
    """Compute standardized (target_dir, pdf_filename) for an NCTB book."""
    root_ay = str(book.get('root_academic_year') or book.get('academic_year') or DEFAULT_ACADEMIC_YEAR)
    if root_ay.startswith('Academic Year '):
        ay_num = root_ay.replace('Academic Year ', '').strip()
    elif root_ay.startswith('AY'):
        ay_num = root_ay[2:].strip()
    else:
        ay_num = root_ay.strip()
    ay_root_folder = f"Academic Year {ay_num}"
    ay_pdf_tag = f"AY{ay_num}"
    stage_folder = STAGE_FOLDER_MAP.get(book['stage'], book['stage'])

    file_title = book['title']
    if book['lang'] == 'English Version':
        ev_map = {
            'প্রাথমিক গণিত': 'Elementary Mathematics',
            'গণিত': 'Mathematics',
            'উচ্চতর গণিত': 'Higher Mathematics',
            'প্রাথমিক বিজ্ঞান': 'Elementary Science',
            'বিজ্ঞান': 'Science',
            'বাংলাদেশ ও বিশ্বপরিচয়': 'Bangladesh and Global Studies',
            'বাংলাদেশ ও বিশ্ব পরিচয়': 'Bangladesh and Global Studies',
            'ইসলাম শিক্ষা': 'Islamic Studies',
            'ইসলাম ও নৈতিক শিক্ষা': 'Islam and Moral Education',
            'হিন্দুধর্ম শিক্ষা': 'Hindu Religion Studies',
            'হিন্দুধর্ম ও নৈতিক শিক্ষা': 'Hindu Religion and Moral Education',
            'বৌদ্ধধর্ম শিক্ষা': 'Buddhist Religion Studies',
            'বৌদ্ধধর্ম ও নৈতিক শিক্ষা': 'Buddhist Religion and Moral Education',
            'খ্রিষ্টধর্ম শিক্ষা': 'Christian Religion Studies',
            'খ্রীষ্টধর্ম শিক্ষা': 'Christian Religion Studies',
            'খ্রিষ্টধর্ম ও নৈতিক শিক্ষা': 'Christian Religion and Moral Education',
            'খ্রীষ্টধর্ম ও নৈতিক শিক্ষা': 'Christian Religion and Moral Education',
            'তথ্য ও যোগাযোগ প্রযুক্তি': 'Information and Communication Technology',
            'শারীরিক শিক্ষা ও স্বাস্থ্য': 'Physical Education and Health',
            'কর্ম ও জীবনমুখী শিক্ষা': 'Work and Life Oriented Education',
            'কৃষিশিক্ষা': 'Agriculture Studies',
            'গার্হস্থ্যবিজ্ঞান': 'Home Science',
            'চারু ও কারুকলা': 'Arts and Crafts',
            'সংগীত': 'Music',
            'পৌরনীতি ও নাগরিকতা': 'Civics and Citizenship',
            'ভূগোল ও পরিবেশ': 'Geography and Environment',
            'অর্থনীতি': 'Economics',
            'হিসাববিজ্ঞান': 'Accounting',
            'ব্যবসায় উদ্যোগ': 'Business Entrepreneurship',
            'ফিন্যান্স ও ব্যাংকিং': 'Finance and Banking',
            'পদার্থবিজ্ঞান': 'Physics',
            'রসায়ন': 'Chemistry',
            'জীববিজ্ঞান': 'Biology',
            'আনন্দপাঠ': 'Anandapath',
            'চারুপাঠ': 'Charupath',
            'সাহিত্য কণিকা': 'Sahitya Konika',
            'বাংলা সাহিত্য': 'Bangla Sahitya',
            'বাংলা সহপাঠ': 'Bangla Sahapath',
            'English For Today': 'English for Today',
        }
        file_title = ev_map.get(file_title, file_title)

    stage = book['stage']

    if stage == 'Ethnic Minority':
        ep = ETHNIC_PREFIX_MAP.get(book['lang'], book['lang'][:2].upper())
        if book['class_folder'] == 'Pre-Primary':
            tag = f"{ep}0"
            target_dir = os.path.join(base_dir, 'NCTB', ay_root_folder, stage_folder, 'Pre-Primary', f"{book['lang']}-{tag}")
        else:
            m_cls = re.search(r'(\d+)', book['class_folder'])
            cnum = m_cls.group(1) if m_cls else '1'
            tag = f"{ep}{cnum}"
            target_dir = os.path.join(base_dir, 'NCTB', ay_root_folder, stage_folder, 'Primary', f"General Class {cnum}", f"{book['lang']}-{tag}")
        pdf_name = f"{file_title}-{tag}-{ay_pdf_tag}.pdf"
        return target_dir, pdf_name

    if stage == 'Pre-Primary':
        age_folder = f"General Class-{book['class_folder']}"
        target_dir = os.path.join(base_dir, 'NCTB', ay_root_folder, stage_folder, age_folder)
        pdf_name = f"{file_title}-{book['class_folder']}-GC0-{ay_pdf_tag}.pdf"
        return target_dir, pdf_name

    prefix = STAGE_CLASS_PREFIX.get(stage, 'GC')
    full_cls_name = STAGE_FULL_CLASS_NAME.get(stage, 'General Class')
    m_cls = re.search(r'Class\s*([0-9-]+)', book['class_folder'])
    cls_num_str = m_cls.group(1) if m_cls else book['class_folder']
    tag = f"{prefix}{cls_num_str}"
    cls_folder_name = f"{full_cls_name} {cls_num_str}"
    ver_folder = f"{book['lang']}-{tag}"
    subj_folder = f"{book['subject']}-{tag}"

    if stage == 'Higher Secondary':
        hs_ay = book.get('academic_year') or '2025-2026'
        hs_ay_folder = f"Academic Year {hs_ay}" if not str(hs_ay).startswith('Academic Year') else str(hs_ay)
        hs_ay_tag = _format_hs_ay_tag(hs_ay)
        target_dir = os.path.join(base_dir, 'NCTB', ay_root_folder, stage_folder, hs_ay_folder, cls_folder_name, ver_folder, subj_folder)
        pdf_name = f"{file_title}-{tag}-{hs_ay_tag}.pdf"
        return target_dir, pdf_name

    target_dir = os.path.join(base_dir, 'NCTB', ay_root_folder, stage_folder, cls_folder_name, ver_folder, subj_folder)
    pdf_name = f"{file_title}-{tag}-{ay_pdf_tag}.pdf"
    return target_dir, pdf_name


def download_nctb_book(book: dict, base_dir: str, web_search_fallback: bool = True) -> bool:
    """Download an NCTB book PDF into the standardized folder & filename."""
    target_dir, pdf_name = get_standard_nctb_dest(book, base_dir)
    os.makedirs(target_dir, exist_ok=True)
    dest_path = os.path.join(target_dir, pdf_name)

    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 10000:
        print(f"[SKIP] NCTB [{book['stage']} > {book['class_folder']} > {book['lang']} > {book['subject']}] {pdf_name} - Already exists.")
        return True

    links = book['links']
    print(f"[NCTB] Downloading [{book['class_folder']} | {book['lang']} | {book['subject']}] {pdf_name} ...")

    egov_link = next((l for l in links if 'egovcloud' in l.lower()), None)
    if egov_link:
        direct_egov = egov_link if egov_link.rstrip('/').endswith('/download') else egov_link.rstrip('/') + '/download'
        if download_stream(direct_egov, dest_path, timeout=60):
            print(f"[✓] NCTB [{book['class_folder']} > {book['subject']}] {pdf_name} -> Downloaded ({os.path.getsize(dest_path)/(1024*1024):.2f} MB).")
            return True

    gdrive_link = next((l for l in links if 'drive.google.com' in l.lower()), None)
    if gdrive_link:
        id_m = re.search(r'file/d/([a-zA-Z0-9_-]+)', gdrive_link) or re.search(r'id=([a-zA-Z0-9_-]+)', gdrive_link)
        if id_m:
            file_id = id_m.group(1)
            if download_gdrive(file_id, dest_path, timeout=90):
                print(f"[✓] NCTB [{book['class_folder']} > {book['subject']}] {pdf_name} -> Downloaded via Google Drive ({os.path.getsize(dest_path)/(1024*1024):.2f} MB).")
                return True

    for l in links:
        if l != egov_link and l != gdrive_link:
            if download_stream(l, dest_path, timeout=60):
                print(f"[✓] NCTB [{book['class_folder']} > {book['subject']}] {pdf_name} -> Downloaded ({os.path.getsize(dest_path)/(1024*1024):.2f} MB).")
                return True

    if web_search_fallback:
        ay_str = book.get('root_academic_year') or book.get('academic_year') or ''
        query = f'"{book["title"]}" {book["class_folder"]} {ay_str} NCTB pdf'
        print(f"[*] Official links failed for {pdf_name}; searching web fallback...")
        for cand_url in search_web_for_book_links(query):
            if 'drive.google.com' in cand_url.lower():
                id_m = re.search(r'file/d/([a-zA-Z0-9_-]+)', cand_url) or re.search(r'id=([a-zA-Z0-9_-]+)', cand_url)
                if id_m and download_gdrive(id_m.group(1), dest_path, timeout=90):
                    print(f"[✓] NCTB [{book['class_folder']} > {book['subject']}] {pdf_name} -> Downloaded via Web Search Drive ({os.path.getsize(dest_path)/(1024*1024):.2f} MB).")
                    return True
            elif cand_url.lower().endswith('.pdf') and download_stream(cand_url, dest_path, timeout=60):
                print(f"[✓] NCTB [{book['class_folder']} > {book['subject']}] {pdf_name} -> Downloaded via Web Search ({os.path.getsize(dest_path)/(1024*1024):.2f} MB).")
                return True

    print(f"[✗] NCTB [{book['class_folder']} > {book['subject']}] Failed: {pdf_name}")
    return False


# ==============================================================================
# INTERACTIVE SELECTION HELPERS
# ==============================================================================

def _parse_index_selection(raw: str, max_idx: int) -> list:
    """Parse comma-separated indices and ranges like '1,3,5-8' into 0-based indices."""
    selected = set()
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            bounds = part.split('-', 1)
            if bounds[0].strip().isdigit() and bounds[1].strip().isdigit():
                start, end = int(bounds[0]), int(bounds[1])
                for i in range(min(start, end), max(start, end) + 1):
                    if 1 <= i <= max_idx:
                        selected.add(i - 1)
        elif part.isdigit():
            idx = int(part)
            if 1 <= idx <= max_idx:
                selected.add(idx - 1)
    return sorted(selected)


def interactive_filter_books(books: list, label: str) -> list:
    """Ask user whether to download all books for the filtered classes or pick specific books."""
    if not books:
        return books

    print(f"\n[{label}] {len(books)} book(s) matched your filter.")
    choice = input(f"Download ALL {len(books)} {label} books or select SPECIFIC books? [all / select] (default: all): ").strip().lower()
    if choice in ('', 'a', 'all', 'y', 'yes'):
        return books

    print(f"\n--- {label} Available Books ---")
    for idx, b in enumerate(books, 1):
        if b['source'] == 'NCERT':
            print(f"  {idx:3d}. [Class {b['class_num']} | {b['subject']} | {b['lang']}] {b['title']}")
        else:
            print(f"  {idx:3d}. [{b['stage']} | {b['class_folder']} | {b['lang']} | {b['subject']}] {b['title']}")

    sel_raw = input("\nEnter book numbers to download (e.g. 1,3,5-8 or 'all'): ").strip()
    if sel_raw.lower() in ('', 'all'):
        return books
    indices = _parse_index_selection(sel_raw, len(books))
    chosen = [books[i] for i in indices]
    print(f"[✓] Selected {len(chosen)} {label} book(s).")
    return chosen


def filter_books_by_classes(ncert_books: list, nctb_books: list, classes: list) -> tuple:
    """Filter NCERT and NCTB book lists by integer class numbers."""
    if not classes:
        return ncert_books, nctb_books
    filtered_ncert = [b for b in ncert_books if b['class_num'] in classes]
    class_str_set = {f"Class {c}" for c in classes} | {f"Class {c:02d}" for c in classes}
    filtered_nctb = [
        b for b in nctb_books
        if (0 in classes and b['stage'] == 'Pre-Primary')
        or any(cs in b['class_folder'] for cs in class_str_set)
    ]
    return filtered_ncert, filtered_nctb


# ==============================================================================
# MAIN COORDINATOR
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="NCERT and NCTB Full Textbook Downloader")
    parser.add_argument(
        '--source',
        choices=['all', 'ncert', 'nctb'],
        default='all',
        help="Choose source to download: 'all' (default), 'ncert', or 'nctb'"
    )
    parser.add_argument(
        '--academic-year',
        default=None,
        help=f"NCTB Academic Year to download (default: {DEFAULT_ACADEMIC_YEAR}, e.g. 2026, 2025, 2025-2026)"
    )
    parser.add_argument(
        '--output',
        default='.',
        help="Base directory to save downloaded books (default: current directory)"
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=6,
        help="Number of concurrent download threads (default: 6)"
    )
    parser.add_argument(
        '--classes',
        nargs='*',
        type=int,
        help="Specific class numbers to download (e.g. --classes 1 2 3; use 0 for Pre-Primary)"
    )
    parser.add_argument(
        '--stages',
        nargs='*',
        help="Specific stages to download for NCTB (e.g. --stages pre-primary primary ibtedayi)"
    )
    parser.add_argument(
        '--exclude-stages',
        nargs='*',
        help="Specific stages to exclude from download for NCTB"
    )
    parser.add_argument(
        '--include-vocational',
        action='store_true',
        help="Also crawl NCERT Vocational Education portal (https://ncert.nic.in/vocational.php)"
    )
    parser.add_argument(
        '--no-web-search',
        action='store_true',
        help="Disable internet search fallback when saved links fail or year is missing"
    )
    parser.add_argument(
        '--non-interactive',
        action='store_true',
        help="Skip interactive prompts and use CLI flags directly"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="List all books discovered without downloading them"
    )

    args = parser.parse_args()
    base_dir = os.path.abspath(args.output)
    os.makedirs(base_dir, exist_ok=True)

    academic_year = args.academic_year
    if not academic_year and args.source in ['all', 'nctb']:
        if args.non_interactive or args.dry_run:
            academic_year = DEFAULT_ACADEMIC_YEAR
        else:
            inp_ay = input(f"Enter NCTB Academic Year (default: {DEFAULT_ACADEMIC_YEAR}): ").strip()
            academic_year = inp_ay if inp_ay else DEFAULT_ACADEMIC_YEAR

    classes = args.classes
    if not classes and not args.non_interactive and not args.dry_run:
        inp_cls = input("Enter class numbers (e.g. 1 2 9, 0 for Pre-Primary, or 'all'): ").strip()
        if inp_cls and inp_cls.lower() != 'all':
            classes = [int(x) for x in re.findall(r'\d+', inp_cls)]

    include_vocational = args.include_vocational
    if args.source in ['all', 'ncert'] and not include_vocational and not args.non_interactive and not args.dry_run:
        voc_ans = input("Include NCERT Vocational Education portal books? [y/N]: ").strip().lower()
        include_vocational = voc_ans in ('y', 'yes')

    print("=" * 75)
    print("NCERT & NCTB Automated Textbook Downloader")
    print(f"Target Directory   : {base_dir}")
    print(f"Source Selected    : {args.source.upper()}")
    if args.source in ['all', 'ncert']:
        print(f"Include Vocational : {'Yes' if include_vocational else 'No'}")
    if args.source in ['all', 'nctb']:
        print(f"NCTB Academic Year : AY{academic_year}")
    print(f"Concurrency        : {args.workers} worker threads")
    print("=" * 75)

    ncert_dir = os.path.join(base_dir, 'NCERT')
    existing_ncert_codes = scan_existing_ncert_codes(ncert_dir)
    if existing_ncert_codes:
        print(f"[*] Detected {len(existing_ncert_codes)} pre-existing books in NCERT folder. They will be skipped.")

    ncert_books = []
    if args.source in ['all', 'ncert']:
        ncert_books = get_ncert_books(include_vocational=include_vocational)

    nctb_books = []
    if args.source in ['all', 'nctb']:
        nctb_books = get_nctb_books(academic_year=academic_year or DEFAULT_ACADEMIC_YEAR, allow_web_search=not args.no_web_search)
        if args.stages:
            stage_targets = {s.lower().replace('-', '').replace(' ', '') for s in args.stages}
            nctb_books = [
                b for b in nctb_books
                if b['stage'].lower().replace('-', '').replace(' ', '') in stage_targets
            ]
        if args.exclude_stages:
            exclude_targets = {s.lower().replace('-', '').replace(' ', '') for s in args.exclude_stages}
            nctb_books = [
                b for b in nctb_books
                if b['stage'].lower().replace('-', '').replace(' ', '') not in exclude_targets
            ]

    ncert_books, nctb_books = filter_books_by_classes(ncert_books, nctb_books, classes)

    if not args.non_interactive and not args.dry_run:
        if ncert_books:
            ncert_books = interactive_filter_books(ncert_books, "NCERT")
        if nctb_books:
            nctb_books = interactive_filter_books(nctb_books, "NCTB")

    total_tasks = len(ncert_books) + len(nctb_books)
    print(f"\n[+] Total books queued: {total_tasks} (NCERT: {len(ncert_books)}, NCTB: {len(nctb_books)})")

    if args.dry_run:
        print("\n--- Dry Run: Books List with Output Folders ---")
        for b in ncert_books:
            print(f"  [NCERT] {b['title']} -> {get_standard_ncert_dir(b, base_dir)}")
        for b in nctb_books:
            t_dir, pdf_name = get_standard_nctb_dest(b, base_dir)
            print(f"  [NCTB] {b['title']} -> {os.path.join(t_dir, pdf_name)}")
        print("\nDry run completed.")
        return

    interleaved = []
    i, j = 0, 0
    while i < len(nctb_books) or j < len(ncert_books):
        if i < len(nctb_books):
            interleaved.append(('NCTB', nctb_books[i]))
            i += 1
        if j < len(ncert_books):
            interleaved.append(('NCERT', ncert_books[j]))
            j += 1

    start_time = time.time()
    successful = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for source_type, book in interleaved:
            if source_type == 'NCERT':
                f = executor.submit(download_ncert_book, book, base_dir, existing_ncert_codes)
                futures[f] = f"NCERT: {book['title']}"
            else:
                f = executor.submit(download_nctb_book, book, base_dir, not args.no_web_search)
                futures[f] = f"NCTB: {book['title']}"

        for future in as_completed(futures):
            label = futures[future]
            try:
                res = future.result()
                if res:
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"[!] Error processing {label}: {e}")
                failed += 1

    elapsed = time.time() - start_time
    print("\n" + "=" * 75)
    print("Download Summary:")
    print(f"  Total Processed : {total_tasks}")
    print(f"  Successful      : {successful}")
    print(f"  Failed / Skipped: {failed}")
    print(f"  Total Time Taken: {elapsed / 60:.2f} minutes")
    print(f"  Files saved in  : {base_dir}")
    print("=" * 75)


if __name__ == '__main__':
    main()
