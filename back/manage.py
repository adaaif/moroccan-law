#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

# Commands that never write what a public answer is made of; after any other, the answers kept in Redis are not
# served again (S14 of the performance audit: apps/corpus/services/generation.py).
READ_ONLY = {'runserver', 'check', 'help', 'version', 'showmigrations', 'sqlmigrate', 'makemigrations', 'diffsettings',
             'test', 'collectstatic', 'dumpdata', 'search_eval', 'check_topic', 'reader_report', 'link_eval',
             'perf_report', 'draft_test_questions', 'grade_answers', 'budget', 'draft_lemmas',
             # Page images only, files the answers never hold: after a deploy's run every worker read its titles again.
             'draw_pages',
             # The same entries in a fresh index: run each night, it had emptied every kept answer at 03:30.
             'merge_search_index',
             # The assistants' sign-in rows and platform ranges: neither is read by an answer.
             'prune_oauth', 'refresh_platforms',
             # Two readings set side by side: nothing is written.
             'witness_pages',
             # A data file to commit and reports: no row an answer reads is changed.
             'hijri_months',
             # Letters sent, and when: run every five minutes and every hour by their timers, they emptied every kept
             # answer each time. They write the notices' and the digest's own marks, which no kept answer holds.
             'send_notice_letters', 'review_digest',
             # The measures' day counts and the web's file of their names: no answer reads either.
             'fold_events', 'write_measure_types',
             # The machines' day counts, read from nginx's log each night: no answer reads them.
             'count_machines',
             # The week's counts read and mailed, and the counts from before 16 Nov 2026 written as day counts: no
             # answer reads them.
             'analytics_letter', 'import_past_counts',
             # Access on request's night: accesses past their date ended, the letters 30 days before, old requests'
             # typed answers emptied. No answer reads an access or a request.
             'end_accesses',
             # It asks the week's most shown pages of the site after a deploy, to build their answers: outside this
             # set it emptied, as it ended, every answer it had just built.
             'warm_answers',
             # The database's edition, written as files under OPEN_DATA_DIR once a month: no kept answer holds them
             # (/api/open/ reads them from the disk each time).
             'export_open_data',
             # Where the doubtful words stand on their pages (Suspect.place) and the word boxes beside the renders: the
             # words' answers are never kept (/api/quality/words/ is counted at each request), nor is the law made of them.
             'place_words'}


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
    from django.core.management import execute_from_command_line

    command = sys.argv[1] if len(sys.argv) > 1 else 'help'
    try:
        execute_from_command_line(sys.argv)
    finally:
        # Even when it failed half way: what it wrote is in the database.
        if command not in READ_ONLY and not command.startswith('-'):
            try:
                from apps.corpus.services import generation
                generation.bump()
            except Exception:  # noqa: BLE001 — Django never started: nothing was written either
                pass


if __name__ == '__main__':
    main()
