# logic.py
import pandas as pd
from typing import Dict, Any

# --- Константы, необходимые для расчетов ---
VAT_RATE = 1.2
FIXATION_COEFFICIENT_MAP = {
    1: 1.0, 2: 1.02, 3: 1.04, 4: 1.05, 5: 1.06, 6: 1.07,
    7: 1.08, 8: 1.09, 9: 1.11, 10: 1.12, 11: 1.13, 12: 1.14
}

def run_calculation(data: Dict[str, Any], df_prices: pd.DataFrame) -> Dict[str, Any]:
    """
    Основная функция, выполняющая все расчеты калькулятора.
    
    Args:
        data (Dict[str, Any]): Словарь с входными данными от пользователя.
        df_prices (pd.DataFrame): DataFrame с данными прайс-листа.

    Returns:
        Dict[str, Any]: Словарь с результатами расчета.
    """
    
    # --- Извлечение входных данных ---
    is_ld_service = "ЛД" in data.get('service', '')
    prepayment_months = data.get('prepayment_months', 1) or 1
    discount_multiplier = 1 - (data.get('discount_percent', 0) / 100.0)
    fixation_coefficient = FIXATION_COEFFICIENT_MAP.get(data.get('fixation_months', 0), 1.0)
    
    # --- Этап 1: Сбор и расчет цен для каждого уровня ---
    level_results = []
    found_any_price = False

    for level_input in data.get('levels', []):
        accounts = level_input.get('accounts', 0)
        if accounts <= 0:
            continue

        # Поиск подходящей строки в прайсе
        possible_tiers = df_prices[
            (df_prices['Сервис'] == data['service']) &
            (df_prices['Уровень'] == level_input['level']) &
            (df_prices['Период'] == data['period'])
        ]
        if possible_tiers.empty:
            continue

        found_row = None
        exact_match = possible_tiers[possible_tiers['Аккаунтов'] == accounts]
        if not exact_match.empty:
            found_row = exact_match.iloc[0]
        else:
            max_accounts_in_tier = possible_tiers['Аккаунтов'].max()
            if accounts > max_accounts_in_tier:
                found_row = possible_tiers.loc[possible_tiers['Аккаунтов'].idxmax()]
        
        if found_row is not None:
            found_any_price = True
            
            price_without_vat_per_user = found_row.get('Стоимость без НДС', 0.0)
            price_for_level_without_vat = price_without_vat_per_user * accounts
            
            # Расчет трех видов цен для этой строки
            list_price_with_vat = round(price_for_level_without_vat * VAT_RATE, 2)
            
            discounted_price_without_vat_raw = price_for_level_without_vat * discount_multiplier
            discounted_price_with_vat = round(round(discounted_price_without_vat_raw, 2) * VAT_RATE, 2)

            fixed_price_without_vat = round(discounted_price_without_vat_raw * fixation_coefficient, 2)
            fixed_price_with_vat = round(fixed_price_without_vat * VAT_RATE, 2)
            
            level_results.append({
                "list_price": list_price_with_vat,
                "discounted_price": discounted_price_with_vat,
                "fixed_price": fixed_price_with_vat,
            })

    if not found_any_price:
        # Если ничего не нашли, возвращаем пустой результат, чтобы не было ошибки
        return { "price_summary": None }

    # --- Этап 2: Суммирование поэтапно рассчитанных цен ---
    total_list_price_monthly = sum(item['list_price'] for item in level_results)
    total_discounted_price_monthly = sum(item['discounted_price'] for item in level_results)
    total_fixed_price_monthly = sum(item['fixed_price'] for item in level_results)
    
    # --- Этап 3: Расчет итогов за период ---
    price_period_list = total_list_price_monthly * prepayment_months
    price_period_discounted = total_discounted_price_monthly * prepayment_months
    price_period_fixed = total_fixed_price_monthly * prepayment_months

    # --- Формирование ответа ---
    return {
        "price_summary": {
            "list_monthly": float(round(total_list_price_monthly, 2)),
            "list_period": float(round(price_period_list, 2)),
            "discounted_monthly": float(round(total_discounted_price_monthly, 2)),
            "discounted_period": float(round(price_period_discounted, 2)),
            "fixed_monthly": float(round(total_fixed_price_monthly, 2)),
            "fixed_period": float(round(price_period_fixed, 2))
        }
    }