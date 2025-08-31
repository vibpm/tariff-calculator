# document_generator.py

from docxtpl import DocxTemplate
from typing import Dict, Any
import io

def create_offer_document(context: Dict[str, Any]) -> io.BytesIO:
    """
    Генерирует коммерческое предложение в формате .docx на основе шаблона и данных.

    Args:
        context: Словарь с данными для заполнения шаблона.

    Returns:
        Объект io.BytesIO, содержащий сгенерированный документ в памяти.
    """
    try:
        # Убедись, что у тебя есть папка templates_docx и в ней лежит твой шаблон
        # Если твой файл называется offer_template.dotx, то все верно
        doc = DocxTemplate("templates_docx/offer_template.docx")

        doc.render(context)

        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        
        return file_stream

    except Exception as e:
        print(f"!!! ОШИБКА при генерации DOCX: {e}")
        return None