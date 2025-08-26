# main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import pandas as pd
from typing import Optional, List, Dict
from datetime import datetime, date
import json

# --- Модели данных ---
class LevelInput(BaseModel):
    level: str
    accounts: int

class CalculationInput(BaseModel):
    period: str
    service: str
    levels: List[LevelInput]
    prepayment_months: int = 1
    discount_percent: float = 0.0
    fixation_months: int = 0

# --- Инициализация ---
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Глобальные переменные и функции ---
df_prices = None
MONTH_MAP = {
    'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
    'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
}
FIXATION_COEFFICIENT_MAP = {
    1: 1.0, 2: 1.02, 3: 1.04, 4: 1.05, 5: 1.06, 6: 1.07,
    7: 1.08, 8: 1.09, 9: 1.11, 10: 1.12, 11: 1.13, 12: 1.14
}

def parse_period_string(period_str: str) -> datetime:
    try:
        month_abbr, year_part = period_str.lower().split('.')
        month_num = MONTH_MAP.get(month_abbr, 1)
        year = 2000 + int(year_part)
        return datetime(year, month_num, 1)
    except (ValueError, IndexError):
        return datetime(1900, 1, 1)

@app.on_event("startup")
def load_data():
    global df_prices
    filepath = 'data_export/pricelist.csv'
    try:
        print(f"Попытка прочитать и обработать файл: {filepath}...")
        df_prices = pd.read_csv(
            filepath, sep=';', on_bad_lines='skip', 
            encoding='utf-8', decimal=','
        )
        df_prices.dropna(axis=1, how='all', inplace=True)
        df_prices.dropna(axis=0, how='all', inplace=True)
        df_prices.columns = df_prices.columns.str.strip()
        
        for col in ['Сервис', 'Уровень', 'Период']:
            if col in df_prices.columns:
                df_prices[col] = df_prices[col].str.strip()

        if 'Аккаунтов' in df_prices.columns:
            df_prices['Аккаунтов'] = df_prices['Аккаунтов'].fillna(0).astype(int)
        if 'Минут' in df_prices.columns:
            df_prices['Минут'] = df_prices['Минут'].astype(str).str.split('/').str[0].str.strip()
            df_prices['Минут'] = pd.to_numeric(df_prices['Минут'], errors='coerce').fillna(0).astype(int)
        
        print(f"✓ Прайс-лист '{filepath}' успешно загружен и обработан.")
    except Exception as e:
        print(f"!!! КРИТИЧЕСКАЯ ОШИБКА при чтении или обработке CSV: {e}")
        df_prices = None

# --- Маршруты (Endpoints) ---

@app.get("/", response_class=HTMLResponse)
async def get_main_page(request: Request):
    if df_prices is None or df_prices.empty:
        return templates.TemplateResponse("error.html", {"request": request, "error_message": "Данные не загружены."})
    try:
        services = sorted(df_prices.dropna(subset=['Уровень'])['Сервис'].unique().tolist())
        levels_from_file = df_prices['Уровень'].dropna().unique().tolist()
        custom_order = ["Эксперт", "Оптимальный", "Оптимальный Плюс", "Минимальный", "Базовый"]
        levels = sorted(levels_from_file, key=lambda level: (custom_order.index(level) if level in custom_order else float('inf'), level))
        periods_list = df_prices['Период'].dropna().unique().tolist()
        periods = sorted(periods_list, key=parse_period_string)
        minutes_map = {}
        minutes_df = df_prices[['Уровень', 'Минут']].dropna().drop_duplicates('Уровень').set_index('Уровень')
        minutes_map = minutes_df['Минут'].astype(int).to_dict()
    except KeyError as e:
        return templates.TemplateResponse("error.html", {"request": request, "error_message": f"Ошибка в данных: отсутствует столбец: {e}"})
    
    return templates.TemplateResponse("index.html", {
        "request": request, "services": services, "levels": levels,
        "periods": periods, "minutes_map_json": json.dumps(minutes_map),
        "fixation_map_json": json.dumps(FIXATION_COEFFICIENT_MAP)
    })

@app.get("/get_levels_for_service/{service_name}")
async def get_levels_for_service(service_name: str):
    if df_prices is None: return []
    try:
        filtered_df = df_prices[df_prices['Сервис'] == service_name]
        levels_from_file = filtered_df['Уровень'].dropna().unique().tolist()
        custom_order = ["Эксперт", "Оптимальный", "Оптимальный Плюс", "Минимальный", "Базовый"]
        sorted_levels = sorted(
            levels_from_file, 
            key=lambda level: (custom_order.index(level) if level in custom_order else float('inf'), level)
        )
        return sorted_levels
    except Exception as e:
        print(f"Ошибка при получении уровней для сервиса '{service_name}': {e}")
        return []

@app.post("/calculate")
async def handle_calculation(data: CalculationInput):
    if df_prices is None:
        raise HTTPException(status_code=500, detail="Данные прайс-листа не загружены.")

    # --- Валидация входных данных ---
    total_accounts = sum(item.accounts for item in data.levels)
    is_ld_service = "ЛД" in data.service
    if is_ld_service and data.prepayment_months < 4:
        return {"error": "Для тарифных планов типа 'ЛД' период предоплаты не может быть меньше 4 месяцев."}
    
    is_single_user_service = "1 пользователь" in data.service
    if is_single_user_service and total_accounts > 1:
        return {"error": f"Тарифный план '{data.service}' является однопользовательским. Выбрано пользователей: {total_accounts}."}

    warning_message = None
    try:
        selected_period_date = parse_period_string(data.period).date()
        today = date.today()
        start_of_current_month = today.replace(day=1)
        if selected_period_date < start_of_current_month:
            warning_message = "Внимание! Используется прейскурант за прошедший месяц."
    except Exception as e:
        print(f"Не удалось проверить дату периода: {e}")
    # --- Конец валидации ---

    # --- Новая логика расчета, в точности копирующая Excel ---
    level_results = []
    discount_multiplier = 1 - (data.discount_percent / 100.0)
    fixation_coefficient = FIXATION_COEFFICIENT_MAP.get(data.fixation_months, 1.0)
    VAT_RATE = 1.2

    for level_input in data.levels:
        if level_input.accounts <= 0: continue
        try:
            result_df = df_prices.loc[
                (df_prices['Сервис'] == data.service) &
                (df_prices['Уровень'] == level_input.level) &
                (df_prices['Аккаунтов'] == level_input.accounts) &
                (df_prices['Период'] == data.period)
            ]
            if not result_df.empty:
                found_row = result_df.iloc[0]
                price_without_vat_per_user = found_row.get('Стоимость без НДС', 0.0)
                price_for_level_without_vat = price_without_vat_per_user * level_input.accounts
                
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
        except Exception as e:
            print(f"Ошибка при расчете для уровня '{level_input.level}': {e}")
            raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера.")

    if not level_results and total_accounts > 0:
         return {"error": "Не удалось найти тарифы для указанных позиций."}

    total_list_price_monthly = sum(item['list_price'] for item in level_results)
    total_discounted_price_monthly = sum(item['discounted_price'] for item in level_results)
    total_fixed_price_monthly = sum(item['fixed_price'] for item in level_results)
    
    prepayment_months = data.prepayment_months if data.prepayment_months > 0 else 1

    price_period_list = total_list_price_monthly * prepayment_months
    price_period_discounted = total_discounted_price_monthly * prepayment_months
    price_period_fixed = total_fixed_price_monthly * prepayment_months

    # --- Формирование ответа ---
    response_data = {
        "price_summary": {
            "list_monthly": float(round(total_list_price_monthly, 2)),
            "list_period": float(round(price_period_list, 2)),
            "discounted_monthly": float(round(total_discounted_price_monthly, 2)),
            "discounted_period": float(round(price_period_discounted, 2)),
            "fixed_monthly": float(round(total_fixed_price_monthly, 2)),
            "fixed_period": float(round(price_period_fixed, 2))
        },
        "totals": { "accounts": int(total_accounts) }
    }
    
    if warning_message:
        response_data["warning"] = warning_message
        
    return response_data