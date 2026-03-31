import json
from pathlib import Path
from typing import Any

from openpyxl import Workbook


class XLSXGenerator:
    def __init__(self, output_path: str) -> None:
        self.output_path = Path(output_path)

    def generate(self, products: list[dict[str, Any]]) -> Path:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Products"

        headers = [
            "Ссылка на товар",
            "Артикул",
            "Название",
            "Цена",
            "Описание",
            "Ссылки на изображения",
            "Все характеристики",
            "Название селлера",
            "Ссылка на селлера",
            "Размеры товара",
            "Остатки по товару (число)",
            "Рейтинг",
            "Количество отзывов",
        ]
        worksheet.append(headers)

        for product in products:
            worksheet.append(
                [
                    product.get("url"),
                    product.get("article"),
                    product.get("name"),
                    product.get("price"),
                    product.get("description"),
                    product.get("image_urls"),
                    self._serialize(product.get("characteristics")),
                    product.get("seller_name"),
                    product.get("seller_url"),
                    product.get("sizes"),
                    product.get("stock"),
                    product.get("rating"),
                    product.get("feedbacks"),
                ]
            )

        self._set_column_widths(worksheet)
        workbook.save(self.output_path)
        return self.output_path

    @staticmethod
    def _serialize(value: Any) -> str | None:
        if value in (None, "", [], {}):
            return None
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    @staticmethod
    def _set_column_widths(worksheet) -> None:
        widths = {
            "A": 45,
            "B": 14,
            "C": 35,
            "D": 12,
            "E": 60,
            "F": 70,
            "G": 80,
            "H": 24,
            "I": 35,
            "J": 24,
            "K": 18,
            "L": 10,
            "M": 18,
        }

        for column, width in widths.items():
            worksheet.column_dimensions[column].width = width
