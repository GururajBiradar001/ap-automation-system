from django.core.management.base import BaseCommand
from workflow.engine import run_escalations


class Command(BaseCommand):
    help = "Send approval reminders and escalate overdue approvals (run every ~15 min via cron)"

    def handle(self, *a, **kw):
        self.stdout.write(str(run_escalations()))
