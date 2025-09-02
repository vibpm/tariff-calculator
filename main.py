from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import pandas as pd
from typing import List, Union, Optional
from datetime import datetime, date
import json
from urllib.parse import quote
import os
from pathlib import Path

# --- НАШИ МОДУЛИ ---
import logic
import document_generator

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
    promotion_id: Optional[Union[int, str]] = None

class PromotionRequest(BaseModel):
    service: str
    levels: List[str]
    prepayment_months: int

# --- Инициализация ---
app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# --- Глобальные переменные ---
df_prices = None
df_promotions = None

# --- Функции ---
MONTH_MAP = {
    'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
    'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
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
    global df_prices, df_promotions
    DATA_DIR = BASE_DIR / "data_export"
    # ... (код загрузки данных без изменений) ...
    # --- 1. Загрузка прайс-листа ---
    filepath_prices = DATA_DIR / "pricelist.csv"
    try:
        df_prices = pd.read_csv(filepath_prices, sep=';', on_bad_lines='skip', encoding='utf-8', decimal=',')
        df_prices.dropna(axis=1, how='all', inplace=True)
        df_prices.dropna(axis=0, how='all', inplace=True)
        df_prices.columns = df_prices.columns.str.strip()
        for col in ['Сервис', 'Уровень', 'Период']:
            if col in df_prices.columns: df_prices[col] = df_prices[col].str.strip()
        if 'Аккаунтов' in df_prices.columns: df_prices['Аккаунтов'] = df_prices['Аккаунтов'].fillna(0).astype(int)
        if 'Минут' in df_prices.columns:
            df_prices['Минут'] = df_prices['Минут'].astype(str).str.split('/').str[0].str.strip()
            df_prices['Минут'] = pd.to_numeric(df_prices['Минут'], errors='coerce').fillna(0).astype(int)
        print(f"✓ Прайс-лист '{filepath_prices}' успешно загружен и обработан.")
    except Exception as e:
        print(f"!!! КРИТИЧЕСКАЯ ОШИБКА при чтении прайс-листа: {e}")
        df_prices = None

    # --- 2. Загрузка акций ---
    filepath_promos = DATA_DIR / "promotions.xlsx"
    try:
        df_promotions = pd.read_excel(filepath_promos)
        df_promotions.columns = df_promotions.columns.str.strip()
        for col in ['ТП', 'Уровень', 'Приказ', 'Условие2']:
            if col in df_promotions.columns: df_promotions[col] = df_promotions[col].astype(str).str.strip()
        if 'Условие1' in df_promotions.columns: df_promotions['Условие1'] = pd.to_numeric(df_promotions['Условие1'], errors='coerce').fillna(0.0)
        if 'Месяцев' in df_promotions.columns: df_promotions['Месяцев'] = pd.to_numeric(df_promotions['Месяцев'], errors='coerce').fillna(0).astype(int)
        print(f"✓ Акции из файла '{filepath_promos}' успешно загружены.")
    except FileNotFoundError:
        print(f"--- ПРЕДУПРЕЖДЕНИЕ: Файл с акциями '{filepath_promos}' не найден. Акции не будут доступны.")
        df_promotions = pd.DataFrame()
    except Exception as e:
        print(f"!!! КРИТИЧЕСКАЯ ОШИБКА при чтении файла акций: {e}")
        df_promotions = pd.DataFrame()


# --- Маршруты (Endpoints) ---

@app.get("/", response_class=HTMLResponse)
async def get_main_page(request: Request):
    # ... (код без изменений) ...
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
        fixation_map_for_json = {key: float(value) for key, value in logic.FIXATION_COEFFICIENT_MAP.items()}
        return templates.TemplateResponse("index.html", {
            "request": request, "services": services, "levels": levels,
            "periods": periods, "minutes_map_json": json.dumps(minutes_map),
            "fixation_map_json": json.dumps(fixation_map_for_json)
        })
    except KeyError as e:
        return templates.TemplateResponse("error.html", {"request": request, "error_message": f"Ошибка в данных: отсутствует столбец: {e}"})

@app.get("/get_levels_for_service/{service_name}")
async def get_levels_for_service(service_name: str):
    # ... (код без изменений) ...
    if df_prices is None: return []
    try:
        filtered_df = df_prices[df_prices['Сервис'] == service_name]
        levels_from_file = filtered_df['Уровень'].dropna().unique().tolist()
        custom_order = ["Эксперт", "Оптимальный", "Оптимальный Плюс", "Минимальный", "Базовый"]
        sorted_levels = sorted(levels_from_file, key=lambda level: (custom_order.index(level) if level in custom_order else float('inf'), level))
        return sorted_levels
    except Exception as e:
        print(f"Ошибка при получении уровней для сервиса '{service_name}': {e}")
        return []

@app.post("/get_promotions")
async def get_promotions_for_service(data: PromotionRequest):
    # ... (код без изменений, мы его уже исправили) ...
    available_promotions = [{"id": "no_promotion", "name": "Нет акции"}]
    if df_promotions is None or df_promotions.empty:
        return available_promotions
    try:
        service_lower = data.service.lower()
        levels_lower = [level.lower() for level in data.levels]
        filtered_df = df_promotions[
            (df_promotions['ТП'].str.lower() == service_lower) &
            (df_promotions['Уровень'].str.lower().isin(levels_lower)) &
            (df_promotions['Месяцев'] == data.prepayment_months)
        ]
        if not filtered_df.empty:
            for promo_name, group in filtered_df.groupby('Приказ'):
                promo_representative = group.iloc[0]
                applicable_levels = group['Уровень'].unique().tolist()
                promo_data = {
                    "id": promo_name, 
                    "name": promo_name,
                    "discount_percent": promo_representative['Условие1'] * 100,
                    "months": int(promo_representative['Месяцев']),
                    "condition2": promo_representative['Условие2'],
                    "applicable_levels": applicable_levels
                }
                available_promotions.append(promo_data)
        return available_promotions
    except Exception as e:
        print(f"!!! ОШИБКА при поиске акций для '{data.service}': {e}")
        return [{"id": "no_promotion", "name": "Нет акции"}]

@app.post("/calculate")
async def handle_calculation(data: CalculationInput):
    if df_prices is None: raise HTTPException(status_code=500, detail="Данные прайс-листа не загружены.")

    # --- Валидация (без изменений) ---
    # ...

    # ===== ИЗМЕНЕНИЕ ЗДЕСЬ: Новый, точный поиск акции для расчета =====
    promotion_details = None
    if data.promotion_id is not None and data.promotion_id != 'no_promotion':
        if not df_promotions.empty:
            # Ищем акцию по тем же трем параметрам, что и на фронтенде
            service_lower = data.service.lower()
            levels_lower = [level.level.lower() for level in data.levels]
            
            promo_df = df_promotions[
                (df_promotions['ТП'].str.lower() == service_lower) &
                (df_promotions['Уровень'].str.lower().isin(levels_lower)) &
                (df_promotions['Месяцев'] == data.prepayment_months) &
                # Дополнительно фильтруем по названию приказа, чтобы быть на 100% уверенными
                (df_promotions['Приказ'] == data.promotion_id) 
            ]
            if not promo_df.empty:
                promotion_details = promo_df.to_dict('records')

    calculation_result = logic.run_calculation(
        data.dict(), 
        df_prices,
        promotion_details=promotion_details
    )
    # ====================================================================

    if calculation_result.get("price_summary") is None:
        return {"error": "Не удалось найти тарифы для указанных позиций."}
    
    context = calculation_result.get("calculation_context", {})
    final_response = {
        "price_summary": calculation_result["price_summary"],
        "totals": { "accounts": context.get("total_users", 0) },
        "calculation_context": context
    }
    # ... (warning_message и return без изменений) ...
    return final_response

@app.post("/download_offer")
async def download_offer(data: CalculationInput):
    if df_prices is None: raise HTTPException(status_code=500, detail="Данные прайс-листа не загружены.")
        
    # ===== ИЗМЕНЕНИЕ ЗДЕСЬ: Синхронизируем логику с /calculate =====
    promotion_details = None
    if data.promotion_id is not None and data.promotion_id != 'no_promotion':
        if not df_promotions.empty:
            service_lower = data.service.lower()
            levels_lower = [level.level.lower() for level in data.levels]
            promo_df = df_promotions[
                (df_promotions['ТП'].str.lower() == service_lower) &
                (df_promotions['Уровень'].str.lower().isin(levels_lower)) &
                (df_promotions['Месяцев'] == data.prepayment_months) &
                (df_promotions['Приказ'] == data.promotion_id)
            ]
            if not promo_df.empty:
                promotion_details = promo_df.to_dict('records')

    calculation_result = logic.run_calculation(
        data.dict(), 
        df_prices,
        promotion_details=promotion_details
    )
    # ===============================================================
    
    context = calculation_result.get("calculation_context")
    if not context:
        raise HTTPException(status_code=404, detail="Не удалось рассчитать данные для формирования предложения.")
        
    context['current_date'] = datetime.now().strftime("%d.%m.%Y")
    document_stream = document_generator.create_offer_document(context)
    if not document_stream:
        raise HTTPException(status_code=500, detail="Произошла ошибка при создании документа.")
        
    service_name_slug = context.get('service_name', 'offer').replace('/', '_')
    date_str = context['current_date']
    original_filename = f"КП {service_name_slug} от {date_str}.docx"
    encoded_filename = quote(original_filename)
    media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    headers = {'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"}
    return StreamingResponse(document_stream, media_type=media_type, headers=headers)