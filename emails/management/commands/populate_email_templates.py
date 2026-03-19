from django.core.management.base import BaseCommand

from emails.models import EmailTemplate

TEMPLATES = [
    {
        'slug': 'email_verify',
        'subject_ru': 'Подтвердите email — DR.JOYS',
        'subject_kk': 'Email-ді растаңыз — DR.JOYS',
        'subject_en': 'Verify your email — DR.JOYS',
        'body_ru': (
            'Здравствуйте, {user_name}!\n\n'
            'Для завершения регистрации подтвердите ваш email-адрес, перейдя по ссылке:\n\n'
            '{verify_url}\n\n'
            'Ссылка действительна 24 часа.\n\n'
            'Если вы не регистрировались на DR.JOYS — просто проигнорируйте это письмо.\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'body_kk': (
            'Сәлеметсіз бе, {user_name}!\n\n'
            'Тіркелуді аяқтау үшін email мекенжайыңызды растаңыз:\n\n'
            '{verify_url}\n\n'
            'Сілтеме 24 сағат жарамды.\n\n'
            'Егер DR.JOYS-та тіркелмесеңіз — бұл хатты елемеңіз.\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'body_en': (
            'Hello, {user_name}!\n\n'
            'Please verify your email address by following this link:\n\n'
            '{verify_url}\n\n'
            'This link is valid for 24 hours.\n\n'
            'If you did not sign up for DR.JOYS, please ignore this email.\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'description': 'Плейсхолдеры: {user_name}, {user_email}, {verify_url}, {site_url}',
    },
    {
        'slug': 'password_reset',
        'subject_ru': 'Сброс пароля — DR.JOYS',
        'subject_kk': 'Құпия сөзді қалпына келтіру — DR.JOYS',
        'subject_en': 'Password reset — DR.JOYS',
        'body_ru': (
            'Здравствуйте, {user_name}!\n\n'
            'Вы запросили сброс пароля для аккаунта {user_email}.\n'
            'Для создания нового пароля перейдите по ссылке:\n\n'
            '{reset_url}\n\n'
            'Ссылка действительна 1 час.\n\n'
            'Если вы не запрашивали сброс пароля — просто проигнорируйте это письмо.\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'body_kk': (
            'Сәлеметсіз бе, {user_name}!\n\n'
            '{user_email} аккаунтының құпия сөзін қалпына келтіру сұралды.\n'
            'Жаңа құпия сөз жасау үшін сілтемеге өтіңіз:\n\n'
            '{reset_url}\n\n'
            'Сілтеме 1 сағат жарамды.\n\n'
            'Егер сіз сұрамаған болсаңыз — бұл хатты елемеңіз.\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'body_en': (
            'Hello, {user_name}!\n\n'
            'You requested a password reset for {user_email}.\n'
            'To create a new password, follow this link:\n\n'
            '{reset_url}\n\n'
            'This link is valid for 1 hour.\n\n'
            'If you did not request a password reset, please ignore this email.\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'description': 'Плейсхолдеры: {user_name}, {user_email}, {reset_url}, {site_url}',
    },
    {
        'slug': 'welcome',
        'subject_ru': 'Добро пожаловать в DR.JOYS!',
        'subject_kk': 'DR.JOYS-қа қош келдіңіз!',
        'subject_en': 'Welcome to DR.JOYS!',
        'body_ru': (
            'Здравствуйте, {user_name}!\n\n'
            'Добро пожаловать в DR.JOYS — ультратонкие презервативы нового поколения.\n\n'
            'Ваш аккаунт создан. Приятных покупок!\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'body_kk': (
            'Сәлеметсіз бе, {user_name}!\n\n'
            'DR.JOYS-қа қош келдіңіз — жаңа буынның ультра жұқа мүшеқаптары.\n\n'
            'Сіздің аккаунтыңыз жасалды. Жақсы сатып алу!\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'body_en': (
            'Hello, {user_name}!\n\n'
            'Welcome to DR.JOYS — ultra-thin condoms of the new generation.\n\n'
            'Your account has been created. Happy shopping!\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'description': 'Плейсхолдеры: {user_name}, {user_email}, {site_url}',
    },
    {
        'slug': 'order_created',
        'subject_ru': 'Заказ #{order_number} создан — DR.JOYS',
        'subject_kk': '#{order_number} тапсырыс жасалды — DR.JOYS',
        'subject_en': 'Order #{order_number} created — DR.JOYS',
        'body_ru': (
            'Здравствуйте, {customer_name}!\n\n'
            'Ваш заказ #{order_number} от {order_date} создан.\n\n'
            'Состав заказа:\n'
            '{items_text}\n\n'
            'Итого: {order_total} {currency}\n\n'
            'Доставка: {delivery_address}\n\n'
            '{payment_url}\n\n'
            'Заказ будет автоматически отменён через 30 минут, если не оплачен.\n\n'
            'Если у вас есть вопросы — напишите на info@dr-joys.com\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'body_kk': (
            'Сәлеметсіз бе, {customer_name}!\n\n'
            '#{order_number} тапсырыс {order_date} күні жасалды.\n\n'
            'Тапсырыс құрамы:\n'
            '{items_text}\n\n'
            'Барлығы: {order_total} {currency}\n\n'
            'Жеткізу: {delivery_address}\n\n'
            '{payment_url}\n\n'
            'Тапсырыс 30 минуттан кейін төленбесе автоматты түрде жойылады.\n\n'
            'Сұрақтарыңыз болса — info@dr-joys.com жазыңыз\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'body_en': (
            'Hello, {customer_name}!\n\n'
            'Your order #{order_number} from {order_date} has been created.\n\n'
            'Order details:\n'
            '{items_text}\n\n'
            'Total: {order_total} {currency}\n\n'
            'Delivery: {delivery_address}\n\n'
            '{payment_url}\n\n'
            'The order will be automatically cancelled in 30 minutes if not paid.\n\n'
            'Questions? Email us at info@dr-joys.com\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'description': (
            'Плейсхолдеры: {order_number}, {order_date}, {order_total}, {currency}, '
            '{customer_name}, {items_text}, {delivery_address}, {payment_url}, {site_url}'
        ),
    },
    {
        'slug': 'order_paid',
        'subject_ru': 'Заказ #{order_number} оплачен — DR.JOYS',
        'subject_kk': '#{order_number} тапсырыс төленді — DR.JOYS',
        'subject_en': 'Order #{order_number} paid — DR.JOYS',
        'body_ru': (
            'Здравствуйте, {customer_name}!\n\n'
            'Ваш заказ #{order_number} от {order_date} оплачен.\n\n'
            'Состав заказа:\n'
            '{items_text}\n\n'
            'Итого: {order_total} {currency}\n\n'
            'Доставка: {delivery_address}\n\n'
            'Мы свяжемся с вами для уточнения деталей доставки.\n'
            'Спасибо за покупку!\n\n'
            'Вопросы? Напишите на info@dr-joys.com\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'body_kk': (
            'Сәлеметсіз бе, {customer_name}!\n\n'
            '#{order_number} тапсырыс {order_date} күні төленді.\n\n'
            'Тапсырыс құрамы:\n'
            '{items_text}\n\n'
            'Барлығы: {order_total} {currency}\n\n'
            'Жеткізу: {delivery_address}\n\n'
            'Жеткізу бойынша сізбен хабарласамыз.\n'
            'Сатып алғаныңызға рахмет!\n\n'
            'Сұрақтар? info@dr-joys.com жазыңыз\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'body_en': (
            'Hello, {customer_name}!\n\n'
            'Your order #{order_number} from {order_date} has been paid.\n\n'
            'Order details:\n'
            '{items_text}\n\n'
            'Total: {order_total} {currency}\n\n'
            'Delivery: {delivery_address}\n\n'
            'We will contact you to arrange delivery.\n'
            'Thank you for your purchase!\n\n'
            'Questions? Email us at info@dr-joys.com\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'description': (
            'Плейсхолдеры: {order_number}, {order_date}, {order_total}, {currency}, '
            '{customer_name}, {items_text}, {delivery_address}, {site_url}'
        ),
    },
    {
        'slug': 'order_shipped',
        'subject_ru': 'Заказ #{order_number} отправлен — DR.JOYS',
        'subject_kk': '#{order_number} тапсырыс жіберілді — DR.JOYS',
        'subject_en': 'Order #{order_number} shipped — DR.JOYS',
        'body_ru': (
            'Здравствуйте, {customer_name}!\n\n'
            'Ваш заказ #{order_number} отправлен.\n'
            '{tracking_number}\n\n'
            'Мы свяжемся с вами для уточнения деталей доставки.\n\n'
            'Если у вас есть вопросы — напишите на info@dr-joys.com\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'body_kk': (
            'Сәлеметсіз бе, {customer_name}!\n\n'
            '#{order_number} тапсырыс жіберілді.\n'
            '{tracking_number}\n\n'
            'Жеткізу бойынша сізбен хабарласамыз.\n\n'
            'Сұрақтарыңыз болса — info@dr-joys.com жазыңыз\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'body_en': (
            'Hello, {customer_name}!\n\n'
            'Your order #{order_number} has been shipped.\n'
            '{tracking_number}\n\n'
            'We will contact you to arrange delivery.\n\n'
            'Questions? Email us at info@dr-joys.com\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'description': 'Плейсхолдеры: {order_number}, {tracking_number}, {customer_name}, {site_url}',
    },
    {
        'slug': 'staff_invite',
        'subject_ru': 'Доступ к панели управления — DR.JOYS',
        'subject_kk': 'Басқару панеліне кіру — DR.JOYS',
        'subject_en': 'Backoffice access — DR.JOYS',
        'body_ru': (
            'Здравствуйте, {user_name}!\n\n'
            'Вам предоставлен доступ к панели управления DR.JOYS.\n\n'
            'Данные для входа:\n'
            '  Ссылка: {login_url}\n'
            '  Email: {user_email}\n'
            '  Пароль: {password}\n'
            '  Роль: {role}\n\n'
            'Рекомендуем сменить пароль после первого входа.\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'body_kk': (
            'Сәлеметсіз бе, {user_name}!\n\n'
            'DR.JOYS басқару панеліне кіру мүмкіндігі берілді.\n\n'
            'Кіру деректері:\n'
            '  Сілтеме: {login_url}\n'
            '  Email: {user_email}\n'
            '  Құпия сөз: {password}\n'
            '  Рөл: {role}\n\n'
            'Бірінші кіргеннен кейін құпия сөзді ауыстыруды ұсынамыз.\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'body_en': (
            'Hello, {user_name}!\n\n'
            'You have been granted access to the DR.JOYS backoffice.\n\n'
            'Login credentials:\n'
            '  URL: {login_url}\n'
            '  Email: {user_email}\n'
            '  Password: {password}\n'
            '  Role: {role}\n\n'
            'We recommend changing your password after the first login.\n\n'
            '—\n'
            'DR.JOYS\n'
            '{site_url}'
        ),
        'description': 'Плейсхолдеры: {user_name}, {user_email}, {password}, {role}, {login_url}, {site_url}',
    },
]


class Command(BaseCommand):
    help = 'Создать начальные шаблоны email-писем'

    def handle(self, *args, **options):
        created = 0
        for tpl_data in TEMPLATES:
            slug = tpl_data['slug']
            obj, is_new = EmailTemplate.objects.get_or_create(
                slug=slug,
                defaults={
                    'subject': tpl_data['subject_ru'],
                    'subject_ru': tpl_data['subject_ru'],
                    'subject_kk': tpl_data['subject_kk'],
                    'subject_en': tpl_data['subject_en'],
                    'body': tpl_data['body_ru'],
                    'body_ru': tpl_data['body_ru'],
                    'body_kk': tpl_data['body_kk'],
                    'body_en': tpl_data['body_en'],
                    'description': tpl_data['description'],
                },
            )
            if is_new:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  + {slug}'))
            else:
                self.stdout.write(f'  = {slug} (already exists)')

        self.stdout.write(self.style.SUCCESS(f'\nDone: {created} created'))
