# Парсер для WB
Реализовано при помощи связки Selenium + requests, где первый нужен только для получения куки, так как у WB есть антибот система, проверяющая наличие JS. по этой же причине при первом запуске октрывается Chrome без headless, после куки сохраняются и используются пока не умрут.

## Запуск
### Создание окружения и установка зависимостей
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
### Варианты запуска
  - python app.py "пальто из натуральной шерсти"
  - python app.py "пальто из натуральной шерсти" --filtered-max-price 8000
  - python app.py "пальто из натуральной шерсти" --no-filtered-rating
  - python app.py "пальто из натуральной шерсти" --search-max-price 15000
