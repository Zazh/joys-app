r"""Текстовые хелперы без HTML-семантики.

Для мета-тегов есть `core/seo.py::plain_text` (strip_tags + unescape) — он
здесь сознательно не реюзается: значения покупателя надо печатать буквально,
а не как HTML.
"""

import re

_CONTROL_CHARS = re.compile(r'[\x00-\x1f]')
_SPACE_RUNS = re.compile(r' {2,}')


def one_line(value):
    r"""Свернуть значение, пришедшее от покупателя, в одну строку.

    Управляющие символы (\r, \n, \t и прочие C0) заменяются пробелом,
    последовательности пробелов схлопываются в один, края обрезаются;
    None → ''.

    Зачем: значения покупателя попадают в plain-text носители, где перевод
    строки — структура. `%0A` в query-параметре callback-а дописывал в лог
    поддельную запись (log-injection), а адрес с `\n\n` печатал в письме
    владельцу поддельные строки «Сумма:» выше настоящих.

    Кто пользуется (санитайзер в проекте один — Р-5 `payments-polish`):
    `orders/gateways/vtb.py::process_callback` (INFO-строка callback-а) и
    `emails/service.py` (оба письма владельцу).
    """
    if value is None:
        return ''
    text = _CONTROL_CHARS.sub(' ', str(value))
    return _SPACE_RUNS.sub(' ', text).strip()
