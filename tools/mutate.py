"""Мутационное тестирование правил приложения (make mutation).

В код по очереди вносится одна намеренная ошибка (мутант): меняется условие, знак или
граница. После каждой мутации запускаются тесты. Если тесты упали, мутант «убит» —
тесты заметили ошибку. Если прошли, мутант «выжил» — значит, правило не проверяется
тестами и нужно дописать тест. После каждой мутации файл возвращается в исходный вид.
"""

import subprocess  # nosec B404 — запуск тестов этого же проекта
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

API = "tests/api"
UNIT = "tests/unit"

# файл, исходный фрагмент, мутация, что ломается, какие тесты запускать
MUTANTS = [
    (
        "app/services/receipts.py",
        "if not receipt.items:",
        "if False:",
        "можно провести поступление без строк",
        [f"{API}/test_receipts.py"],
    ),
    (
        "app/services/receipts.py",
        'if receipt.status != "draft":',
        'if receipt.status == "draft":',
        "проверка «только черновик» перевёрнута",
        [f"{API}/test_receipts.py"],
    ),
    (
        "app/services/receipts.py",
        "stock=Material.stock + item.quantity",
        "stock=Material.stock + item.quantity * 2",
        "остаток увеличивается неверно",
        [f"{API}/test_receipts.py"],
    ),
    (
        "app/services/receipts.py",
        'receipt.status = "posted"',
        'receipt.status = "draft"',
        "проведённое поступление остаётся черновиком",
        [f"{API}/test_receipts.py"],
    ),
    (
        "app/services/receipts.py",
        "if any(item.material_id == data.material_id for item in receipt.items):",
        "if False:",
        "один материал можно добавить в поступление дважды",
        [f"{API}/test_receipts.py"],
    ),
    (
        "app/schemas/receipt.py",
        "quantity: Decimal = Field(gt=0,",
        "quantity: Decimal = Field(ge=0,",
        "разрешено количество 0",
        [UNIT],
    ),
    (
        "app/schemas/receipt.py",
        "price: Decimal = Field(ge=0,",
        "price: Decimal = Field(gt=0,",
        "запрещена цена 0 (бесплатная поставка)",
        [UNIT],
    ),
    (
        "app/models/receipt.py",
        'quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)',
        'quantize(Decimal("0.01"))',
        "сумма округляется не по правилам для денег",
        [UNIT],
    ),
    (
        "app/schemas/supplier.py",
        "len(value) not in (10, 12)",
        "len(value) not in (10, 11, 12)",
        "принимается ИНН из 11 цифр",
        [UNIT],
    ),
    (
        "app/services/suppliers.py",
        "or_(Supplier.name == data.name, Supplier.inn == data.inn)",
        "Supplier.name == data.name",
        "можно завести двух поставщиков с одним ИНН",
        [f"{API}/test_suppliers.py"],
    ),
    (
        "app/services/materials.py",
        "if material.stock > 0:",
        "if material.stock > 1:",
        "можно удалить материал с остатком меньше 1",
        [f"{API}/test_materials.py"],
    ),
    (
        "app/services/units.py",
        "if used:",
        "if used > 1:",
        "можно удалить единицу, которая используется в одном материале",
        [f"{API}/test_units.py"],
    ),
    (
        "app/security.py",
        'if user.role != "admin":',
        'if user.role == "nobody":',
        "кладовщик может удалять записи",
        [API],
    ),
]


def run_tests(test_paths) -> int:
    command = [sys.executable, "-m", "pytest", "-x", "-q", "--no-cov", "-p", "no:cacheprovider"]
    result = subprocess.run(  # nosec B603 — фиксированная команда, без оболочки
        [*command, *test_paths], cwd=ROOT, capture_output=True, check=False
    )
    return result.returncode


def main():
    if run_tests([UNIT, API]) != 0:
        print("Тесты падают и без мутаций — сначала почините их (make test)")
        sys.exit(1)

    survived = []
    for number, (file, original, mutated, meaning, tests) in enumerate(MUTANTS, 1):
        path = ROOT / file
        # файл читается и восстанавливается побайтно: под Windows запись в текстовом
        # режиме заменила бы переводы строк на CRLF
        source = path.read_bytes()
        if source.count(original.encode()) != 1:
            print(f"{number:2}. ОШИБКА  {file}: фрагмент «{original}» не найден, обновите список")
            sys.exit(1)
        path.write_bytes(source.replace(original.encode(), mutated.encode()))
        try:
            code = run_tests(tests)
        finally:
            path.write_bytes(source)
        if code == 1:
            print(f"{number:2}. убит    {meaning}")
        else:
            print(f"{number:2}. ВЫЖИЛ   {meaning}  ({file})")
            survived.append(meaning)

    killed = len(MUTANTS) - len(survived)
    print(f"\nУбито мутантов: {killed} из {len(MUTANTS)} ({killed * 100 // len(MUTANTS)}%)")
    if survived:
        print("Выжившие мутанты означают, что правило не проверяется тестами")
        sys.exit(1)


if __name__ == "__main__":
    main()
