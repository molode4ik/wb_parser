import json
import math
import time
from pathlib import Path
from typing import Any

import requests


class WBParser:
    def __init__(
        self,
        url: str,
        query: str,
        cookies_path: str = "wb_cookies.json",
    ) -> None:
        self.url = url
        self.query = query
        self.cookies_path = Path(cookies_path)
        self.session = requests.Session()
        self.cookies: dict[str, str] = {}
        self.cookies_checked = False
        self.params = {
            "ab_testing": "false",
            "appType": 1,
            "curr": "rub",
            "dest": "-1257786",
            "hide_vflags": 4294967296,
            "inheritFilters": "false",
            "lang": "ru",
            "page": 1,
            "query": query,
            "resultset": "catalog",
            "sort": "popular",
            "spp": 30,
            "suppressSpellcheck": "false",
        }
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.wildberries.ru/",
            "Origin": "https://www.wildberries.ru",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def _requires_cookies(self, url: str) -> bool:
        return "__internal/" in url

    def _load_cached_auth(self) -> bool:
        if not self.cookies_path.exists():
            return False

        try:
            data = json.loads(self.cookies_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False

        cookies = data.get("cookies")
        user_agent = data.get("user_agent")

        if not isinstance(cookies, dict) or not cookies:
            return False

        if isinstance(user_agent, str) and user_agent:
            self.headers["User-Agent"] = user_agent

        self.cookies = {str(key): str(value) for key, value in cookies.items()}
        return True

    def _save_auth(self, user_agent: str, cookies: dict[str, str]) -> None:
        payload = {
            "saved_at": int(time.time()),
            "user_agent": user_agent,
            "cookies": cookies,
        }
        self.cookies_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _probe_search_cookies(self) -> bool:
        if not self.cookies:
            return False

        response = self.session.get(
            self.url,
            params=self.params,
            headers=self.headers,
            cookies=self.cookies,
            timeout=20,
        )
        if response.status_code != 200:
            return False

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            return False

        return isinstance(payload.get("products"), list)

    def _refresh_auth_with_browser(self) -> None:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        driver = webdriver.Chrome(options=options)
        driver.execute_script(
            """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        })
        """
        )

        try:
            driver.get("https://www.wildberries.ru/")
            time.sleep(10)
            user_agent = driver.execute_script("return navigator.userAgent;")
            cookies = driver.get_cookies()
        finally:
            driver.quit()

        cookies_dict = {
            cookie["name"]: cookie["value"]
            for cookie in cookies
            if cookie.get("name") and cookie.get("value")
        }

        self.headers["User-Agent"] = user_agent
        self.cookies = cookies_dict
        self._save_auth(user_agent=user_agent, cookies=cookies_dict)

    def _ensure_auth(self) -> None:
        if self.cookies_checked:
            return

        if not self._load_cached_auth() or not self._probe_search_cookies():
            self._refresh_auth_with_browser()
            if not self._probe_search_cookies():
                raise RuntimeError("Не удалось получить рабочие cookies для Wildberries.")

        self.cookies_checked = True

    def get(
        self,
        url: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> requests.Response:
        target_url = url or self.url
        target_params = self.params if params is None else params

        request_kwargs: dict[str, Any] = {
            "url": target_url,
            "params": target_params,
            "headers": self.headers,
            "timeout": 20,
        }

        if self._requires_cookies(target_url):
            self._ensure_auth()
            request_kwargs["cookies"] = self.cookies

        return self.session.get(**request_kwargs)

    def fetch(
        self,
        url: str | None = None,
        params: dict[str, Any] | None = None,
        retry_delay: int = 1,
    ) -> dict[str, Any]:
        response = self.get(url=url, params=params)

        while response.status_code != 200:
            time.sleep(retry_delay)
            response = self.get(url=url, params=params)

        return json.loads(response.text)

    def _build_search_params(
        self,
        page: int,
        min_price: float | None = None,
        max_price: float | None = None,
        rating: bool = False,
    ) -> dict[str, Any]:
        params = dict(self.params)
        params["page"] = page

        if min_price is not None or max_price is not None:
            lower = 0 if min_price is None else int(min_price * 100)
            upper = "" if max_price is None else int(max_price * 100)
            params["priceU"] = f"{lower};{upper}"

        if rating:
            params["fRating"] = 1

        return params

    def fetch_search_payload(
        self,
        page: int = 1,
        min_price: float | None = None,
        max_price: float | None = None,
        rating: bool = False,
    ) -> dict[str, Any]:
        params = self._build_search_params(
            page=page,
            min_price=min_price,
            max_price=max_price,
            rating=rating,
        )
        return self.fetch(params=params)

    def fetch_all_search_payloads(
        self,
        min_price: float | None = None,
        max_price: float | None = None,
        rating: bool = False,
    ) -> dict[str, Any]:
        first_payload = self.fetch_search_payload(
            page=1,
            min_price=min_price,
            max_price=max_price,
            rating=rating,
        )
        products = list(first_payload.get("products", []))
        total = first_payload.get("total") or len(products)

        if not products or len(products) >= total:
            aggregated = dict(first_payload)
            aggregated["products"] = products
            aggregated["total"] = total
            return aggregated

        per_page = len(products)
        pages_count = math.ceil(total / per_page)
        seen_ids = {product.get("id") for product in products}

        for page in range(2, pages_count + 1):
            print(f"Loading search page {page}/{pages_count}", end="\r")
            payload = self.fetch_search_payload(
                page=page,
                min_price=min_price,
                max_price=max_price,
                rating=rating,
            )
            for product in payload.get("products", []):
                product_id = product.get("id")
                if product_id in seen_ids:
                    continue
                seen_ids.add(product_id)
                products.append(product)

        print(f"Loaded search pages: {pages_count}/{pages_count}".ljust(40))
        aggregated = dict(first_payload)
        aggregated["products"] = products
        aggregated["total"] = total
        return aggregated

    @staticmethod
    def _print_progress(current: int, total: int, prefix: str) -> None:
        if total <= 0:
            return

        bar_length = 24
        filled = int(bar_length * current / total)
        bar = "#" * filled + "-" * (bar_length - filled)
        print(f"{prefix} [{bar}] {current}/{total}", end="\r")

    @staticmethod
    def _convert_price(value: int | float | None) -> float | None:
        if value is None:
            return None
        return round(value / 100, 2)

    @staticmethod
    def _build_product_url(product_id: str) -> str:
        return f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx"

    @staticmethod
    def _build_card_url(product_id: str) -> str:
        return (
            "https://www.wildberries.ru/__internal/u-card/cards/v4/detail"
            f"?appType=1&curr=rub&dest=-1257786&spp=30"
            f"&hide_vflags=4294967296&ab_testing=false&lang=ru&nm={product_id}"
        )

    @staticmethod
    def _build_photo_urls(product_id: str, photo_count: int | None) -> list[str]:
        if not photo_count:
            return []

        base = (
            f"https://basket-12.wbbasket.ru/vol{product_id[:4]}"
            f"/part{product_id[:6]}/{product_id}/images/c516x688"
        )
        return [f"{base}/{index}.webp" for index in range(1, photo_count + 1)]

    @staticmethod
    def _build_seller_url(supplier_id: int | None) -> str | None:
        if supplier_id is None:
            return None
        return f"https://www.wildberries.ru/seller/{supplier_id}"

    @staticmethod
    def _extract_products(payload: dict[str, Any]) -> list[dict[str, Any]]:
        products = payload.get("products")
        if products is None:
            products = payload.get("data", {}).get("products", [])
        return products

    @staticmethod
    def _extract_card_product(payload: dict[str, Any]) -> dict[str, Any]:
        products = payload.get("products")
        if isinstance(products, list) and products:
            first_product = products[0]
            if isinstance(first_product, dict):
                return first_product
        return payload

    @staticmethod
    def _join_sizes(
        search_sizes: list[dict[str, Any]],
        card_product: dict[str, Any],
    ) -> str | None:
        values: list[str] = []

        for size in search_sizes:
            size_name = size.get("name") or size.get("origName")
            if size_name:
                normalized = str(size_name)
                if normalized not in values:
                    values.append(normalized)

        for size in card_product.get("sizes", []):
            size_name = size.get("name") or size.get("origName")
            if size_name:
                normalized = str(size_name)
                if normalized not in values:
                    values.append(normalized)

        sizes_table = card_product.get("sizes_table")
        if isinstance(sizes_table, dict):
            for item in sizes_table.get("values", []):
                tech_size = item.get("tech_size")
                if tech_size:
                    normalized = str(tech_size)
                    if normalized not in values:
                        values.append(normalized)

        if not values:
            return None
        return ", ".join(values)

    @staticmethod
    def _get_price_info(product: dict[str, Any]) -> dict[str, Any]:
        for size in product.get("sizes", []):
            price_info = size.get("price")
            if isinstance(price_info, dict) and price_info:
                return price_info
        return {}

    def filter_products(
        self,
        max_price: float | None = None,
        rating: bool = False,
        min_price: float | None = None,
    ) -> list[dict[str, Any]]:
        payload = self.fetch_all_search_payloads(
            min_price=min_price,
            max_price=max_price,
            rating=rating,
        )
        return self.extract_products(payload)

    def extract_products(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        products = self._extract_products(payload)
        result: list[dict[str, Any]] = []
        total_products = len(products)

        for index, product in enumerate(products, start=1):
            product_id = str(product.get("id"))
            card_payload = self.fetch(url=self._build_card_url(product_id))
            card_product = self._extract_card_product(card_payload)

            price_info = self._get_price_info(card_product) or self._get_price_info(product)
            photo_count = card_product.get("pics") or product.get("pics")

            result.append(
                {
                    "url": self._build_product_url(product_id),
                    "article": product_id,
                    "name": card_product.get("name") or product.get("name"),
                    "price": self._convert_price(price_info.get("product"))
                    or self._convert_price(price_info.get("basic")),
                    "description": card_product.get("description"),
                    "image_urls": ", ".join(
                        self._build_photo_urls(product_id, photo_count)
                    )
                    or None,
                    "characteristics": product.get("sizes"),
                    "seller_name": card_product.get("supplier") or product.get("supplier"),
                    "seller_url": self._build_seller_url(
                        card_product.get("supplierId") or product.get("supplierId")
                    ),
                    "sizes": self._join_sizes(product.get("sizes", []), card_product),
                    "stock": card_product.get("totalQuantity") or product.get("totalQuantity"),
                    "rating": card_product.get("reviewRating") or product.get("reviewRating"),
                    "feedbacks": card_product.get("feedbacks") or product.get("feedbacks"),
                }
            )
            self._print_progress(index, total_products, "Processing products")

        if total_products:
            print(f"Processing products [{'#' * 24}] {total_products}/{total_products}")
        return result


if __name__ == "__main__":
    parser = WBParser(
        url="https://www.wildberries.ru/__internal/u-search/exactmatch/ru/common/v18/search",
        query="пальто из натуральной шерсти",
    )
    print(parser.extract_products(parser.fetch_all_search_payloads()))
