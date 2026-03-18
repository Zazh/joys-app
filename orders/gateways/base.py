from dataclasses import dataclass, field


@dataclass
class PaymentResult:
    """Результат создания платежа в шлюзе."""
    success: bool
    payment_id: str = ''
    payment_url: str = ''
    error_message: str = ''
    _payment_object: dict = field(default_factory=dict, repr=False)


@dataclass
class PaymentStatus:
    """Результат проверки статуса платежа."""
    paid: bool
    raw_status: str = ''


class BaseGateway:
    """Абстрактный интерфейс платёжного шлюза.

    Каждый шлюз (VTB, Halyk, Stripe, ...) наследует этот класс
    и реализует все методы. Views работают только через этот интерфейс.
    """

    code: str = ''  # 'vtb', 'halyk' — уникальный код шлюза

    def create_payment(self, order, return_url, callback_url):
        """
        Создать платёж в шлюзе.

        Args:
            order: Order instance (number, total_amount, customer_email, region)
            return_url: URL для редиректа клиента после оплаты
            callback_url: URL для серверного callback от шлюза

        Returns:
            PaymentResult
        """
        raise NotImplementedError

    def check_status(self, payment_id):
        """
        Проверить статус платежа.

        Args:
            payment_id: ID платежа в шлюзе (Order.payment_id)

        Returns:
            PaymentStatus
        """
        raise NotImplementedError

    def process_callback(self, request):
        """
        Обработать callback от шлюза.

        Args:
            request: Django HttpRequest

        Returns:
            tuple(Order | None, bool) — (заказ, оплачен ли)
        """
        raise NotImplementedError

    def refund(self, payment_id, amount=None):
        """
        Возврат средств.

        Args:
            payment_id: ID платежа в шлюзе
            amount: Decimal сумма (None = полный возврат)

        Returns:
            dict с результатом
        """
        raise NotImplementedError
