# C:\excel-to-web\main.py

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import pandas as pd
from typing import List, Union, Optional, Dict, Any
from datetime import datetime
import json
from urllib.parse import quote
from pathlib import Path
from dateutil.relativedelta import relativedelta # <-- ВОТ ДОБАВЛЕННЫЙ ИМПОРТ

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

class PromotionAllRequest(BaseModel):
    service: str
    levels: List[str]
    
# --- Инициализация ---
app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# --- Глобальные переменные ---
df_prices = None
df_promotions = None

# --- Вспомогательные функции ---
MONTH_MAP = {
    'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
    'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
}

# Определяем главный уровень для комбо-акций
MAIN_LEVEL_NAME = "Эксперт"

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

    # --- 1. Загрузка прайс-листа ---
    filepath_prices = DATA_DIR / "pricelist.xlsx"
    try:
        string_columns = { 'Сервис': str, 'Уровень': str, 'Минут': str }
        df_prices = pd.read_excel(filepath_prices, dtype=string_columns)
        df_prices.dropna(axis=1, how='all', inplace=True)
        df_prices.dropna(axis=0, how='all', inplace=True)
        df_prices.columns = df_prices.columns.str.strip()
        for col in ['Сервис', 'Уровень']:
            if col in df_prices.columns: df_prices[col] = df_prices[col].str.strip()
        if 'Период' in df_prices.columns:
            df_prices['Период'] = pd.to_datetime(df_prices['Период'], errors='coerce')
            df_prices.dropna(subset=['Период'], inplace=True)
            RU_MONTHS_MAP = { 1: 'янв', 2: 'фев', 3: 'мар', 4: 'апр', 5: 'май', 6: 'июн', 7: 'июл', 8: 'авг', 9: 'сен', 10: 'окт', 11: 'ноя', 12: 'дек' }
            df_prices['Период'] = df_prices['Период'].apply( lambda dt: f"{RU_MONTHS_MAP[dt.month]}.{str(dt.year)[-2:]}" )
        if 'Аккаунтов' in df_prices.columns:
            df_prices['Аккаунтов'] = pd.to_numeric(df_prices['Аккаунтов'], errors='coerce').fillna(0).astype(int)
        if 'Минут' in df_prices.columns:
            df_prices['Минут'] = df_prices['Минут'].astype(str).str.replace(r'\.0$', '', regex=True)
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

# --- ===== НАЧАЛО ЗАМЕНЫ ===== ---
# --- ОБНОВЛЕННАЯ ЦЕНТРАЛИЗОВАННАЯ ФУНКЦИЯ ПОИСКА АКЦИИ ---
def find_applicable_promotion(
    data: CalculationInput, 
    df_promotions: pd.DataFrame
) -> Optional[Dict[str, Any]]:
    """
    Ищет НАИБОЛЕЕ подходящую акцию с учетом стандартных и "комбо" уровней,
    а также проверяет, разрешено ли применять акцию в текущем месяце.
    """
    # --- БЛОК ИЗМЕНЕНИЙ ---
    # Проверка на "сезонность" акции. Бэкенд - единственный источник правды.
    today = datetime.now()
    # Устанавливаем день на 1 для корректного сравнения месяцев, обнуляем время
    current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # +1 и +2 месяца от текущего с помощью relativedelta
    next_month_start = current_month_start + relativedelta(months=1)
    month_after_next_start = current_month_start + relativedelta(months=2)
    
    allowed_months = [current_month_start, next_month_start, month_after_next_start]

    # Парсим период из запроса пользователя
    # parse_period_string вернет datetime(1900, 1, 1), если не сможет распарсить,
    # что заведомо не попадет в наш разрешенный список. Это безопасно.
    selected_period_date = parse_period_string(data.period).replace(hour=0, minute=0, second=0, microsecond=0)

    # Если выбранный период прейскуранта не входит в разрешенные, то акцию применять нельзя.
    # Это защищает от отправки "хитрых" запросов с фронтенда.
    if selected_period_date not in allowed_months:
        return None # Просто молча не находим акцию
    # --- КОНЕЦ БЛОКА ИЗМЕНЕНИЙ ---

    if df_promotions is None or df_promotions.empty or data.promotion_id is None or data.promotion_id == 'no_promotion':
        return None

    user_active_levels_set = {
        level.level.lower() for level in data.levels if level.accounts > 0
    }
    if not user_active_levels_set:
        return None

    service_lower = data.service.lower()
    
    # 1. Находим ВСЕ варианты для данной акции и периода предоплаты
    candidate_promos = df_promotions[
        (df_promotions['ТП'].str.lower() == service_lower) &
        (df_promotions['Приказ'] == data.promotion_id) &
        (df_promotions['Месяцев'] == data.prepayment_months)
    ]
    
    if candidate_promos.empty:
        return None

    best_match = None
    max_matched_levels = 0

    # 2. Итерируемся по всем вариантам и ищем лучший
    for _, promo_row in candidate_promos.iterrows():
        promo_level_str = promo_row.get('Уровень', '')
        
        required_levels = logic._parse_combo_level(promo_level_str)
        required_levels_lower_set = {level.lower() for level in required_levels}

        if not required_levels_lower_set.issubset(user_active_levels_set):
            continue

        is_combo = len(required_levels) > 1
        if is_combo:
            main_level_in_promo = MAIN_LEVEL_NAME.lower() in required_levels_lower_set
            if main_level_in_promo and (MAIN_LEVEL_NAME.lower() not in user_active_levels_set):
                 continue
        
        # 3. Сравниваем, насколько хорош этот вариант
        current_match_count = len(required_levels_lower_set)
        if current_match_count > max_matched_levels:
            max_matched_levels = current_match_count
            best_match = {
                "details": promo_row.to_dict(),
                "applicable_levels": required_levels
            }
            
    return best_match
# --- ===== КОНЕЦ ЗАМЕНЫ ===== ---


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
        fixation_map_for_json = {key: float(value) for key, value in logic.FIXATION_COEFFICIENT_MAP.items()}
        return templates.TemplateResponse("index.html", {
            "request": request, "services": services, "levels": levels,
            "periods": periods,
            "fixation_map_json": json.dumps(fixation_map_for_json)
        })
    except KeyError as e:
        return templates.TemplateResponse("error.html", {"request": request, "error_message": f"Ошибка в данных: отсутствует столбец: {e}"})

@app.get("/get_levels_for_service/{service_name}")
async def get_levels_for_service(service_name: str):
    if df_prices is None:
        return []
    try:
        filtered_df = df_prices[df_prices['Сервис'] == service_name]
        levels_with_minutes_df = filtered_df[['Уровень', 'Минут']].copy()
        levels_with_minutes_df.dropna(subset=['Уровень'], inplace=True)
        levels_with_minutes_df.drop_duplicates(subset=['Уровень'], keep='first', inplace=True)
        custom_order = ["Эксперт", "Оптимальный", "Оптимальный Плюс", "Минимальный", "Базовый"]
        levels_list = levels_with_minutes_df.to_dict('records')
        def sort_key(level_dict):
            level_name = level_dict['Уровень']
            return (custom_order.index(level_name) if level_name in custom_order else float('inf'), level_name)
        sorted_levels = sorted(levels_list, key=sort_key)
        return sorted_levels
    except Exception as e:
        print(f"Ошибка при получении уровней для сервиса '{service_name}': {e}")
        return []

@app.post("/get_all_promotions_for_selection")
async def get_all_promotions_for_selection(data: PromotionAllRequest):
    if df_promotions is None or df_promotions.empty:
        return {}
    try:
        service_lower = data.service.lower()
        levels_lower = [level.lower() for level in data.levels]
        
        mask = df_promotions.apply(
            lambda row: (row['ТП'].lower() == service_lower) and any(
                level_lower in row['Уровень'].lower().replace(" ", "") 
                for level_lower in levels_lower
            ), 
            axis=1
        )
        filtered_df = df_promotions[mask]

        if filtered_df.empty:
            return {}

        promotions_map = {}
        for promo_name, group in filtered_df.groupby('Приказ'):
            promo_levels = group['Уровень'].unique().tolist()
            
            variants = []
            for _, row in group.drop_duplicates(subset=['Месяцев']).iterrows():
                variants.append({
                    "months": int(row['Месяцев']),
                    "discount_percent": row['Условие1'] * 100,
                    "condition2": str(row['Условие2']) if pd.notna(row['Условие2']) else None
                })
            
            variants.sort(key=lambda x: x['months'])

            promotions_map[promo_name] = {
                "id": promo_name,
                "name": promo_name,
                "applicable_levels": promo_levels,
                "variants": variants
            }
        
        return promotions_map
    except Exception as e:
        print(f"!!! ОШИБКА при поиске всех акций для '{data.service}': {e}")
        return {}

@app.post("/calculate")
async def handle_calculation(data: CalculationInput):
    if df_prices is None: raise HTTPException(status_code=500, detail="Данные прайс-листа не загружены.")
    
    promotion_info = find_applicable_promotion(data, df_promotions)
    
    calculation_result = logic.run_calculation(
        data.dict(), 
        df_prices,
        promotion_info=promotion_info
    )
    
    if calculation_result.get("price_summary") is None:
        return {"error": "Не удалось найти тарифы для указанных позиций."}
    
    context = calculation_result.get("calculation_context", {})
    final_response = {
        "price_summary": calculation_result["price_summary"],
        "totals": { "accounts": context.get("total_users", 0) },
        "calculation_context": context
    }
    return final_response

@app.post("/download_offer")
async def download_offer(data: CalculationInput):
    if df_prices is None: raise HTTPException(status_code=500, detail="Данные прайс-листа не загружены.")
        
    promotion_info = find_applicable_promotion(data, df_promotions)

    calculation_result = logic.run_calculation(
        data.dict(), 
        df_prices,
        promotion_info=promotion_info
    )
    
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