#!/usr/bin/env python3
"""
NCERT-Only Automated Textbook Downloader
========================================
Downloads Indian NCERT textbooks (Classes 1–12 + optional Vocational Education portal)
with interactive class and specific-book selection.
"""

import os
import re
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from download_books import (
    get_ncert_books,
    get_standard_ncert_dir,
    scan_existing_ncert_codes,
    download_ncert_book,
    interactive_filter_books,
    filter_books_by_classes,
)


def main():
    parser = argparse.ArgumentParser(description="NCERT-Only Textbook Downloader")
    parser.add_argument('--output', default='.', help="Base directory to save books (default: current directory)")
    parser.add_argument('--workers', type=int, default=6, help="Concurrent download threads (default: 6)")
    parser.add_argument('--classes', nargs='*', type=int, help="Specific class numbers (e.g. --classes 1 2 9)")
    parser.add_argument('--include-vocational', action='store_true', help="Include NCERT Vocational Education portal books")
    parser.add_argument('--non-interactive', action='store_true', help="Skip interactive prompts")
    parser.add_argument('--dry-run', action='store_true', help="List books without downloading")
    args = parser.parse_args()

    base_dir = os.path.abspath(args.output)
    os.makedirs(base_dir, exist_ok=True)

    classes = args.classes
    include_vocational = args.include_vocational
    if not args.non_interactive and not args.dry_run:
        if not classes:
            inp_cls = input("Enter NCERT class numbers (e.g. 1 2 9, or 'all'): ").strip()
            if inp_cls and inp_cls.lower() != 'all':
                classes = [int(x) for x in re.findall(r'\d+', inp_cls)]
        if not include_vocational:
            voc_ans = input("Include NCERT Vocational Education portal books? [y/N]: ").strip().lower()
            include_vocational = voc_ans in ('y', 'yes')

    print("=" * 75)
    print("NCERT Automated Textbook Downloader")
    print(f"Target Directory   : {base_dir}")
    print(f"Include Vocational : {'Yes' if include_vocational else 'No'}")
    print(f"Concurrency        : {args.workers} worker threads")
    print("=" * 75)

    existing_codes = scan_existing_ncert_codes(os.path.join(base_dir, 'NCERT'))
    if existing_codes:
        print(f"[*] Detected {len(existing_codes)} pre-existing NCERT book codes (will skip).")

    books = get_ncert_books(include_vocational=include_vocational)
    books, _ = filter_books_by_classes(books, [], classes)

    if not args.non_interactive and not args.dry_run and books:
        books = interactive_filter_books(books, "NCERT")

    print(f"\n[+] Total NCERT books queued: {len(books)}")

    if args.dry_run:
        for b in books:
            print(f"  [NCERT] {b['title']} -> {get_standard_ncert_dir(b, base_dir)}")
        return

    start_time = time.time()
    successful, failed = 0, 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download_ncert_book, b, base_dir, existing_codes): b['title'] for b in books}
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
