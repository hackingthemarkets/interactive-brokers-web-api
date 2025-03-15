import requests, time, os, random, functools
from flask import Flask, render_template, request, redirect
from babel.numbers import get_currency_symbol, format_currency
import locale

# disable warnings until you install a certificate
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

BASE_API_URL = "https://localhost:5055/v1/api"

os.environ['PYTHONHTTPSVERIFY'] = '0'

# Set locale for number formatting
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'en_US')
    except:
        pass  # If both fail, we'll use Babel's formatting instead

app = Flask(__name__)

def require_auth(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        accounts = []
        try:
            r = requests.get(f"{BASE_API_URL}/portfolio/accounts", verify=False)
            accounts = r.json()
        except Exception as e:
            return 'Make sure you authenticate first then visit current page. <a href="https://localhost:5055">Log in</a>'
        return f(*args, accounts=accounts, **kwargs)
    return decorated_function

@app.template_filter('ctime')
def timectime(s):
    return time.ctime(s/1000)

@app.template_filter('currency_symbol')
def currency_symbol(currency_code):
    """Get the currency symbol for any currency code using Babel."""
    try:
        # Get the currency symbol using Babel
        symbol = get_currency_symbol(currency_code)
        return symbol
    except (ValueError, KeyError):
        # If the currency code is not recognized, return the code itself
        return currency_code

@app.template_filter('money_format')
def money_format(amount, currency_code='USD'):
    """Format a number as currency in US locale."""
    try:
        # Try using locale first (better for US formatting)
        if currency_code == 'USD':
            return locale.currency(float(amount), grouping=True)
        else:
            # For non-USD, use Babel's formatting
            return format_currency(amount, currency_code, locale='en_US')
    except (ValueError, TypeError, locale.Error):
        # Fallback to basic formatting if locale or Babel fails
        try:
            return f"{float(amount):,.2f}"
        except (ValueError, TypeError):
            return str(amount)

@app.route("/")
@require_auth
def dashboard(accounts):
    # Get summary for each account
    account_summaries = []
    for account in accounts:
        account_id = account["id"]
        r = requests.get(f"{BASE_API_URL}/portfolio/{account_id}/summary", verify=False)
        summary = r.json()
        account_summaries.append({
            "account": account,
            "summary": summary
        })
    return render_template("dashboard.html", account_summaries=account_summaries)


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
@require_auth
def contract(contract_id, accounts, period='5d', bar='1d'):
    data = {
        "conids": [
            contract_id
        ]
    }
    
    r = requests.post(f"{BASE_API_URL}/trsrv/secdef", data=data, verify=False)
    contract = r.json()['secdef'][0]

    r = requests.get(f"{BASE_API_URL}/iserver/marketdata/history?conid={contract_id}&period={period}&bar={bar}", verify=False)
    price_history = r.json()

    return render_template("contract.html", price_history=price_history, contract=contract, accounts=accounts)


@app.route("/orders")
@require_auth
def orders(accounts):
    r = requests.get(f"{BASE_API_URL}/iserver/account/orders", verify=False)
    orders = r.json()["orders"]
    return render_template("orders.html", orders=orders)


@app.route("/order", methods=['POST'])
def place_order():
    print("== placing order ==")
    account_id = request.form.get('account_id')

    data = {
        "orders": [
            {
                "acctId": account_id,
                "conid": int(request.form.get('contract_id')),
                "orderType": "LMT",
                "price": float(request.form.get('price')),
                "quantity": int(request.form.get('quantity')),
                "side": request.form.get('side'),
                "tif": "GTC"
            }
        ]
    }

    r = requests.post(f"{BASE_API_URL}/iserver/account/{account_id}/orders", json=data, verify=False)
    return r.json()

@app.route("/reply/<reply_id>", methods=['POST'])
def reply(reply_id):
    post_data = request.get_json()
    r = requests.post(f"{BASE_API_URL}/iserver/reply/{reply_id}", json=post_data, verify=False)
    return r.json()


@app.route("/account/<account_id>/order/<order_id>", methods=['DELETE'])
def cancel_order(account_id, order_id):
    cancel_url = f"{BASE_API_URL}/iserver/account/{account_id}/order/{order_id}"
    r = requests.delete(cancel_url, verify=False)
    return r.json()


@app.route("/portfolio")
@require_auth
def portfolio(accounts):
    all_positions = []
    account_map = {account["id"]: account for account in accounts}
    
    for account in accounts:
        account_id = account["id"]
        r = requests.get(f"{BASE_API_URL}/portfolio/{account_id}/positions/0", verify=False)
        if r.content:
            positions = r.json()
            for position in positions:
                position['account_id'] = account_id
                position['account'] = account
                all_positions.append(position)

    return render_template("portfolio.html", positions=all_positions, account_map=account_map)

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
