import requests, time, os, random
from flask import Flask, render_template, request, redirect, url_for

# disable warnings until you install a certificate
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

BASE_API_URL = "https://localhost:5055/v1/api"
os.environ['PYTHONHTTPSVERIFY'] = '0'

app = Flask(__name__)

@app.template_filter('ctime')
def timectime(s):
    return time.ctime(s/1000)

def get_accounts():
    """Get available accounts or return None if not authenticated"""
    try:
        r = requests.get(f"{BASE_API_URL}/portfolio/accounts", verify=False)
        return r.json()
    except Exception:
        return None

@app.route("/")
def root():
    """Show accounts list or redirect to first account if only one exists"""
    accounts = get_accounts()
    if not accounts:
        return 'Make sure you authenticate first then visit this page. <a href="https://localhost:5055">Log in</a>'
    if len(accounts) == 1:
        return redirect(url_for('account_dashboard', account_id=accounts[0]['id']))
    return render_template("accounts.html", accounts=accounts)

@app.route("/accounts/<account_id>")
def account_dashboard(account_id):
    """Show dashboard for a specific account"""
    accounts = get_accounts()
    if not accounts:
        return 'Make sure you authenticate first then visit this page. <a href="https://localhost:5055">Log in</a>'

    if not any(acc['id'] == account_id for acc in accounts):
        return redirect(url_for('root'))

    r = requests.get(f"{BASE_API_URL}/portfolio/{account_id}/summary", verify=False)
    summary = r.json()
    
    return render_template("dashboard.html", accounts=accounts, selected_account=account_id, summary=summary)

@app.route("/orders")
def orders():
    """Show orders across all accounts"""
    accounts = get_accounts()
    if not accounts:
        return redirect(url_for('root'))

    r = requests.get(f"{BASE_API_URL}/iserver/account/orders", verify=False)
    orders = r.json()["orders"]
    
    # Get selected account from query param if filtering by account
    selected_account = request.args.get('account')
    if selected_account and not any(acc['id'] == selected_account for acc in accounts):
        selected_account = None
        
    return render_template("orders.html", orders=orders, accounts=accounts, selected_account=selected_account)

@app.route("/accounts/<account_id>/orders", methods=['POST'])
def place_order(account_id):
    """Place order for specific account"""
    accounts = get_accounts()
    if not accounts or not any(acc['id'] == account_id for acc in accounts):
        return redirect(url_for('root'))

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

    r = requests.post(f"{BASE_API_URL}/iserver/account/{account_id}/orders", json=data, verify=False)
    return redirect(url_for('orders', account=account_id))

@app.route("/accounts/<account_id>/orders/<order_id>", methods=['DELETE'])
def cancel_order(account_id, order_id):
    """Cancel specific order in an account"""
    accounts = get_accounts()
    if not accounts or not any(acc['id'] == account_id for acc in accounts):
        return redirect(url_for('root'))

    cancel_url = f"{BASE_API_URL}/iserver/account/{account_id}/order/{order_id}" 
    r = requests.delete(cancel_url, verify=False)
    return r.json()

@app.route("/positions")
def positions():
    """Show positions across all accounts or filtered by account"""
    accounts = get_accounts()
    if not accounts:
        return redirect(url_for('root'))

    # Get selected account from query param if filtering
    selected_account = request.args.get('account')
    if selected_account and not any(acc['id'] == selected_account for acc in accounts):
        selected_account = None

    positions = []
    if selected_account:
        r = requests.get(f"{BASE_API_URL}/portfolio/{selected_account}/positions/0", verify=False)
        positions = r.json() if r.content else []
    else:
        # Aggregate positions from all accounts
        for account in accounts:
            r = requests.get(f"{BASE_API_URL}/portfolio/{account['id']}/positions/0", verify=False)
            if r.content:
                positions.extend(r.json())

    return render_template("positions.html", positions=positions, accounts=accounts, selected_account=selected_account)

@app.route("/lookup")
def lookup():
    symbol = request.args.get('symbol', None)
    stocks = []

    if symbol is not None:
        r = requests.get(f"{BASE_API_URL}/iserver/secdef/search?symbol={symbol}&name=true", verify=False)

        response = r.json()
        stocks = response

    return render_template("lookup.html", stocks=stocks)

@app.route("/contract/<contract_id>")
def contract(contract_id):
    data = {
        "conids": [
            contract_id
        ]
    }
    
    r = requests.post(f"{BASE_API_URL}/trsrv/secdef", data=data, verify=False)
    contract = r.json()['secdef'][0]

    period = request.args.get('period', '5d')
    bar = request.args.get('bar', '1d')
    r = requests.get(f"{BASE_API_URL}/iserver/marketdata/history?conid={contract_id}&period={period}&bar={bar}", verify=False)
    price_history = r.json()

    return render_template("contract.html", price_history=price_history, contract=contract)

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

@app.route("/watchlists/<int:id>/delete", methods=['POST'])
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
