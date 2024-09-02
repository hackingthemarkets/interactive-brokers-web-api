import requests, time, os
from pprint import pprint

# disable SSL warnings until you install a certificate
from requests.packages.urllib3.exceptions import InsecureRequestWarning # type: ignore
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

BASE_API_URL = "https://localhost:5055/v1/api"

session = requests.Session()
session.verify = False

# get account info
r = session.get(f"{BASE_API_URL}/portfolio/accounts")
response = r.json()
pprint(response)
account_id = response[0]['id']

# get orders
# r = session.get(f"{BASE_API_URL}/iserver/account/orders")
# pprint(r.json())

# Get information about the google contract
# contract_id = 208813720

# data = {
#     "conids": [
#         contract_id
#     ]
# }
    
# r = session.post(f"{BASE_API_URL}/trsrv/secdef", data=data)
# contract = r.json()['secdef'][0]
# pprint(contract)

# Get market data for google
# period = '365d'
# bar = '1d'

# r = session.get(f"{BASE_API_URL}/iserver/marketdata/history?conid={contract_id}&period={period}&bar={bar}")
# price_history = r.json()
# pprint(price_history)

# place a limit order for 1 share of Google stock at 20.00 a share
# data = {
#     "orders": [
#         {
#             "conid": contract_id,
#             "orderType": "LMT",
#             "price": 20.00,
#             "quantity": 1,
#             "side": "BUY",
#             "tif": "GTC"
#         }
#     ]
# }

# r = session.post(f"{BASE_API_URL}/iserver/account/{account_id}/orders", json=data)
# pprint(r.json())
