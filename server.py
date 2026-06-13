"""
Finland Shopping MCP Server
===========================

MCP tools for shopping in Finland from:
  - Hinta.fi: new retail price comparison
  - Tori.fi: used marketplace listings
  - Huuto.net: search-link fallback, because direct scraping commonly hits bot protection

The tools are general-purpose. They can search for PC parts, phones,
furniture, tools, appliances, hobby gear, or whatever else the user asks for.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP


logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

mcp = FastMCP(
    "finland-shopping",
    instructions=(
        "Search Finnish shopping prices from Hinta.fi retail listings and "
        "Tori.fi used marketplace listings. Use find_best_prices for a "
        "combined best-price view across new and used options."
    ),
)

HINTA_BASE_URL = "https://hinta.fi"
TORI_BASE_URL = "https://www.tori.fi"
HUUTO_BASE_URL = "https://www.huuto.net"

TORI_CATEGORY_FILTERS = {
    "all": None,
    "pc_components": "2.93.3215.8368",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.8",
}


async def _fetch(url: str) -> BeautifulSoup:
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _parse_price(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value)
    text = text.replace("\xa0", " ").replace("EUR", "")
    text = re.sub(r"\s+", "", text)
    text = text.replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _absolute_url(base: str, href: str | None) -> str | None:
    if not href:
        return None
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return f"{base}{href if href.startswith('/') else '/' + href}"


def _extract_product_jsonld(soup: BeautifulSoup) -> dict[str, Any] | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "Product":
                return item
    return None


def _extract_tori_items(soup: BeautifulSoup) -> list[dict[str, Any]]:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict) or data.get("@type") != "CollectionPage":
            continue

        item_list = data.get("mainEntity", {}).get("itemListElement", [])
        listings: list[dict[str, Any]] = []
        for entry in item_list:
            product = entry.get("item", {}) if isinstance(entry, dict) else {}
            offer = product.get("offers", {}) if isinstance(product, dict) else {}
            name = product.get("name")
            url = product.get("url")
            price = _parse_price(offer.get("price"))
            if not name or not url:
                continue
            listings.append(
                {
                    "source": "tori.fi",
                    "condition": "used",
                    "name": name,
                    "description": product.get("description"),
                    "price": price,
                    "price_text": f"{price:.2f} EUR" if price is not None else None,
                    "currency": offer.get("priceCurrency", "EUR"),
                    "availability": str(offer.get("availability", "")).rsplit("/", 1)[-1] or None,
                    "listing_type": "wanted" if name.lower().startswith(("o:", "ostetaan")) else "for_sale",
                    "image": product.get("image"),
                    "url": url,
                }
            )
        return listings
    return []


async def _search_hinta(query: str, page: int = 1, limit: int = 20) -> dict[str, Any]:
    url = f"{HINTA_BASE_URL}/haku?{urlencode({'q': query, 'p': page})}"
    soup = await _fetch(url)

    products: list[dict[str, Any]] = []
    for row in soup.select("tr.hv-prt-tr")[: max(1, limit)]:
        name_el = row.select_one("strong.hv--name")
        group_el = row.select_one(".hv--group")
        features_el = row.select_one(".hv--features")
        price_el = row.select_one("td.hv--price .hv--v")
        total_el = row.select_one("td.hv--price-total .hv--v")
        delivery_el = row.select_one("td.hv--delivery-days")
        stores_el = row.select_one("td.hv--store-count")
        link_el = row.select_one("a.hv-prt_product-a")

        price_text = price_el.get_text(" ", strip=True) if price_el else None
        total_text = total_el.get_text(" ", strip=True) if total_el else None
        products.append(
            {
                "source": "hinta.fi",
                "condition": "new",
                "id": row.get("data-id", ""),
                "name": name_el.get_text(" ", strip=True) if name_el else "Unknown",
                "category": group_el.get_text(" ", strip=True) if group_el else None,
                "features": features_el.get_text(" ", strip=True) if features_el else None,
                "price": _parse_price(price_text),
                "price_text": price_text,
                "price_with_delivery": _parse_price(total_text),
                "price_with_delivery_text": total_text,
                "delivery_days": delivery_el.get_text(" ", strip=True) if delivery_el else None,
                "store_count": stores_el.get_text(" ", strip=True) if stores_el else None,
                "url": _absolute_url(HINTA_BASE_URL, link_el.get("href") if link_el else None),
            }
        )

    total_el = soup.select_one(".hv-bar-i.hv--text strong")
    return {
        "source": "hinta.fi",
        "query": query,
        "page": page,
        "total_results": total_el.get_text(" ", strip=True) if total_el else "unknown",
        "url": url,
        "products": products,
    }


async def _search_tori(
    query: str,
    limit: int = 20,
    category: str = "all",
    min_price: float | None = None,
    max_price: float | None = None,
) -> dict[str, Any]:
    params: dict[str, str] = {"q": query}
    category_id = TORI_CATEGORY_FILTERS.get(category, TORI_CATEGORY_FILTERS["all"])
    if category_id:
        params["product_category"] = category_id
    url = f"{TORI_BASE_URL}/recommerce/forsale/search?{urlencode(params)}"
    soup = await _fetch(url)

    listings = _extract_tori_items(soup)
    if min_price is not None:
        listings = [item for item in listings if item["price"] is None or item["price"] >= min_price]
    if max_price is not None:
        listings = [item for item in listings if item["price"] is None or item["price"] <= max_price]

    title = soup.select_one("title")
    return {
        "source": "tori.fi",
        "query": query,
        "category": category,
        "title": title.get_text(" ", strip=True) if title else None,
        "url": url,
        "listings": listings[: max(1, limit)],
    }


def _huuto_search_link(query: str) -> dict[str, Any]:
    url = f"{HUUTO_BASE_URL}/haku?{urlencode({'words': query})}"
    return {
        "source": "huuto.net",
        "query": query,
        "url": url,
        "note": (
            "Huuto.net often blocks non-browser scraping with bot protection, "
            "so this MCP returns a direct search URL instead of unreliable parsed prices."
        ),
    }


def _sort_price_key(item: dict[str, Any]) -> tuple[int, float]:
    price = item.get("price_with_delivery")
    if price is None:
        price = item.get("price")
    return (price is None, float(price or 0))


@mcp.tool()
async def search_hinta_products(query: str, page: int = 1, limit: int = 20) -> str:
    """Search new retail product prices on Hinta.fi."""
    return _json(await _search_hinta(query=query, page=page, limit=limit))


@mcp.tool()
async def search_tori_listings(
    query: str,
    limit: int = 20,
    category: str = "all",
    min_price: float | None = None,
    max_price: float | None = None,
) -> str:
    """Search used marketplace listings on Tori.fi.

    Args:
        query: What to search for.
        limit: Maximum listings to return.
        category: "all" for broad search or "pc_components" for Tori's PC component category.
        min_price: Optional minimum listing price in EUR.
        max_price: Optional maximum listing price in EUR.
    """
    return _json(
        await _search_tori(
            query=query,
            limit=limit,
            category=category,
            min_price=min_price,
            max_price=max_price,
        )
    )


@mcp.tool()
async def get_huuto_search_link(query: str) -> str:
    """Return a Huuto.net search URL for manual checking."""
    return _json(_huuto_search_link(query))


@mcp.tool()
async def find_best_prices(
    query: str,
    include_used: bool = True,
    max_results_per_source: int = 10,
    max_price: float | None = None,
    category: str = "all",
) -> str:
    """Compare Finnish prices for anything across Hinta.fi and Tori.fi.

    Use this when the user asks for a good price, cheapest listing, or whether
    a deal looks fair in Finland. Set category to "pc_components" when the user
    specifically asks for computer components.
    """
    hinta = await _search_hinta(query=query, limit=max_results_per_source)
    tori = (
        await _search_tori(query=query, limit=max_results_per_source, max_price=max_price, category=category)
        if include_used
        else {"listings": [], "url": None}
    )

    candidates: list[dict[str, Any]] = []
    for product in hinta["products"]:
        price = product.get("price_with_delivery") or product.get("price")
        if max_price is None or price is None or price <= max_price:
            candidates.append(product)
    candidates.extend(tori["listings"])
    candidates = [item for item in candidates if item.get("listing_type") != "wanted"]
    candidates.sort(key=_sort_price_key)

    cheapest_new = next((item for item in candidates if item["source"] == "hinta.fi"), None)
    cheapest_used = next((item for item in candidates if item["source"] == "tori.fi"), None)

    summary = {
        "cheapest_overall": candidates[0] if candidates else None,
        "cheapest_new": cheapest_new,
        "cheapest_used": cheapest_used,
        "used_savings_vs_new": None,
    }
    if cheapest_new and cheapest_used and cheapest_new.get("price") and cheapest_used.get("price"):
        summary["used_savings_vs_new"] = round(cheapest_new["price"] - cheapest_used["price"], 2)

    return _json(
        {
            "query": query,
            "category": category,
            "summary": summary,
            "results_sorted_by_price": candidates,
            "sources": {
                "hinta": {"url": hinta["url"], "total_results": hinta["total_results"]},
                "tori": {"url": tori.get("url")} if include_used else None,
                "huuto": _huuto_search_link(query),
            },
        }
    )


@mcp.tool()
async def find_pc_part_prices(
    query: str,
    include_used: bool = True,
    max_results_per_source: int = 10,
    max_price: float | None = None,
) -> str:
    """Compatibility helper for PC-part searches.

    This is a convenience wrapper around find_best_prices with Tori limited to
    the PC components category.
    """
    return await find_best_prices(
        query=query,
        include_used=include_used,
        max_results_per_source=max_results_per_source,
        max_price=max_price,
        category="pc_components",
    )


@mcp.tool()
async def get_shopping_links(query: str) -> str:
    """Return direct Finnish shopping search links for manual checking."""
    links = {
        "hinta": f"{HINTA_BASE_URL}/haku?{urlencode({'q': query})}",
        "tori": f"{TORI_BASE_URL}/recommerce/forsale/search?{urlencode({'q': query})}",
        "huuto": _huuto_search_link(query)["url"],
    }
    return _json({"query": query, "links": links, "note": "Use these links for manual verification."})


@mcp.tool()
async def get_hinta_product_details(product_id: str) -> str:
    """Get detailed Hinta.fi product information including store offers."""
    soup = await _fetch(f"{HINTA_BASE_URL}/{product_id}")
    jsonld = _extract_product_jsonld(soup)
    title = soup.select_one("h1.hv-content-hd-h")

    features: dict[str, str] = {}
    for dt in soup.select("dl.hv-prh_features dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            features[dt.get_text(" ", strip=True)] = dd.get_text(" ", strip=True)

    current_price_el = soup.select_one(".hv-prh_price")
    old_price_el = soup.select_one(".hv-prh_price-old")
    change_el = soup.select_one(".hv-prh_price-change")

    offers: list[dict[str, Any]] = []
    if jsonld and isinstance(jsonld.get("offers"), dict):
        for offer in jsonld["offers"].get("offers", []):
            offers.append(
                {
                    "store": offer.get("seller", {}).get("name", "Unknown"),
                    "product_name": offer.get("name", ""),
                    "price": _parse_price(offer.get("price")),
                    "currency": offer.get("priceCurrency", "EUR"),
                }
            )

    for row in soup.select("tr.hv-oft-tr"):
        store_el = row.select_one("th.hv--store")
        product_el = row.select_one("td.hv--product")
        price_cell = row.select_one("td.hv--price strong")
        total_cell = row.select_one("td.hv--price-total .hv--v")
        delivery_cell = row.select_one("td.hv--delivery-time")
        store_name = store_el.get_text(" ", strip=True) if store_el else "Unknown"
        if any(o["store"] == store_name for o in offers):
            continue
        offers.append(
            {
                "store": store_name,
                "product_name": product_el.get_text(" ", strip=True) if product_el else "",
                "price": _parse_price(price_cell.get_text(" ", strip=True)) if price_cell else None,
                "price_with_delivery": _parse_price(total_cell.get_text(" ", strip=True)) if total_cell else None,
                "delivery_time": delivery_cell.get_text(" ", strip=True) if delivery_cell else None,
            }
        )

    return _json(
        {
            "source": "hinta.fi",
            "id": product_id,
            "name": title.get_text(" ", strip=True) if title else "Unknown",
            "url": f"{HINTA_BASE_URL}/{product_id}",
            "current_price": current_price_el.get_text(" ", strip=True) if current_price_el else None,
            "previous_price_30d": old_price_el.get_text(" ", strip=True) if old_price_el else None,
            "price_change": change_el.get_text(" ", strip=True) if change_el else None,
            "features": features,
            "offers": sorted(offers, key=_sort_price_key),
            "brand": jsonld.get("brand", {}).get("name") if jsonld else None,
            "description": jsonld.get("description") if jsonld else None,
            "image": jsonld.get("image") if jsonld else None,
        }
    )


# Backward-compatible aliases from the original Hinta-only MCP.
@mcp.tool()
async def search_products(query: str, page: int = 1) -> str:
    """Compatibility alias for search_hinta_products."""
    return await search_hinta_products(query=query, page=page)


@mcp.tool()
async def get_product_details(product_id: str) -> str:
    """Compatibility alias for get_hinta_product_details."""
    return await get_hinta_product_details(product_id=product_id)


@mcp.tool()
async def get_deals(page: int = 1) -> str:
    """Get current Hinta.fi deals."""
    url = f"{HINTA_BASE_URL}/tarjoukset?{urlencode({'l': 1, 'page': page})}"
    soup = await _fetch(url)
    products = []
    for row in soup.select("tr.hv-prt-tr"):
        name_el = row.select_one("strong.hv--name")
        price_el = row.select_one("td.hv--price .hv--v")
        link_el = row.select_one("a.hv-prt_product-a")
        price_text = price_el.get_text(" ", strip=True) if price_el else None
        products.append(
            {
                "source": "hinta.fi",
                "condition": "new",
                "id": row.get("data-id", ""),
                "name": name_el.get_text(" ", strip=True) if name_el else "Unknown",
                "price": _parse_price(price_text),
                "price_text": price_text,
                "url": _absolute_url(HINTA_BASE_URL, link_el.get("href") if link_el else None),
            }
        )
    return _json({"source": "hinta.fi", "page": page, "url": url, "deals": products, "count": len(products)})


@mcp.tool()
async def get_categories() -> str:
    """Get Hinta.fi category links."""
    soup = await _fetch(f"{HINTA_BASE_URL}/ryhmat")
    categories = []
    for link in soup.select("a[href^='/g']"):
        name = link.get_text(" ", strip=True)
        href = link.get("href")
        if name and href:
            categories.append({"name": name, "url": _absolute_url(HINTA_BASE_URL, href)})
    return _json({"source": "hinta.fi", "categories": categories, "count": len(categories)})


@mcp.tool()
async def get_category_products(category_url: str, page: int = 1) -> str:
    """Get Hinta.fi products in a category URL."""
    separator = "&" if "?" in category_url else "?"
    url = f"{category_url}{separator}{urlencode({'p': page})}"
    soup = await _fetch(url)
    title_el = soup.select_one("h1.hv-content-hd-h")
    results = []
    for row in soup.select("tr.hv-prt-tr"):
        name_el = row.select_one("strong.hv--name")
        price_el = row.select_one("td.hv--price .hv--v")
        link_el = row.select_one("a.hv-prt_product-a")
        price_text = price_el.get_text(" ", strip=True) if price_el else None
        results.append(
            {
                "source": "hinta.fi",
                "condition": "new",
                "id": row.get("data-id", ""),
                "name": name_el.get_text(" ", strip=True) if name_el else "Unknown",
                "price": _parse_price(price_text),
                "price_text": price_text,
                "url": _absolute_url(HINTA_BASE_URL, link_el.get("href") if link_el else None),
            }
        )
    return _json(
        {
            "source": "hinta.fi",
            "category": title_el.get_text(" ", strip=True) if title_el else "Unknown",
            "page": page,
            "url": url,
            "products": results,
        }
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
