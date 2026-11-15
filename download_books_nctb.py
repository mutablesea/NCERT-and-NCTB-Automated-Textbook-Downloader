#!/usr/bin/env python3
"""
NCTB-Only Automated Textbook Downloader (Academic Year Strict)
==============================================================
Downloads Bangladeshi NCTB textbooks strictly for a specified Academic Year
(e.g. 2026, 2025, 2025-2026) with standardized C/IC/DC/VC/GC/EMC/CC/MC/SC/TC naming.
"""

import os
import re
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from download_books import (
    get_nctb_books,
    get_standard_nctb_dest,
    download_nctb_book,
    interactive_filter_books,
    filter_books_by_classes,
)

# Set your target Academic Year here (or pass --academic-year / enter at prompt)
ACADEMIC_YEAR = "2026"


def main():
    parser = argparse.ArgumentParser(description="NCTB-Only Textbook Downloader (Strict Academic Year)")
    parser.add_argument(
        '--academic-year',
        default=None,
        help=f"Target NCTB Academic Year (default: {ACADEMIC_YEAR}, e.g. 2026, 2025, 2025-2026)"
    )
    parser.add_argument('--output', default='.', help="Base directory to save books (default: current directory)")
    parser.add_argument('--workers', type=int, default=6, help="Concurrent download threads (default: 6)")
    parser.add_argument('--classes', nargs='*', type=int, help="Specific class numbers (0 for Pre-Primary)")
    parser.add_argument('--stages', nargs='*', help="Specific stages (e.g. pre-primary primary ibtedayi secondary dakhil vocational higher-secondary ethnic-minority)")
    parser.add_argument('--exclude-stages', nargs='*', help="Stages to exclude")
    parser.add_argument('--no-web-search', action='store_true', help="Disable web search fallback if saved links fail")
    parser.add_argument('--non-interactive', action='store_true', help="Skip interactive prompts")
    parser.add_argument('--dry-run', action='store_true', help="List books without downloading")
    args = parser.parse_args()

    base_dir = os.path.abspath(args.output)
    os.makedirs(base_dir, exist_ok=True)

    target_ay = args.academic_year
    if not target_ay:
        if args.non_interactive or args.dry_run:
            target_ay = ACADEMIC_YEAR
        else:
            inp_ay = input(f"Enter NCTB Academic Year to download (default: {ACADEMIC_YEAR}): ").strip()
            target_ay = inp_ay if inp_ay else ACADEMIC_YEAR

    classes = args.classes
    if not classes and not args.non_interactive and not args.dry_run:
        inp_cls = input("Enter class numbers (e.g. 1 2 9, 0 for Pre-Primary, or 'all'): ").strip()
        if inp_cls and inp_cls.lower() != 'all':
            classes = [int(x) for x in re.findall(r'\d+', inp_cls)]

    print("=" * 75)
    print("NCTB Automated Textbook Downloader (Strict Academic Year Mode)")
    print(f"Target Directory : {base_dir}")
    print(f"Academic Year    : AY{target_ay}")
    print(f"Concurrency      : {args.workers} worker threads")
    print("=" * 75)

    books = get_nctb_books(academic_year=target_ay, allow_web_search=not args.no_web_search)

    if args.stages:
        stage_targets = {s.lower().replace('-', '').replace(' ', '') for s in args.stages}
        books = [b for b in books if b['stage'].lower().replace('-', '').replace(' ', '') in stage_targets]
    if args.exclude_stages:
        exclude_targets = {s.lower().replace('-', '').replace(' ', '') for s in args.exclude_stages}
        books = [b for b in books if b['stage'].lower().replace('-', '').replace(' ', '') not in exclude_targets]

    _, books = filter_books_by_classes([], books, classes)

    if not args.non_interactive and not args.dry_run and books:
        books = interactive_filter_books(books, f"NCTB AY{target_ay}")

    print(f"\n[+] Total NCTB books queued for AY{target_ay}: {len(books)}")

    if args.dry_run:
        for b in books:
            t_dir, pdf_name = get_standard_nctb_dest(b, base_dir)
            print(f"  [NCTB] {b['title']} -> {os.path.join(t_dir, pdf_name)}")
        return

    start_time = time.time()
    successful, failed = 0, 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download_nctb_book, b, base_dir, not args.no_web_search): b['title'] for b in books}
        for future in as_completed(futures):
            try:
                if future.result():
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"[!] Error processing {futures[future]}: {e}")
                failed += 1

    elapsed = time.time() - start_time
    print(f"\n[✓] Done! Processed: {len(books)}, Successful: {successful}, Failed: {failed} ({elapsed/60:.2f} min)")


if __name__ == '__main__':
    main()
