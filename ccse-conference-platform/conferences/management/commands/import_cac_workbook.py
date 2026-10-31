"""Repeatable, provenance-preserving import of the sponsor's CAC listing."""
import json
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from conferences.cac_import import import_workbook

class Command(BaseCommand):
    help='Import the CAC workbook, preserving row sources and existing catalog values.'
    def add_arguments(self,parser):
        parser.add_argument('path')
        parser.add_argument('--dry-run',action='store_true')
        parser.add_argument('--report',help='Write the import reconciliation as JSON.')
    def handle(self,*args,**opts):
        try:
            report=import_workbook(opts['path'],dry_run=opts['dry_run'])
        except (OSError,ValueError,KeyError) as exc:
            raise CommandError(str(exc)) from exc
        if opts['report']:
            Path(opts['report']).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        label='DRY RUN: no database changes' if report['dry_run'] else 'Import complete'
        self.stdout.write(f"{label}. {report['rows']} source rows; {report['conferences_created']} new conferences; "
            f"{report['editions_created']} new editions; {report['existing_editions_preserved']} existing editions retained; "
            f"{report['already_imported']} rows already imported. No registration prices invented.")
