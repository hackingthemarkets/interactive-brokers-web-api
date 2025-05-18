import os
import time
import httpx
from fastapi import FastAPI, Request, Query, Form, Body, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

BASE_API_URL = "https://localhost:5055/v1/api"
ACCOUNT_ID = os.environ.get('IBKR_ACCOUNT_ID', '')

app = FastAPI()

mcp = FastMCP.from_fastapi(app, name="IBKR API MCP Server")

# Helper for ctime filter
def timectime(s):
    return time.ctime(s/1000)

# Models
class OrderRequest(BaseModel):
    contract_id: int
    price: float
    quantity: int
    side: str

class WatchlistCreateRequest(BaseModel):
    name: str
    symbols: str

# @app.get("/")
@mcp.tool()
async def dashboard():
    print("dashboard")
    try:
        async with httpx.AsyncClient(verify=False) as client:
            r = await client.get(f"{BASE_API_URL}/portfolio/accounts")
            accounts = r.json()
    except Exception:
        return JSONResponse(content={"error": "Make sure you authenticate first then visit this page.", "login_url": "https://localhost:5055"}, status_code=401)
    account = accounts[0]
    account_id = accounts[0]["id"]
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.get(f"{BASE_API_URL}/portfolio/{account_id}/summary")
        summary = r.json()
    return {"account": account, "summary": summary}

# @app.get("/lookup")
@mcp.tool()
async def lookup(symbol: Optional[str] = Query(None)):
    stocks = []
    if symbol is not None:
        async with httpx.AsyncClient(verify=False) as client:
            r = await client.get(f"{BASE_API_URL}/iserver/secdef/search?symbol={symbol}&name=true")
            stocks = r.json()
    return {"stocks": stocks}

# @app.get("/contract/{contract_id}/{period}")
@mcp.tool()
async def contract(contract_id: str, period: str = '5d', bar: str = '1d'):
    data = {"conids": [contract_id]}
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.post(f"{BASE_API_URL}/trsrv/secdef", data=data)
        contract = r.json()['secdef'][0]
        r = await client.get(f"{BASE_API_URL}/iserver/marketdata/history?conid={contract_id}&period={period}&bar={bar}")
        price_history = r.json()
    return {"price_history": price_history, "contract": contract}

# @app.get("/orders")
@mcp.tool()
async def orders():
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.get(f"{BASE_API_URL}/iserver/account/orders")
        orders = r.json()["orders"]
    return {"orders": orders}

# @app.post("/order")
@mcp.tool()
async def place_order(order: OrderRequest):
    data = {
        "orders": [
            {
                "conid": order.contract_id,
                "orderType": "LMT",
                "price": order.price,
                "quantity": order.quantity,
                "side": order.side,
                "tif": "GTC"
            }
        ]
    }
    async with httpx.AsyncClient(verify=False) as client:
        await client.post(f"{BASE_API_URL}/iserver/account/{ACCOUNT_ID}/orders", json=data)
    return RedirectResponse(url="/orders", status_code=status.HTTP_303_SEE_OTHER)

# @app.get("/orders/{order_id}/cancel")
# @mcp.resource(
#     "order://orders/{order_id}/cancel"
# )
@mcp.tool()
async def cancel_order(order_id: str):
    cancel_url = f"{BASE_API_URL}/iserver/account/{ACCOUNT_ID}/order/{order_id}"
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.delete(cancel_url)
    return r.json()

# @app.get("/portfolio")
@mcp.tool()
async def portfolio():
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.get(f"{BASE_API_URL}/portfolio/{ACCOUNT_ID}/positions/0")
        positions = r.json() if r.content else []
    return {"positions": positions}

# @app.get("/watchlists")
@mcp.tool()
async def watchlists():
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.get(f"{BASE_API_URL}/iserver/watchlists")
        watchlist_data = r.json()["data"]
        watchlists = watchlist_data.get("user_lists", []) if "user_lists" in watchlist_data else []
    return {"watchlists": watchlists}

# @app.get("/watchlists/{id}")
@mcp.tool()
async def watchlist_detail(id: int):
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.get(f"{BASE_API_URL}/iserver/watchlist?id={id}")
        watchlist = r.json()
    return {"watchlist": watchlist}

# @app.get("/watchlists/{id}/delete")
@mcp.tool()
async def watchlist_delete(id: int):
    async with httpx.AsyncClient(verify=False) as client:
        await client.delete(f"{BASE_API_URL}/iserver/watchlist?id={id}")
    return RedirectResponse(url="/watchlists", status_code=status.HTTP_303_SEE_OTHER)

# @app.post("/watchlists/create")
@mcp.tool()
async def create_watchlist(data: WatchlistCreateRequest):
    name = data.name
    rows = []
    symbols = data.symbols.split(",")
    async with httpx.AsyncClient(verify=False) as client:
        for symbol in symbols:
            symbol = symbol.strip()
            if symbol:
                r = await client.get(f"{BASE_API_URL}/iserver/secdef/search?symbol={symbol}&name=true&secType=STK")
                contract_id = r.json()[0]['conid']
                rows.append({"C": contract_id})
        payload = {
            "id": int(time.time()),
            "name": name,
            "rows": rows
        }
        await client.post(f"{BASE_API_URL}/iserver/watchlist", json=payload)
    return RedirectResponse(url="/watchlists", status_code=status.HTTP_303_SEE_OTHER)

# LLM can query this function but failed to get the data or process the search query
# @app.get("/scanner")
@mcp.tool()
async def scanner(
    submitted: Optional[str] = Query(None),
    instrument: Optional[str] = Query(""),
    location: Optional[str] = Query(""),
    sort: Optional[str] = Query(""),
    filter: Optional[str] = Query(""),
    filter_value: Optional[str] = Query("")
):
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.get(f"{BASE_API_URL}/iserver/scanner/params")
        params = r.json()
    scanner_map = {}
    filter_map = {}
    for item in params['instrument_list']:
        scanner_map[item['type']] = {
            "display_name": item['display_name'],
            "filters": item['filters'],
            "sorts": []
        }
    for item in params['filter_list']:
        filter_map[item['group']] = {
            "display_name": item['display_name'],
            "type": item['type'],
            "code": item['code']
        }
    for item in params['scan_type_list']:
        for instrument_item in item['instruments']:
            scanner_map[instrument_item]['sorts'].append({
                "name": item['display_name'],
                "code": item['code']
            })
    for item in params['location_tree']:
        scanner_map[item['type']]['locations'] = item['locations']
    scan_results = []
    if submitted:
        data = {
            "instrument": instrument,
            "location": location,
            "type": sort,
            "filter": [
                {
                    "code": filter,
                    "value": filter_value
                }
            ]
        }
        async with httpx.AsyncClient(verify=False) as client:
            r = await client.post(f"{BASE_API_URL}/iserver/scanner/run", json=data)
            scan_results = r.json()
    return {
        "params": params,
        "scanner_map": scanner_map,
        "filter_map": filter_map,
        "scan_results": scan_results
    }


if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=3100)
