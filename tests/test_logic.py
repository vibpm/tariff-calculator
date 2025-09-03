# C:\excel-to-web\tests\test_logic.py

import pandas as pd
from decimal import Decimal
import pytest

# Импортируем функцию, которую хотим протестировать
from logic import run_calculation

# Используем pytest.approx для безопасного сравнения чисел с плавающей точкой
approx = pytest.approx

def test_vip_complex_with_fixation_and_combo_promotion():
    """
    Тестирует конкретный сценарий со скриншота:
    - ТП: Комплекс коммерческий VIP Предприятие
    - Уровни: Эксперт(2), Оптимальный(2), Минимальный(2)
    - Период: окт.25
    - Акция: Акция_Пр.166 (сентябрь25) на 12 мес. (10% скидка + спец.условие)
    - Фиксация: 5 мес. (коэффициент 1.06)
    """
    # ... (этот тест у тебя уже есть, оставляем его без изменений)
    
    # --- 1. Подготовка данных (Arrange) ---
    mock_prices_data = [
        {'Сервис': 'Комплекс коммерческий VIP Предприятие', 'Уровень': 'Эксперт', 'Аккаунтов': 2, 'Стоимость без НДС': 664.03, 'Период': 'окт.25'},
        {'Сервис': 'Комплекс коммерческий VIP Предприятие', 'Уровень': 'Оптимальный', 'Аккаунтов': 2, 'Стоимость без НДС': 406.20, 'Период': 'окт.25'},
        {'Сервис': 'Комплекс коммерческий VIP Предприятие', 'Уровень': 'Минимальный', 'Аккаунтов': 2, 'Стоимость без НДС': 51.11, 'Период': 'окт.25'},
    ]
    df_prices = pd.DataFrame(mock_prices_data)
    user_input_data = {
        "period": "окт.25",
        "service": "Комплекс коммерческий VIP Предприятие",
        "levels": [
            {"level": "Эксперт", "accounts": 2},
            {"level": "Оптимальный", "accounts": 2},
            {"level": "Минимальный", "accounts": 2},
        ],
        "prepayment_months": 12,
        "discount_percent": 0.0,
        "fixation_months": 5,
        "promotion_id": "Акция_Пр.166 (сентябрь25)",
    }
    promotion_info = {
        "details": {
            'ТП': 'Комплекс коммерческий VIP Предприятие',
            'Уровень': 'ЭКСПЕРТОПТИМАЛЬНЫЙМИНИМАЛЬНЫЙ',
            'Условие1': 0.10, # 10% скидка
            'Месяцев': 12,
            'Условие2': '2 мес. со скидкой 99%',
            'Приказ': 'Акция_Пр.166 (сентябрь25)'
        },
        "applicable_levels": ['Эксперт', 'Оптимальный', 'Минимальный']
    }
    
    # --- 2. Выполнение тестируемого кода (Act) ---
    result = run_calculation(
        data=user_input_data,
        df_prices=df_prices,
        promotion_info=promotion_info
    )
    
    # --- 3. Проверка результата (Assert) ---
    assert result is not None, "Результат расчета не должен быть None"
    summary = result.get("price_summary")
    assert summary is not None, "В результате должен быть ключ 'price_summary'"
    assert summary['list_period'] == approx(32294.52)
    assert summary['list_monthly'] == approx(2691.21)
    assert summary['discounted_period'] == approx(24274.70)
    assert summary['discounted_monthly'] == approx(2022.89)
    assert summary['fixed_period'] == approx(34232.16)
    assert summary['fixed_monthly'] == approx(2852.68)


# ===== НОВЫЙ ТЕСТ =====
def test_complex_vip_with_fixation_6_months():
    """
    Тестирует сценарий со второго скриншота:
    - ТП: Комплекс коммерческий VIP Предприятие
    - Уровни: Эксперт(2), Оптимальный(2), Минимальный(2)
    - Период: окт.25
    - Акция: Акция_Пр.166 (сентябрь25) на 12 мес.
    - Фиксация: 6 мес. (коэффициент 1.07)
    """
    
    # --- 1. Подготовка данных (Arrange) ---
    
    # Данные те же, что и в предыдущем тесте, так как ТП и количество пользователей совпадают
    mock_prices_data = [
        {'Сервис': 'Комплекс коммерческий VIP Предприятие', 'Уровень': 'Эксперт', 'Аккаунтов': 2, 'Стоимость без НДС': 664.03, 'Период': 'окт.25'},
        {'Сервис': 'Комплекс коммерческий VIP Предприятие', 'Уровень': 'Оптимальный', 'Аккаунтов': 2, 'Стоимость без НДС': 406.20, 'Период': 'окт.25'},
        {'Сервис': 'Комплекс коммерческий VIP Предприятие', 'Уровень': 'Минимальный', 'Аккаунтов': 2, 'Стоимость без НДС': 51.11, 'Период': 'окт.25'},
    ]
    df_prices = pd.DataFrame(mock_prices_data)
    
    # Входные данные отличаются только фиксацией
    user_input_data = {
        "period": "окт.25",
        "service": "Комплекс коммерческий VIP Предприятие",
        "levels": [
            {"level": "Эксперт", "accounts": 2},
            {"level": "Оптимальный", "accounts": 2},
            {"level": "Минимальный", "accounts": 2},
        ],
        "prepayment_months": 12,
        "discount_percent": 0.0, 
        "fixation_months": 6, # <-- Изменение здесь
        "promotion_id": "Акция_Пр.166 (сентябрь25)",
    }
    
    # Информация об акции та же самая
    promotion_info = {
        "details": {
            'ТП': 'Комплекс коммерческий VIP Предприятие',
            'Уровень': 'ЭКСПЕРТОПТИМАЛЬНЫЙМИНИМАЛЬНЫЙ',
            'Условие1': 0.10, # 10% скидка
            'Месяцев': 12,
            'Условие2': '2 мес. со скидкой 99%',
            'Приказ': 'Акция_Пр.166 (сентябрь25)'
        },
        "applicable_levels": ['Эксперт', 'Оптимальный', 'Минимальный']
    }

    # --- 2. Выполнение тестируемого кода (Act) ---
    
    result = run_calculation(
        data=user_input_data,
        df_prices=df_prices,
        promotion_info=promotion_info
    )

    # --- 3. Проверка результата (Assert) ---

    assert result is not None
    summary = result.get("price_summary")
    assert summary is not None

    # Сверяем цифры с Excel
    assert summary['list_period'] == approx(32294.52)
    assert summary['list_monthly'] == approx(2691.21)

    assert summary['discounted_period'] == approx(24274.70)
    assert summary['discounted_monthly'] == approx(2022.89)

    assert summary['fixed_period'] == approx(34555.20)
    assert summary['fixed_monthly'] == approx(2879.60)