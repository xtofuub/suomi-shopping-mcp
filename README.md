# Finland Shopping MCP

An MCP server that helps an AI assistant shop in Finland by checking live prices and listings from Finnish marketplaces.

It is not limited to PC parts. You can ask for phones, furniture, appliances, tools, bikes, monitors, clothes, game consoles, cameras, computer parts, or almost anything else.

## What It Searches

| Source | Best for | How this MCP uses it |
| --- | --- | --- |
| [Hinta.fi](https://hinta.fi) | New products from Finnish retailers | Scrapes live search results and product offer pages |
| [Tori.fi](https://www.tori.fi) | Used/local marketplace listings | Scrapes public listing search metadata |
| [Huuto.net](https://www.huuto.net) | Auctions and second-hand listings | Returns direct search links, because direct scraping is often blocked by bot protection |

## Installation

```powershell
git clone https://github.com/xtofuub/suomi-shopping-mcp.git
cd suomi-shopping-mcp
python -m pip install -r requirements.txt
```

## Running Manually

```powershell
python server.py
```

The server uses MCP stdio transport. In normal use, your AI client starts it automatically.

## AI Client Configuration

Add this to a Claude Desktop, Cursor, VS Code, or other MCP-compatible client config:

```json
{
  "mcpServers": {
    "finland-shopping": {
      "command": "python",
      "args": ["C:\\path\\to\\suomi-shopping-mcp\\server.py"]
    }
  }
}
```

An example file is included at:

```text
mcp-config.example.json
```

## Tools

### `find_best_prices`

Combined new-and-used price search across Hinta.fi and Tori.fi.

Use this for questions like:

- `Find the best price for an iPhone 15 in Finland`
- `Is 250 euros good for a used Nintendo Switch OLED?`
- `Find a cheap office chair near Finnish used-market prices`
- `Compare new and used prices for a 4K monitor`

Arguments:

| Argument | Default | Description |
| --- | --- | --- |
| `query` | required | Search phrase |
| `include_used` | `true` | Include Tori.fi used listings |
| `max_results_per_source` | `10` | Limit per source |
| `max_price` | `null` | Optional EUR ceiling |
| `category` | `"all"` | Use `"all"` normally, or `"pc_components"` for Tori's PC component category |

### `search_hinta_products`

Search Hinta.fi retail products.

Good for checking new-product prices, availability, store counts, and product pages.

### `get_hinta_product_details`

Fetch a Hinta.fi product page by product ID and return store offers.

Example:

```text
get_hinta_product_details(product_id="3236886")
```

### `search_tori_listings`

Search Tori.fi used listings.

Arguments:

| Argument | Default | Description |
| --- | --- | --- |
| `query` | required | Search phrase |
| `limit` | `20` | Maximum listings |
| `category` | `"all"` | `"all"` or `"pc_components"` |
| `min_price` | `null` | Optional minimum EUR price |
| `max_price` | `null` | Optional maximum EUR price |

### `get_huuto_search_link`

Returns a Huuto.net search URL for manual checking.

Huuto.net commonly blocks simple non-browser HTTP scraping, so this project intentionally does not fake unreliable parsed prices from it.

### `get_shopping_links`

Returns direct Hinta.fi, Tori.fi, and Huuto.net search links for a query.

### Compatibility Tools

These tool names remain available from the earlier Hinta/PC-part version:

- `find_pc_part_prices`
- `search_products`
- `get_product_details`
- `get_deals`
- `get_categories`
- `get_category_products`

## Example Prompts

```text
Find the best price for AirPods Pro 2 in Finland.
```

```text
Is 400 euros a good used price for an RTX 4070 Super?
```

```text
Find a washing machine under 250 euros, used is okay.
```

```text
Compare new and used prices for a Herman Miller Aeron.
```

```text
Build me a good gaming PC for 1000 euros using Finnish prices.
```

## Output Shape

`find_best_prices` returns:

- `summary.cheapest_overall`
- `summary.cheapest_new`
- `summary.cheapest_used`
- `summary.used_savings_vs_new`
- `results_sorted_by_price`
- source URLs for manual verification

Prices are normalized to numeric EUR values when possible, with original listing text preserved where useful.

## Limitations

- Marketplace HTML can change. If parsing breaks, update selectors in `server.py`.
- Used listings need human judgment. Check seller reputation, location, warranty, exact model, photos, pickup/shipping safety, and whether the listing is actually `for sale` rather than `wanted`.
- Hinta.fi and Tori.fi data is fetched live, so results can change between calls.
- Huuto.net is link-only in this MCP because bot protection makes direct scraping unreliable.

## Development

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Compile check:

```powershell
python -m py_compile server.py
```

Smoke test:

```powershell
python test_server.py
```

## License

MIT
