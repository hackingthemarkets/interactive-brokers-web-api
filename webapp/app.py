import requests, time, os, random
from flask import Flask, render_template, request, redirect

# disable warnings until you install a certificate
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

BASE_API_URL = "https://localhost:5055/v1/api"
ACCOUNT_ID = os.environ['IBKR_ACCOUNT_ID']

os.environ['PYTHONHTTPSVERIFY'] = '0'

app = Flask(__name__)

@app.template_filter('ctime')
def timectime(s):
    return time.ctime(s/1000)


@app.route("/")
def dashboard():
    try:
        r = requests.get(f"{BASE_API_URL}/portfolio/accounts", verify=False)
        accounts = r.json()
    except Exception as e:
        return 'Make sure you authenticate first then visit this page. <a href="https://localhost:5055">Log in</a>'

    account = accounts[0]

    account_id = accounts[0]["id"]
    r = requests.get(f"{BASE_API_URL}/portfolio/{account_id}/summary", verify=False)
    summary = r.json()
    
    return render_template("dashboard.html", account=account, summary=summary)


@app.route("/lookup")
def lookup():
    symbol = request.args.get('symbol', None)
    stocks = []

    if symbol is not None:
        r = requests.get(f"{BASE_API_URL}/iserver/secdef/search?symbol={symbol}&name=true", verify=False)

        response = r.json()
        stocks = response

    return render_template("lookup.html", stocks=stocks)


@app.route("/contract/<contract_id>/<period>")
def contract(contract_id, period='5d', bar='1d'):
    data = {
        "conids": [
            contract_id
        ]
    }
    
    r = requests.post(f"{BASE_API_URL}/trsrv/secdef", data=data, verify=False)
    contract = r.json()['secdef'][0]

    r = requests.get(f"{BASE_API_URL}/iserver/marketdata/history?conid={contract_id}&period={period}&bar={bar}", verify=False)
    price_history = r.json()

    return render_template("contract.html", price_history=price_history, contract=contract)


@app.route("/orders")
def orders():
    r = requests.get(f"{BASE_API_URL}/iserver/account/orders", verify=False)
    orders = r.json()["orders"]
    
    # place order code
    return render_template("orders.html", orders=orders)


@app.route("/order", methods=['POST'])
def place_order():
    print("== placing order ==")

    data = {
        "orders": [
            {
                "conid": int(request.form.get('contract_id')),
                "orderType": "LMT",
                "price": float(request.form.get('price')),
                "quantity": int(request.form.get('quantity')),
                "side": request.form.get('side'),
                "tif": "GTC"
            }
        ]
    }

    r = requests.post(f"{BASE_API_URL}/iserver/account/{ACCOUNT_ID}/orders", json=data, verify=False)

    return redirect("/orders")

@app.route("/orders/<order_id>/cancel")
def cancel_order(order_id):
    cancel_url = f"{BASE_API_URL}/iserver/account/{ACCOUNT_ID}/order/{order_id}" 
    r = requests.delete(cancel_url, verify=False)

    return r.json()


@app.route("/portfolio")
def portfolio():
    r = requests.get(f"{BASE_API_URL}/portfolio/{ACCOUNT_ID}/positions/0", verify=False)

    if r.content:
        positions = r.json()
    else:
        positions = []

    # return my positions, how much cash i have in this account
    return render_template("portfolio.html", positions=positions)

@app.route("/watchlists")
def watchlists():
    r = requests.get(f"{BASE_API_URL}/iserver/watchlists", verify=False)

    watchlist_data = r.json()["data"]
    watchlists = []
    if "user_lists" in watchlist_data:
        watchlists = watchlist_data["user_lists"]
        
    return render_template("watchlists.html", watchlists=watchlists)


@app.route("/watchlists/<int:id>")
def watchlist_detail(id):
    r = requests.get(f"{BASE_API_URL}/iserver/watchlist?id={id}", verify=False)

    watchlist = r.json()

    return render_template("watchlist.html", watchlist=watchlist)


@app.route("/watchlists/<int:id>/delete")
def watchlist_delete(id):
    r = requests.delete(f"{BASE_API_URL}/iserver/watchlist?id={id}", verify=False)

    return redirect("/watchlists")

@app.route("/watchlists/create", methods=['POST'])
def create_watchlist():
    data = request.get_json()
    name = data['name']

    rows = []
    symbols = data['symbols'].split(",")
    for symbol in symbols:
        symbol = symbol.strip()
        if symbol:
            r = requests.get(f"{BASE_API_URL}/iserver/secdef/search?symbol={symbol}&name=true&secType=STK", verify=False)
            contract_id = r.json()[0]['conid']
            rows.append({"C": contract_id})

    data = {
        "id": int(time.time()),
        "name": name,
        "rows": rows
    }

    r = requests.post(f"{BASE_API_URL}/iserver/watchlist", json=data, verify=False)
    
    return redirect("/watchlists")

@app.route("/scanner")
def scanner():
    r = requests.get(f"{BASE_API_URL}/iserver/scanner/params", verify=False)
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
        for instrument in item['instruments']:
            scanner_map[instrument]['sorts'].append({
                "name": item['display_name'],
                "code": item['code']
            })

    for item in params['location_tree']:
        scanner_map[item['type']]['locations'] = item['locations']


    submitted = request.args.get("submitted", "")
    selected_instrument = request.args.get("instrument", "")
    location = request.args.get("location", "")
    sort = request.args.get("sort", "")
    scan_results = []
    filter_code = request.args.get("filter", "")
    filter_value = request.args.get("filter_value", "")

    if submitted:
        data = {
            "instrument": selected_instrument,
            "location": location,
            "type": sort,
            "filter": [
                {
                    "code": filter_code,
                    "value": filter_value
                }
            ]
        }
            
        r = requests.post(f"{BASE_API_URL}/iserver/scanner/run", json=data, verify=False)
        scan_results = r.json()

    return render_template("scanner.html", params=params, scanner_map=scanner_map, filter_map=filter_map, scan_results=scan_results)
