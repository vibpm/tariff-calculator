# main.py (полная обновленная версия)

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse # <-- ДОБАВЛЕН StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import pandas as pd
from typing import Optional, List
from datetime import datetime, date
import json
from urllib.parse import quote

# --- НАШИ МОДУЛИ ---
import logic
import document_generator # <-- ДОБАВЛЕН НАШ НОВЫЙ МОДУЛЬ

# --- Модели данных (без изменений) ---
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

        # ==========================================================
        # ИЗМЕНЕНИЕ ЗДЕСЬ: Конвертируем Decimal в float для JSON
        # ==========================================================
        fixation_map_for_json = {
            key: float(value) for key, value in logic.FIXATION_COEFFICIENT_MAP.items()
        }

        return templates.TemplateResponse("index.html", {
            "request": request, "services": services, "levels": levels,
            "periods": periods, "minutes_map_json": json.dumps(minutes_map),
            "fixation_map_json": json.dumps(fixation_map_for_json) # Используем новую версию
        })

    except KeyError as e:
        return templates.TemplateResponse("error.html", {"request": request, "error_message": f"Ошибка в данных: отсутствует столбец: {e}"})

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
    if not is_single_user_service and total_accounts == 1 and total_accounts > 0:
        warning_message = "Внимание! Выбран многопользовательский тариф, но указан только 1 пользователь."

    try:
        selected_period_date = parse_period_string(data.period).date()
        today = date.today()
        start_of_current_month = today.replace(day=1)
        if selected_period_date < start_of_current_month:
            date_warning = "Используется прейскурант за прошедший месяц."
            if warning_message:
                warning_message += f" {date_warning}"
            else:
                warning_message = date_warning
    except Exception as e:
        print(f"Не удалось проверить дату периода: {e}")
    
    # ==========================================================
    # ИЗМЕНЕНИЕ ЗДЕСЬ: Обрабатываем новую структуру ответа от logic.py
    # ==========================================================
    calculation_result = logic.run_calculation(data.dict(), df_prices)
    
    if calculation_result.get("price_summary") is None:
        return {"error": "Не удалось найти тарифы для указанных позиций."}
    
    context = calculation_result.get("calculation_context", {})
    
    final_response = {
        "price_summary": calculation_result["price_summary"],
        "totals": { "accounts": context.get("total_users", 0) },
        "calculation_context": context # Передаем весь контекст на фронт
    }

    if warning_message:
        final_response["warning"] = warning_message
        
    return final_response

# ==========================================================
# НОВЫЙ ЭНДПОИНТ: Для скачивания коммерческого предложения
# ==========================================================
@app.post("/download_offer")
async def download_offer(data: CalculationInput):
    if df_prices is None:
        raise HTTPException(status_code=500, detail="Данные прайс-листа не загружены.")
        
    # 1. Выполняем расчеты, чтобы получить контекст
    calculation_result = logic.run_calculation(data.dict(), df_prices)
    
    context = calculation_result.get("calculation_context")
    if not context:
        raise HTTPException(status_code=404, detail="Не удалось рассчитать данные для формирования предложения.")
        
    # Дополняем контекст данными
    context['current_date'] = datetime.now().strftime("%d.%m.%Y")
    
    # 2. Генерируем документ
    document_stream = document_generator.create_offer_document(context)
    
    if not document_stream:
        raise HTTPException(status_code=500, detail="Произошла ошибка при создании документа.")
        
    # 3. Отправляем файл пользователю (с правильным кодированием имени файла)
    service_name_slug = context.get('service_name', 'offer').replace('/', '_')
    date_str = context['current_date']
    
    # Создаем имя файла с кириллицей
    original_filename = f"КП {service_name_slug} от {date_str}.docx"
    
    # Кодируем имя файла для HTTP-заголовка
    encoded_filename = quote(original_filename)
    
    media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    
    # Формируем специальный заголовок, который понимают все современные браузеры
    headers = {
        'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
    }
    
    return StreamingResponse(
        document_stream, 
        media_type=media_type, 
        headers=headers
    )