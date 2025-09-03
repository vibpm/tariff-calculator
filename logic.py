# logic.py

import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
import re

# --- Утилиты и константы ---
_quantizer = Decimal('0.01')

def round_decimal(n: Decimal) -> Decimal:
    return n.quantize(_quantizer, rounding=ROUND_HALF_UP)

VAT_RATE = Decimal('1.2')
FIXATION_COEFFICIENT_MAP = {
    1: Decimal('1.0'), 2: Decimal('1.02'), 3: Decimal('1.04'), 4: Decimal('1.05'), 5: Decimal('1.06'), 6: Decimal('1.07'),
    7: Decimal('1.08'), 8: Decimal('1.09'), 9: Decimal('1.11'), 10: Decimal('1.12'), 11: Decimal('1.13'), 12: Decimal('1.14')
}

# --- НОВЫЙ БЛОК: Логика для разбора "комбо" уровней ---
# Полный список всех возможных уровней, отсортированный по длине НАОБОРОТ.
# Это "словарь" для нашего парсера.
KNOWN_LEVELS = sorted([
    "Эксперт", 
    "Оптимальный", 
    "Оптимальный Плюс", 
    "Минимальный", 
    "Базовый"
], key=len, reverse=True)

def _parse_combo_level(level_string: str) -> List[str]:
    """
    Разбирает строку с уровнями ('ЭКСПЕРТОПТИМАЛЬНЫЙ') в список ['Эксперт', 'Оптимальный'].
    Если разобрать не удалось, возвращает исходную строку как единственный элемент списка.
    """
    if not isinstance(level_string, str):
        return []
        
    upper_level_string = level_string.upper().replace(" ", "").replace("/", "")
    found_levels = []
    
    temp_string = upper_level_string
    for level in KNOWN_LEVELS:
        upper_known_level = level.upper().replace(" ", "").replace("/", "")
        if upper_known_level in temp_string:
            found_levels.append(level)
            temp_string = temp_string.replace(upper_known_level, "", 1)
            
    if not temp_string.strip() and found_levels:
        return found_levels
    else:
        return [level_string]
# --- КОНЕЦ НОВОГО БЛОКА ---


# --- Функция поиска ---
def find_price_tiers(data: Dict[str, Any], df_prices: pd.DataFrame) -> List[Dict[str, Any]]:
    level_prices_info = []
    for level_input in data.get('levels', []):
        accounts = level_input.get('accounts', 0)
        if accounts <= 0: continue
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
# СТАРЫЙ БЛОК РАСЧЕТОВ (ДЛЯ РУЧНОЙ СКИДКИ)
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


# ================================================================
# НОВАЯ ЛОГИКА РАСЧЕТА ДЛЯ АКЦИЙ
# ================================================================

def _parse_condition2(condition: str) -> Optional[Tuple[int, Decimal]]:
    if not isinstance(condition, str) or '%' not in condition:
        return None
    
    numbers = re.findall(r'\d+', condition)
    if len(numbers) >= 2:
        months = int(numbers[0])
        discount_percent = Decimal(numbers[1])
        return months, discount_percent / Decimal('100')
    return None

def _calculate_discounted_price_with_promotion(
    level_prices_info: List[Dict[str, Any]], 
    data: Dict[str, Any],
    promotion_details: Dict[str, Any],
    applicable_promo_levels: List[str],
    is_ld_service: bool
) -> Decimal:
    
    print("\n" + "="*50)
    print("ЗАПУСК РАСЧЕТА ПО АКЦИИ (с точной математикой)")
    print("="*50)

    promo_representative = promotion_details
    total_period_price_with_vat = Decimal('0')
    prepayment_months = int(promo_representative.get('Месяцев', data.get('prepayment_months', 1)))
    base_discount_multiplier = Decimal('1') - Decimal(str(promo_representative.get('Условие1', 0)))
    special_condition = _parse_condition2(promo_representative.get('Условие2'))
    promo_levels_set = {level.lower() for level in applicable_promo_levels}

    print(f"Акция: {promo_representative.get('Приказ')}")
    print(f"Период: {prepayment_months} мес.")
    print(f"Основная скидка: {promo_representative.get('Условие1') * 100}% (множитель: {base_discount_multiplier})")
    if special_condition: print(f"Спец. условие: {special_condition[0]} мес. со скидкой {special_condition[1] * 100}%")
    else: print("Спец. условие: Нет")
    print(f"Акция действует на уровни: {promo_levels_set}")
    print("\n--- НАЧАЛО РАСЧЕТА ПО МЕСЯЦАМ ---")
    
    for month_num in range(1, prepayment_months + 1):
        price_this_month_with_vat = Decimal('0')
        print(f"\n--- Месяц {month_num} ---")
        
        for level in level_prices_info:
            level_name = level['level_name']
            accounts = Decimal(str(level['accounts']))
            price_per_user_wo_vat = Decimal(str(level['price_without_vat_per_user']))
            
            current_discount_multiplier = Decimal('1')
            if level_name.lower() in promo_levels_set:
                current_discount_multiplier = base_discount_multiplier
                if special_condition:
                    special_months, special_discount = special_condition
                    if month_num <= special_months:
                        current_discount_multiplier = Decimal('1') - special_discount
            
            price_for_level_with_discount_wo_vat = (price_per_user_wo_vat * accounts) * current_discount_multiplier
            rounded_price_wo_vat = round_decimal(price_for_level_with_discount_wo_vat)
            
            if not is_ld_service:
                price_for_level_final = round_decimal(rounded_price_wo_vat * VAT_RATE)
            else:
                price_for_level_final = rounded_price_wo_vat
            
            print(f"  Уровень '{level_name}': Множитель={current_discount_multiplier}, Цена со скидкой без НДС={price_for_level_with_discount_wo_vat:.4f} -> Округлено={rounded_price_wo_vat:.2f} -> Итого с НДС={price_for_level_final:.2f}")

            price_this_month_with_vat += price_for_level_final
        
        print(f"  > Итого за месяц {month_num}: {price_this_month_with_vat:.2f}")
        total_period_price_with_vat += price_this_month_with_vat

    if is_ld_service:
        total_period_price_with_vat = round_decimal(total_period_price_with_vat * VAT_RATE)
        
    print("="*50)
    print(f"ФИНАЛЬНАЯ ЦЕНА ЗА ПЕРИОД (до округления): {total_period_price_with_vat}")
    final_result = round_decimal(total_period_price_with_vat)
    print(f"ФИНАЛЬНАЯ ЦЕНА ЗА ПЕРИОД (после округления): {final_result}")
    print("="*50)

    return final_result


# --- ГЛАВНАЯ ФУНКЦИЯ-ДИСПЕТЧЕР ---
def run_calculation(
    data: Dict[str, Any], 
    df_prices: pd.DataFrame,
    promotion_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    
    is_ld_service = "ЛД" in data.get('service', '')
    prepayment_months = data.get('prepayment_months', 1) or 1
    
    promotion_details = None
    applicable_promo_levels = []
    if promotion_info:
        promotion_details = promotion_info.get("details")
        applicable_promo_levels = promotion_info.get("applicable_levels", [])
        if promotion_details and promotion_details.get('Месяцев'):
            prepayment_months = int(promotion_details['Месяцев'])
    
    D_prepayment_months = Decimal(str(prepayment_months))
    
    level_prices_info = find_price_tiers(data, df_prices)
    if not level_prices_info:
        return {"price_summary": None, "calculation_context": None}

    # --- РАСЧЕТ ПО ПРЕЙСКУРАНТУ ---
    list_monthly_base = Decimal('0')
    for item in level_prices_info:
        price = Decimal(str(item['price_without_vat_per_user'])) * Decimal(str(item['accounts']))
        if not is_ld_service:
            list_monthly_base += round_decimal(price * VAT_RATE)
        else:
            list_monthly_base += price
    if is_ld_service:
        list_period = round_decimal(list_monthly_base * D_prepayment_months * VAT_RATE)
    else:
        list_period = list_monthly_base * D_prepayment_months
    
    # --- РАСЧЕТ СО СКИДКОЙ И ФИКСАЦИЕЙ ---
    if promotion_details:
        discounted_period = _calculate_discounted_price_with_promotion(
            level_prices_info, data, promotion_details, applicable_promo_levels, is_ld_service
        )
        fixed_period = discounted_period 
    else:
        if is_ld_service:
            discounted_period = calculate_ld_discounted_price(level_prices_info, data)
            fixed_period = calculate_ld_fixed_price(level_prices_info, data)
        else:
            discounted_monthly = calculate_non_ld_discounted_price(level_prices_info, data)
            fixed_monthly = calculate_non_ld_fixed_price(level_prices_info, data)
            discounted_period = discounted_monthly * D_prepayment_months
            fixed_period = fixed_monthly * D_prepayment_months
    
    # --- Формирование итогового словаря ---
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
        "price_summary": price_summary
    }

    return {
        "price_summary": price_summary,
        "calculation_context": context
    }