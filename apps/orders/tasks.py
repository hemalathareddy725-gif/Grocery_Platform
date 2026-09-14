import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def send_order_confirmation(order_id):
    """
    Simulates sending an order confirmation (email/SMS/notification).
    Kept side-effect-light so it runs cleanly without external mail config.
    """
    from .models import Order

    try:
        order = Order.objects.select_related("store").get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning("Order %s not found for confirmation task", order_id)
        return

    logger.info(
        "Order confirmation sent for order #%s (store=%s, status=%s)",
        order.id, order.store.name, order.status,
    )
    return f"confirmation-sent:{order_id}"
