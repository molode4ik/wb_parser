import argparse
from pathlib import Path

from parser import WBParser
from xlsx_generator import XLSXGenerator


DEFAULT_URL = "https://www.wildberries.ru/__internal/u-search/exactmatch/ru/common/v18/search"
DEFAULT_FILTERED_MAX_PRICE = 10000


def build_parser() -> argparse.ArgumentParser:
    arg_parser = argparse.ArgumentParser(
        description="Парсинг товаров Wildberries и сохранение в XLSX."
    )
    arg_parser.add_argument("query", nargs="?", help="Поисковый запрос.")
    arg_parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="URL для запроса к API Wildberries.",
    )
    arg_parser.add_argument(
        "--cookies-path",
        default="wb_cookies.json",
        help="Путь к файлу с сохраненными cookies.",
    )
    arg_parser.add_argument(
        "--search-min-price",
        type=float,
        default=None,
        help="Минимальная цена для полного search-запроса.",
    )
    arg_parser.add_argument(
        "--search-max-price",
        type=float,
        default=None,
        help="Максимальная цена для полного search-запроса.",
    )
    arg_parser.add_argument(
        "--search-rating",
        action="store_true",
        help="Добавлять fRating=1 в полный search-запрос.",
    )
    arg_parser.add_argument(
        "--output",
        default="wb_products.xlsx",
        help="Имя полного XLSX файла.",
    )
    arg_parser.add_argument(
        "--filtered-output",
        default="wb_products_filtered.xlsx",
        help="Имя XLSX файла с фильтрованной выдачей.",
    )
    arg_parser.add_argument(
        "--filtered-min-price",
        type=float,
        default=None,
        help="Минимальная цена для второго search-запроса.",
    )
    arg_parser.add_argument(
        "--filtered-max-price",
        type=float,
        default=DEFAULT_FILTERED_MAX_PRICE,
        help="Максимальная цена для второго search-запроса.",
    )
    arg_parser.add_argument(
        "--filtered-rating",
        action="store_true",
        default=True,
        help="Добавлять fRating=1 во второй search-запрос.",
    )
    arg_parser.add_argument(
        "--no-filtered-rating",
        action="store_false",
        dest="filtered_rating",
        help="Не добавлять fRating=1 во второй search-запрос.",
    )
    return arg_parser


def _resolve_query(args: argparse.Namespace) -> str:
    query = args.query or input("Введите поисковый запрос: ").strip()
    if not query:
        raise SystemExit("Поисковый запрос не указан.")
    return query


def _resolve_outputs(args: argparse.Namespace) -> tuple[str, str]:
    output = args.output
    filtered_output = args.filtered_output

    if not args.query:
        custom_output = input(f"Введите имя полного файла [{args.output}]: ").strip()
        if custom_output:
            output = custom_output

        custom_filtered_output = input(
            f"Введите имя файла с фильтром [{args.filtered_output}]: "
        ).strip()
        if custom_filtered_output:
            filtered_output = custom_filtered_output

    return output, filtered_output


def main() -> None:
    args = build_parser().parse_args()
    query = _resolve_query(args)
    output, filtered_output = _resolve_outputs(args)

    wb_parser = WBParser(
        url=args.url,
        query=query,
        cookies_path=args.cookies_path,
    )

    payload = wb_parser.fetch_all_search_payloads(
        min_price=args.search_min_price,
        max_price=args.search_max_price,
        rating=args.search_rating,
    )
    products = wb_parser.extract_products(payload)

    filtered_products = wb_parser.filter_products(
        min_price=args.filtered_min_price,
        max_price=args.filtered_max_price,
        rating=args.filtered_rating,
    )

    full_path = XLSXGenerator(output_path=output).generate(products)
    filtered_path = XLSXGenerator(output_path=filtered_output).generate(
        filtered_products
    )

    print(f"Found {payload.get('total', len(products))} products in full search")
    print(f"Saved {len(products)} products to {Path(full_path)}")
    print(f"Saved {len(filtered_products)} filtered products to {Path(filtered_path)}")


if __name__ == "__main__":
    main()
