from django.db import transaction
from django.utils import timezone

from apps.core.models import DirectorPaymentAuditLog, FeePaymentLedgerEntry
from apps.core.services.audit_log_service import AuditLogService


def record_fee_payment(*, fee_record, amount, note, actor):
    old_value = {
        "fee_record_id": fee_record.id,
        "amount_due": fee_record.amount_due,
        "amount_paid": fee_record.amount_paid,
        "remaining": fee_record.remaining(),
        "paid_at": fee_record.paid_at,
    }
    with transaction.atomic():
        FeePaymentLedgerEntry.objects.create(fee_record=fee_record, amount=amount, note=note)
        fee_record.amount_paid = fee_record.amount_paid + amount
        if fee_record.remaining() <= 0:
            fee_record.paid_at = timezone.now()
        fee_record.save(update_fields=["amount_paid", "paid_at", "updated_at"])

    AuditLogService.log_action(
        user=actor,
        action_type="RECORD_PAYMENT",
        entity_type="payment",
        entity_id=fee_record.id,
        old_value=old_value,
        new_value={
            "fee_record_id": fee_record.id,
            "amount_due": fee_record.amount_due,
            "amount_paid": fee_record.amount_paid,
            "remaining": fee_record.remaining(),
            "paid_at": fee_record.paid_at,
            "ledger_note": note,
            "delta_amount": amount,
        },
    )
    DirectorPaymentAuditLog.objects.create(
        club=fee_record.club,
        actor=actor,
        action=DirectorPaymentAuditLog.Action.PAYMENT_RECORDED,
        detail=(
            f"Recorded {fee_record.currency} {amount} toward fee #{fee_record.id} "
            f"({fee_record.player.email}). {note}".strip()
        )[:4000],
        fee_record=fee_record,
    )
    return fee_record
