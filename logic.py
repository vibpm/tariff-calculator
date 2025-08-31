# logic.py
import pandas as pd
from typing import Dict, Any, List
from decimal import Decimal, ROUND_HALF_UP

# --- Глобальный "квантизатор" для округления. Определяем один раз. ---
_quantizer = Decimal('0.01')

# --- Функция для округления, теперь работает с Decimal. Заменяет round_excel ---
def round_decimal(n: Decimal) -> Decimal:
    return n.quantize(_quantizer, rounding=ROUND_HALF_UP)

# --- Константы (для удобства тоже приведем к Decimal в начале) ---
VAT_RATE = Decimal('1.2')
FIXATION_COEFFICIENT_MAP = {
    1: Decimal('1.0'), 2: Decimal('1.02'), 3: Decimal('1.04'), 4: Decimal('1.05'), 5: Decimal('1.06'), 6: Decimal('1.07'),
    7: Decimal('1.08'), 8: Decimal('1.09'), 9: Decimal('1.11'), 10: Decimal('1.12'), 11: Decimal('1.13'), 12: Decimal('1.14')
}

# --- Функция поиска (без изменений, т.к. тут нет расчетов) ---
def find_price_tiers(data: Dict[str, Any], df_prices: pd.DataFrame) -> List[Dict[str, Any]]:
    level_prices_info = []
    # ... (весь код этой функции остается прежним)
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
# БЛОК РАСЧЕТОВ ДЛЯ НЕ-ЛД ТАРИФОВ (ПЕРЕПИСАН НА DECIMAL)
# ================================================================

def calculate_non_ld_list_price(level_prices_info: List[Dict[str, Any]], data: Dict[str, Any]) -> Decimal:
    total_price = Decimal('0')
    for item in level_prices_info:
        price_wo_vat = Decimal(str(item['price_without_vat_per_user'])) * Decimal(str(item['accounts']))
        total_price += round_decimal(price_wo_vat * VAT_RATE)
    return total_price

def calculate_non_ld_discounted_price(level_prices_info: List[Dict[str, Any]], data: Dict[str, Any]) -> Decimal:
    total_price = Decimal('0')
    discount = Decimal('1') - (Decimal(str(data.get('discount_percent', 0))) / Decimal('100'))
    for item in level_prices_info:
        price_wo_vat = Decimal(str(item['price_without_vat_per_user'])) * Decimal(str(item['accounts']))
        with_discount = round_decimal(price_wo_vat * discount)
        with_vat = round_decimal(with_discount * VAT_RATE)
        total_price += with_vat
    return total_price

def calculate_non_ld_fixed_price(level_prices_info: List[Dict[str, Any]], data: Dict[str, Any]) -> Decimal:
    total_price = Decimal('0')
    discount = Decimal('1') - (Decimal(str(data.get('discount_percent', 0))) / Decimal('100'))
    fix_coeff = FIXATION_COEFFICIENT_MAP.get(data.get('fixation_months', 0), Decimal('1.0'))
    for item in level_prices_info:
        price_wo_vat = Decimal(str(item['price_without_vat_per_user'])) * Decimal(str(item['accounts']))
        with_fix = round_decimal(price_wo_vat * discount * fix_coeff)
        with_vat = round_decimal(with_fix * VAT_RATE)
        total_price += with_vat
    return total_price

# ================================================================
# БЛОК РАСЧЕТОВ ДЛЯ ЛД ТАРИФОВ (ПЕРЕПИСАН НА DECIMAL)
# ================================================================

def calculate_ld_list_price(level_prices_info: List[Dict[str, Any]], data: Dict[str, Any]) -> Decimal:
    if not level_prices_info: return Decimal('0')
    price_per_user = Decimal(str(level_prices_info[0]['price_without_vat_per_user']))
    prepayment = Decimal(str(data.get('prepayment_months', 1) or 1))
    total_price = (price_per_user * prepayment) * VAT_RATE
    return round_decimal(total_price)

def calculate_ld_discounted_price(level_prices_info: List[Dict[str, Any]], data: Dict[str, Any]) -> Decimal:
    if not level_prices_info: return Decimal('0')
    price_per_user = Decimal(str(level_prices_info[0]['price_without_vat_per_user']))
    prepayment = Decimal(str(data.get('prepayment_months', 1) or 1))
    discount = Decimal('1') - (Decimal(str(data.get('discount_percent', 0))) / Decimal('100'))
    with_discount = round_decimal(price_per_user * discount)
    total_price = (with_discount * prepayment) * VAT_RATE
    return round_decimal(total_price)

def calculate_ld_fixed_price(level_prices_info: List[Dict[str, Any]], data: Dict[str, Any]) -> Decimal:
    if not level_prices_info: return Decimal('0')
    fix_months = data.get('fixation_months', 0)
    if fix_months == 0:
        return calculate_ld_discounted_price(level_prices_info, data)
    
    price_per_user = Decimal(str(level_prices_info[0]['price_without_vat_per_user']))
    prepayment = Decimal(str(data.get('prepayment_months', 1) or 1))
    discount = Decimal('1') - (Decimal(str(data.get('discount_percent', 0))) / Decimal('100'))
    fix_coeff = FIXATION_COEFFICIENT_MAP.get(fix_months, Decimal('1.0'))
    with_fix = round_decimal(price_per_user * discount * fix_coeff)
    total_price = (with_fix * prepayment) * VAT_RATE
    return round_decimal(total_price)

# --- Главная функция-диспетчер (адаптирована под Decimal) ---
def run_calculation(data: Dict[str, Any], df_prices: pd.DataFrame) -> Dict[str, Any]:
    is_ld_service = "ЛД" in data.get('service', '')
    prepayment_months = data.get('prepayment_months', 1) or 1
    D_prepayment_months = Decimal(str(prepayment_months))
    
    level_prices_info = find_price_tiers(data, df_prices)
    if not level_prices_info:
        return {"price_summary": None, "calculation_context": None}

    if is_ld_service:
        list_period = calculate_ld_list_price(level_prices_info, data)
        discounted_period = calculate_ld_discounted_price(level_prices_info, data)
        fixed_period = calculate_ld_fixed_price(level_prices_info, data)
    else:
        list_monthly = calculate_non_ld_list_price(level_prices_info, data)
        discounted_monthly = calculate_non_ld_discounted_price(level_prices_info, data)
        fixed_monthly = calculate_non_ld_fixed_price(level_prices_info, data)
        
        list_period = list_monthly * D_prepayment_months
        discounted_period = discounted_monthly * D_prepayment_months
        fixed_period = fixed_monthly * D_prepayment_months
    
    # Формируем итоговый словарь, конвертируя Decimal обратно во float для JSON
    price_summary = {
        "list_monthly": float(round_decimal(list_period / D_prepayment_months)),
        "list_period": float(round_decimal(list_period)),
        "discounted_monthly": float(round_decimal(discounted_period / D_prepayment_months)),
        "discounted_period": float(round_decimal(discounted_period)),
        "fixed_monthly": float(round_decimal(fixed_period / D_prepayment_months)),
        "fixed_period": float(round_decimal(fixed_period))
    }
    
    context = {
        "service_name": data.get('service', 'N/A'),
        "prepayment_months": prepayment_months,
        "discount_percent": data.get('discount_percent', 0),
        "fixation_months": data.get('fixation_months', 0),
        "total_users": sum(item['accounts'] for item in level_prices_info),
        "levels": level_prices_info,
        "price_summary": price_summary # Используем уже сконвертированный в float словарь
    }

    return {
        "price_summary": price_summary,
        "calculation_context": context
    }