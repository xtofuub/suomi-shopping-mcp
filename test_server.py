import asyncio
import json
import sys

sys.path.insert(0, ".")

from server import (
    find_best_prices,
    find_pc_part_prices,
    get_hinta_product_details,
    get_shopping_links,
    search_hinta_products,
    search_products,
    search_tori_listings,
)


async def test():
    print("=== Testing general best-price search ===")
    general = json.loads(await find_best_prices("iPhone 15", max_results_per_source=3))
    print(f"Found {len(general['results_sorted_by_price'])} combined results")
    if general["summary"]["cheapest_overall"]:
        item = general["summary"]["cheapest_overall"]
        print(f"  Cheapest: {item['source']} - {item['name']} - {item.get('price')} EUR")

    print()
    print("=== Testing Hinta.fi search ===")
    hinta = json.loads(await search_hinta_products("RTX 4070", limit=3))
    print(f"Found {hinta['total_results']} Hinta.fi results")
    if hinta["products"]:
        print(f"  First: {hinta['products'][0]['name']} - {hinta['products'][0]['price']} EUR")

    print()
    print("=== Testing Tori.fi search ===")
    tori = json.loads(await search_tori_listings("office chair", limit=3))
    print(f"Found {len(tori['listings'])} Tori.fi listings")
    if tori["listings"]:
        print(f"  First: {tori['listings'][0]['name']} - {tori['listings'][0]['price']} EUR")

    print()
    print("=== Testing PC compatibility wrapper ===")
    pc = json.loads(await find_pc_part_prices("RTX 4070", max_results_per_source=3))
    print(f"Category: {pc['category']}; results: {len(pc['results_sorted_by_price'])}")

    print()
    print("=== Testing product details compatibility ===")
    details = json.loads(await get_hinta_product_details("3236886"))
    print(f"Product: {details['name']}")
    print(f"Price: {details['current_price']}")
    print(f"Offers: {len(details['offers'])}")

    print()
    print("=== Testing old search alias ===")
    alias = json.loads(await search_products("RTX 4070"))
    print(f"Alias returned {len(alias['products'])} products")

    print()
    print("=== Testing shopping links ===")
    links = json.loads(await get_shopping_links("desk lamp"))
    print(", ".join(sorted(links["links"].keys())))


if __name__ == "__main__":
    asyncio.run(test())
