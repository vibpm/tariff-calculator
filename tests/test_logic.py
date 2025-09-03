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
    # ===== НОВЫЙ ТЕСТ =====
def test_ld_service_monthly_price_rounding():
    """
    Проверяет корректность округления ежемесячной цены для ЛД-тарифов.
    Ежемесячная цена должна считаться как (цена_без_ндс * 1.2) с округлением,
    а не как (цена_за_период / кол-во_месяцев).
    """
    
    # --- 1. Arrange ---
    mock_prices_data = [
        {'Сервис': 'Пакет Программ Главный Бухгалтер, Podpis, ilex.Накладные (1 пользователь, ЛД)', 
         'Уровень': 'Оптимальный', 'Аккаунтов': 1, 'Стоимость без НДС': 79.17, 'Период': 'окт.25'},
    ]
    df_prices = pd.DataFrame(mock_prices_data)
    
    user_input_data = {
        "period": "окт.25",
        "service": "Пакет Программ Главный Бухгалтер, Podpis, ilex.Накладные (1 пользователь, ЛД)",
        "levels": [{"level": "Оптимальный", "accounts": 1}],
        "prepayment_months": 4,
        "discount_percent": 0.0,
        "fixation_months": 0,
        "promotion_id": None,
    }

    # --- 2. Act ---
    result = run_calculation(data=user_input_data, df_prices=df_prices, promotion_info=None)
    
    # --- 3. Assert ---
    summary = result.get("price_summary")
    assert summary is not None
    
    # Проверяем, что итоговая цена за период осталась прежней (380.02)
    assert summary['list_period'] == approx(380.02)
    # А вот ежемесячная цена теперь должна быть 95.00, а не 95.01
    assert summary['list_monthly'] == approx(95.00)
# ===== НОВЫЙ ТЕСТ ДЛЯ СЦЕНАРИЯ С "ОПТИМАЛЬНЫЙ ПЛЮС" =====
def test_ld_service_optimal_plus_no_promo():
    """
    Проверяет корректность расчета для ЛД-тарифа "Оптимальный Плюс" без акций.
    - ТП: Пакет Программ Главный Бухгалтер, Podpis, ilex.Накладные (1 пользователь, ЛД)
    - Уровень: Оптимальный Плюс (1)
    - Период: окт.25
    - Предоплата: 4 мес.
    - Акции и фиксации нет.
    """
    
    # --- 1. Arrange (Подготовка) ---
    
    # Нам нужна всего одна строка из прайс-листа для этого теста
    mock_prices_data = [
        {'Сервис': 'Пакет Программ Главный Бухгалтер, Podpis, ilex.Накладные (1 пользователь, ЛД)', 
         'Уровень': 'Оптимальный Плюс', 
         'Аккаунтов': 1, 
         'Стоимость без НДС': 92.06, # Эту цифру берем из pricelist.xlsx
         'Период': 'окт.25'},
    ]
    df_prices = pd.DataFrame(mock_prices_data)
    
    # Имитируем запрос с фронтенда
    user_input_data = {
        "period": "окт.25",
        "service": "Пакет Программ Главный Бухгалтер, Podpis, ilex.Накладные (1 пользователь, ЛД)",
        "levels": [{"level": "Оптимальный Плюс", "accounts": 1}],
        "prepayment_months": 4,
        "discount_percent": 0.0,
        "fixation_months": 0,
        "promotion_id": None, # Акции нет
    }

    # --- 2. Act (Действие) ---
    
    # Акции нет, поэтому promotion_info передаем как None
    result = run_calculation(data=user_input_data, df_prices=df_prices, promotion_info=None)
    
    # --- 3. Assert (Проверка) ---
    
    summary = result.get("price_summary")
    assert summary is not None
    
    # Сверяем ключевые цифры с Excel
    assert summary['list_period'] == approx(441.89)
    assert summary['list_monthly'] == approx(110.47)
    
    # Поскольку скидок и фиксации нет, остальные поля должны совпадать с 'list'
    assert summary['discounted_period'] == approx(441.89)
    assert summary['discounted_monthly'] == approx(110.47)
    assert summary['fixed_period'] == approx(441.89)
    assert summary['fixed_monthly'] == approx(110.47)
# ===== НОВЫЙ ТЕСТ ДЛЯ "ГЛАВНЫЙ БУХГАЛТЕР ПРОФ" =====
def test_glavbuh_prof_multi_level_with_discount_and_fixation():
    """
    Проверяет сценарий с несколькими уровнями, ручной скидкой и фиксацией для не-ЛД тарифа.
    - ТП: Главный Бухгалтер ПРОФ
    - Уровни: Эксперт(1), Оптимальный(2), Базовый(3)
    - Период: окт.25
    - Предоплата: 4 мес.
    - Скидка: 5%
    - Фиксация: 6 мес.
    """
    
    # --- 1. Arrange (Подготовка) ---
    
    # Собираем все необходимые строки из прайс-листа для этого теста
    mock_prices_data = [
        {'Сервис': 'Главный Бухгалтер ПРОФ', 'Уровень': 'Эксперт', 'Аккаунтов': 1, 'Стоимость без НДС': 205.64, 'Период': 'окт.25'},
        {'Сервис': 'Главный Бухгалтер ПРОФ', 'Уровень': 'Оптимальный', 'Аккаунтов': 2, 'Стоимость без НДС': 101.16, 'Период': 'окт.25'},
        {'Сервис': 'Главный Бухгалтер ПРОФ', 'Уровень': 'Базовый', 'Аккаунтов': 3, 'Стоимость без НДС': 28.86, 'Период': 'окт.25'},
    ]
    df_prices = pd.DataFrame(mock_prices_data)
    
    # Имитируем запрос с фронтенда на основе скриншота
    user_input_data = {
        "period": "окт.25",
        "service": "Главный Бухгалтер ПРОФ",
        "levels": [
            {"level": "Эксперт", "accounts": 1},
            {"level": "Оптимальный", "accounts": 2},
            {"level": "Базовый", "accounts": 3},
        ],
        "prepayment_months": 4,
        "discount_percent": 5.0,
        "fixation_months": 6,
        "promotion_id": None, # Акции нет
    }

    # --- 2. Act (Действие) ---
    
    # Вызываем нашу основную функцию. promotion_info=None, так как акции нет.
    result = run_calculation(data=user_input_data, df_prices=df_prices, promotion_info=None)
    
    # --- 3. Assert (Проверка) ---
    
    summary = result.get("price_summary")
    assert summary is not None
    
    # Сверяем каждую цифру с эталоном из Excel
    assert summary['list_period'] == approx(2373.80)
    assert summary['list_monthly'] == approx(593.45)

    assert summary['discounted_period'] == approx(2255.08)
    assert summary['discounted_monthly'] == approx(563.77)

    assert summary['fixed_period'] == approx(2412.96)
    assert summary['fixed_monthly'] == approx(603.24)