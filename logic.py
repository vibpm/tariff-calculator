# logic.py
import pandas as pd
from typing import Dict, Any, List
from decimal import Decimal, ROUND_HALF_UP

# --- Функция для округления как в Excel ---
def round_excel(n):
    return float(Decimal(str(n)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

# --- Константы ---
VAT_RATE = 1.2
FIXATION_COEFFICIENT_MAP = {
    1: 1.0, 2: 1.02, 3: 1.04, 4: 1.05, 5: 1.06, 6: 1.07,
    7: 1.08, 8: 1.09, 9: 1.11, 10: 1.12, 11: 1.13, 12: 1.14
}

# --- Функция поиска ---
def find_price_tiers(data: Dict[str, Any], df_prices: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Находит подходящие строки в прайс-листе для каждого уровня из запроса.
    Реализует логику точного совпадения и превышения максимума.
    """
    level_prices_info = []
    for level_input in data.get('levels', []):
        accounts = level_input.get('accounts', 0)
        if accounts <= 0:
            continue
        possible_tiers = df_prices[
            (df_prices['Сервис'] == data['service']) &
            (df_prices['Уровень'] == level_input['level']) &
            (df_prices['Период'] == data['period'])
        ]
        if possible_tiers.empty: continue
        found_row = None
        exact_match = possible_tiers[possible_tiers['Аккаунтов'] == accounts]
        if not exact_match.empty:
            found_row = exact_match.iloc[0]
        else:
            max_accounts_in_tier = possible_tiers['Аккаунтов'].max()
            if accounts > max_accounts_in_tier:
                found_row = possible_tiers.loc[possible_tiers['Аккаунтов'].idxmax()]
        if found_row is not None:
            level_prices_info.append({
                "level_name": level_input['level'],
                "accounts": accounts,
                "price_without_vat_per_user": found_row.get('Стоимость без НДС', 0.0),
            })
    return level_prices_info

# ================================================================
# БЛОК РАСЧЕТОВ ДЛЯ НЕ-ЛД ТАРИФОВ
# ================================================================

def calculate_non_ld_list_price(level_prices_info: List[Dict[str, Any]], data: Dict[str, Any]) -> float:
    """
    1. Расчет 'По прейскуранту' для НЕ-ЛД тарифов (ЕЖЕМЕСЯЧНО).
    """
    total_list_price_monthly = 0.0
    for item in level_prices_info:
        price_without_vat = item['price_without_vat_per_user'] * item['accounts']
        total_list_price_monthly += round_excel(price_without_vat * VAT_RATE)
    return total_list_price_monthly

def calculate_non_ld_discounted_price(level_prices_info: List[Dict[str, Any]], data: Dict[str, Any]) -> float:
    """
    2. Расчет 'Итого со скидкой' для НЕ-ЛД тарифов (ЕЖЕМЕСЯЧНО).
    """
    total_discounted_price_monthly = 0.0
    discount_multiplier = 1 - (data.get('discount_percent', 0) / 100.0)
    for item in level_prices_info:
        price_without_vat = item['price_without_vat_per_user'] * item['accounts']
        discounted_without_vat = round_excel(price_without_vat * discount_multiplier)
        total_discounted_price_monthly += round_excel(discounted_without_vat * VAT_RATE)
    return total_discounted_price_monthly

def calculate_non_ld_fixed_price(level_prices_info: List[Dict[str, Any]], data: Dict[str, Any]) -> float:
    """
    3. Расчет 'Итого с фиксацией' для НЕ-ЛД тарифов (ЕЖЕМЕСЯЧНО).
    """
    total_fixed_price_monthly = 0.0
    discount_multiplier = 1 - (data.get('discount_percent', 0) / 100.0)
    fixation_coefficient = FIXATION_COEFFICIENT_MAP.get(data.get('fixation_months', 0), 1.0)
    
    for item in level_prices_info:
        price_without_vat = item['price_without_vat_per_user'] * item['accounts']
        
        # Шаг 1: Применяем скидку и фиксацию к цене БЕЗ НДС
        price_after_discount_and_fix = price_without_vat * discount_multiplier * fixation_coefficient
        
        # Шаг 2: Округляем до 2 знаков
        price_after_discount_and_fix_rounded = round_excel(price_after_discount_and_fix)
        
        # Шаг 3: Начисляем НДС и снова округляем
        final_price_for_level = round_excel(price_after_discount_and_fix_rounded * VAT_RATE)
        
        # Шаг 4: Суммируем
        total_fixed_price_monthly += final_price_for_level
        
    return total_fixed_price_monthly

# ================================================================
# БЛОК РАСЧЕТОВ ДЛЯ ЛД ТАРИФОВ
# ================================================================

def calculate_ld_list_price(level_prices_info: List[Dict[str, Any]], data: Dict[str, Any]) -> float:
    """
    4. Расчет 'По прейскуранту' для ЛД тарифов (ЗА ПЕРИОД).
    """
    # Для ЛД тарифов всегда 1 пользователь, поэтому берем данные из первой (и единственной) строки
    if not level_prices_info:
        return 0.0

    # Берем цену без НДС за 1 пользователя
    price_without_vat_per_user = level_prices_info[0]['price_without_vat_per_user']
    prepayment_months = data.get('prepayment_months', 1) or 1
    
    # Считаем итоговую сумму за период
    total_price_period = round_excel((price_without_vat_per_user * prepayment_months) * VAT_RATE)
    
    return total_price_period

def calculate_ld_discounted_price(level_prices_info: List[Dict[str, Any]], data: Dict[str, Any]) -> float:
    """
    5. Расчет 'Итого со скидкой' для ЛД тарифов (ЗА ПЕРИОД).
    """
    if not level_prices_info:
        return 0.0

    prepayment_months = data.get('prepayment_months', 1) or 1
    discount_multiplier = 1 - (data.get('discount_percent', 0) / 100.0)
    
    # Для ЛД всегда 1 пользователь, берем первую запись
    item = level_prices_info[0]
    price_without_vat = item['price_without_vat_per_user'] * item['accounts']
    
    # Шаг 1: Применяем скидку и округляем
    discounted_price_monthly_without_vat = round_excel(price_without_vat * discount_multiplier)
    
    # Шаг 2: Умножаем на период, НДС и финально округляем
    total_discounted_price_period = round_excel((discounted_price_monthly_without_vat * prepayment_months) * VAT_RATE)
        
    return total_discounted_price_period

def calculate_ld_fixed_price(level_prices_info: List[Dict[str, Any]], data: Dict[str, Any]) -> float:
    """
    6. Расчет 'Итого с фиксацией' для ЛД тарифов (ЗА ПЕРИОД).
    """
    if not level_prices_info:
        return 0.0

    prepayment_months = data.get('prepayment_months', 1) or 1
    discount_multiplier = 1 - (data.get('discount_percent', 0) / 100.0)
    fixation_months = data.get('fixation_months', 0)
    fixation_coefficient = FIXATION_COEFFICIENT_MAP.get(fixation_months, 1.0)

    # Если фиксации нет, цена равна цене со скидкой
    if fixation_months == 0:
        return calculate_ld_discounted_price(level_prices_info, data)
    
    # Для ЛД всегда 1 пользователь, берем первую запись
    item = level_prices_info[0]
    price_without_vat = item['price_without_vat_per_user'] * item['accounts']
    
    # Шаг 1: Применяем скидку и фиксацию к цене БЕЗ НДС и округляем
    fixed_price_monthly_without_vat = round_excel(price_without_vat * discount_multiplier * fixation_coefficient)
    
    # Шаг 2: Умножаем на период, начисляем НДС и финально округляем
    # Особенность Excel: (цена * период) * ндс, а не (цена * ндс) * период
    total_fixed_price_period = round_excel((fixed_price_monthly_without_vat * prepayment_months) * VAT_RATE)
        
    return total_fixed_price_period

# --- Главная функция-диспетчер ---
def run_calculation(data: Dict[str, Any], df_prices: pd.DataFrame) -> Dict[str, Any]:
    is_ld_service = "ЛД" in data.get('service', '')
    prepayment_months = data.get('prepayment_months', 1) or 1
    
    level_prices_info = find_price_tiers(data, df_prices)
    if not level_prices_info:
        return {"price_summary": None}

    if is_ld_service:
        list_period = calculate_ld_list_price(level_prices_info, data)
        discounted_period = calculate_ld_discounted_price(level_prices_info, data)
        fixed_period = calculate_ld_fixed_price(level_prices_info, data)
    else:
        list_monthly = calculate_non_ld_list_price(level_prices_info, data)
        discounted_monthly = calculate_non_ld_discounted_price(level_prices_info, data)
        fixed_monthly = calculate_non_ld_fixed_price(level_prices_info, data)
        
        list_period = list_monthly * prepayment_months
        discounted_period = discounted_monthly * prepayment_months
        fixed_period = fixed_monthly * prepayment_months

    return {
        "price_summary": {
            "list_monthly": float(round_excel(list_period / prepayment_months)),
            "list_period": float(round_excel(list_period)),
            "discounted_monthly": float(round_excel(discounted_period / prepayment_months)),
            "discounted_period": float(round_excel(discounted_period)),
            "fixed_monthly": float(round_excel(fixed_period / prepayment_months)),
            "fixed_period": float(round_excel(fixed_period))
        }
    }