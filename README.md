## Description
A simple Python API for Investopedia's stock simulator games.

## Features
Currently you can programmatically:
* Read all positions in your stock, and short portfolios and get quotes for each position
* Fetch and cancel pending/open trades
* Buy/Sell long positions
* Short sell/cover short positions
* Buy/sell options
* Perform option chain lookups
* Buy/sell options

## Dependencies
To use this API, there are a few dependencies that you will need to install.  See the below sections for an explanation of each.

### Python
This API is intended to be used for writing Python programs to automate trades in the Investopedia Stock Simulator, therefore you should have Python installed on your system.  I recommend using Python 3.12.2 or later to avoid running into issues or other problems.  You can download Python [here](https://www.python.org/downloads/).

### Git (optional)
This API is not currently hosted as a package anywhere, so you'll need to download the code directly from GitHub to use it.  [Download and install the latest version of Git](https://git-scm.com/downloads) on your system and run the following in a terminal to download a copy of this repository:

`git clone https://github.com/dchrostowski/investopedia_simulator_api.git/`

Alternatively, you can just download a zipped archive of the source code directly from this project's GitHub page and unzip it somewhere on your filesystem.  To do this, click on the green Code button and select Download ZIP.

### Node.js
Node.js is utilized to facilitate logging in to the simulator with a virtual web browser and fetching authentication tokens.  [Download and install the latest version of Node.js on your system here.](https://nodejs.org/en/download).


## Usage

Once all dependencies are installed, you will need to use pip to install supplementary Python packages to run your code with the API.  Open a terminal on your system and navigate to where you downloaded this code:

```cd path/to/investopedia_simulator_api```

Next run the following command to install the supplementary packages:

```pip install -r ./requirements.txt```

Once all the required packages are installed, you will need to provide your login credentials for the Investopedia Stock Simulator.  Rename the ```credentials_example.json``` file to ```credentials.json```, open it, and replace the username and password values with your actual username and password for logging in to Investopedia.  Make sure you leave the double quotes intaact.

Finally, try running the provided `example.py` file.  This `example.py` file is a usage example of the API.  Feel free to modify it as you see fit for your needs:

```python example.py```

## Example
### code
```
from investopedia_api import InvestopediaApi
import json
from datetime import datetime, timedelta
from api_models import OptionScope
from trade_common import OrderLimit, TransactionType, Expiration, StockTrade, OptionTrade

credentials = {}
with open('credentials.json') as ifh:
    credentials = json.load(ifh)
# look at credentials_example.json
# credentials = {"username": "you@example.org", "password": "yourpassword" }
client = InvestopediaApi(credentials)

p = client.portfolio
print("\nPortfolio Details")
print("-------------------------------------------------")
print("Portfolio Value: %s" % p.account_value)
print("Cash: %s" % p.cash)
print("Buying Power: %s" % p.buying_power)
print("Annual Return Percent: %s" % p.annual_return_pct)
print("-------------------------------------------------")

print("\nOpen Orders:")
# To cancel a pending trade, run open_order.cancel()
for open_order in p.open_orders:
    print("-------------------------------------------------")
    print("Trade Type: %s" % open_order.trade_type)
    print("Symbol: %s" % open_order.symbol)
    print("Quantity: %s" % open_order.quantity)
    print("Price: %s" % open_order.order_price)
    print("-------------------------------------------------")
print("-------------------------------------------------")


stock_portfolio = p.stock_portfolio
short_portfolio = p.short_portfolio
option_portfolio = p.option_portfolio

print("\nStock Portfolio Details:")
print("-------------------------------------------------")
print("Market Value: %s" % p.stock_portfolio.market_value)
print("Today's Gain: %s (%s%%)" % (p.stock_portfolio.day_gain_dollar, p.stock_portfolio.day_gain_percent))
print("Total Gain: %s (%s%%)" % (p.stock_portfolio.total_gain_dollar, p.stock_portfolio.total_gain_percent))
print("-------------------------------------------------")

print("\nLong Positions:")
for position in p.stock_portfolio:
    print("-------------------------------------------------")
    print("Company: %s (%s)" % (position.description, position.symbol))
    print("Shares: %s" % position.quantity)
    print("Purchase Price: %s" % position.purchase_price)
    print("Current Price: %s" % position.current_price)
    print("Today's Gain: %s (%s%%)" % (position.day_gain_dollar, position.day_gain_percent))
    print("Total Gain: %s (%s%%)" % (position.total_gain_dollar, position.total_gain_percent))
    print("Market/Total Value: %s" % position.market_value)
    print("\t------------------------------")
    print("\tQuote")
    print("\t------------------------------")
    quote = position.quote
    for k,v in quote.__dict__.items():
        print("\t%s: %s" % (k,v))
    print("\t------------------------------")
    print("-------------------------------------------------")


print("\nShort Positions:")
for position in p.short_portfolio:
    print("-------------------------------------------------")
    print("Company: %s (%s)" % (position.description, position.symbol))
    print("Shares: %s" % position.quantity)
    print("Purchase Price: %s" % position.purchase_price)
    print("Current Price: %s" % position.current_price)
    print("Today's Gain: %s (%s%%)" % (position.day_gain_dollar, position.day_gain_percent))
    print("Total Gain: %s (%s%%)" % (position.total_gain_dollar, position.total_gain_percent))
    print("Market/Total Value: %s" % position.market_value)
    print("\t------------------------------")
    print("\tQuote")
    print("\t------------------------------")
    quote = position.quote
    for k,v in quote.__dict__.items():
        print("\t%s: %s" % (k,v))
    print("\t------------------------------")
    print("-------------------------------------------------")

print("\nOption Positions:")
for position in p.option_portfolio:
    print("-------------------------------------------------")
    print("Company: %s (%s)" % (position.description, position.underlying_symbol))
    print("Symbol: %s" % position.symbol)
    print("Contracts: %s" % position.quantity)
    print("Purchase Price: %s" % position.purchase_price)
    print("Current Price: %s" % position.current_price)
    print("Today's Gain: %s (%s%%)" % (position.day_gain_dollar, position.day_gain_percent))
    print("Total Gain: %s (%s%%)" % (position.total_gain_dollar, position.total_gain_percent))
    print("Market/Total Value: %s" % position.market_value)
    print("\t------------------------------")
    print("\tQuote")
    print("\t------------------------------")
    quote = position.quote
    for k,v in quote.__dict__.items():
        print("\t%s: %s" % (k,v))
    print("\t------------------------------")
    print("-------------------------------------------------")

# Make a stock trade
    
# Buy 2 shares of GOOG with limit $100 and no expiration
tt1 = TransactionType.BUY
ol1 = OrderLimit.LIMIT(100)
exp1 = Expiration.GOOD_UNTIL_CANCELLED()
trade1 = StockTrade(portfolio_id=p.portfolio_id, symbol="GOOG", quantity=2, transaction_type=tt1, order_limit=ol1, expiration=exp1)
trade1.validate()
trade1.execute()

# Buy 3 shares of AAPL at market value with expiration set to end of day
# defaults order_limit to OrderLimit.MARKET() and expiration to Expiration.END_OF_DAY())
trade2 = StockTrade(portfolio_id=p.portfolio_id, symbol='AAPL', quantity=3, transaction_type=TransactionType.BUY)
trade2.validate()
trade2.execute()

# short sell 1 share of AMZN
trade3 = StockTrade(portfolio_id=p.portfolio_id, symbol='AMZN', quantity=1, transaction_type=TransactionType.SELL_SHORT)
trade3.validate()
trade3.execute()


client.refresh_portfolio()
p = client.portfolio

for open_order in p.open_orders:
    if open_order.symbol == 'GOOG' and open_order.quantity == 2:
        # cancel GOOG trade
        open_order.cancel()
    
    if open_order.symbol == 'AAPL' and open_order.quantity == 3:
        # cancel AAPL trade
        open_order.cancel()

    if open_order.symbol == 'AMZN' and open_order.quantity == 1:
        # cancel AMZN trade
        open_order.cancel()


stock_portfolio = p.stock_portfolio
if len(p.stock_portfolio) > 0:
    # first long position in portfolio
    first_long_position = p.stock_portfolio[0]
    symbol = first_long_position.symbol
    quantity = first_long_position.quantity
    
    # execute trade to sell position in portfolio
    first_long_position.sell()
    client.refresh_portfolio()
    p = client.portfolio
    for oo in p.open_orders:
        if oo.symbol == symbol and oo.quantity == quantity:
            # cancel trade to sell first position in portfolio
            oo.cancel()

short_portfolio = p.short_portfolio
if len(p.short_portfolio) > 0:
    # first short position in portfolio
    first_short_position = p.short_portfolio[0]
    symbol = first_short_position.symbol
    quantity = first_short_position.quantity
    
    # execute trade to cover position in portfolio
    first_short_position.cover()
    client.refresh_portfolio()
    p = client.portfolio
    for oo in p.open_orders:
        # cancel cover trade you just made
        if oo.symbol == symbol and oo.quantity == quantity:
            # cancel trade to cover first position in portfolio
            oo.cancel()

if len(p.option_portfolio) > 0:
    first_option_contract = p.option_portfolio[0]
    symbol = first_option_contract.symbol
    quantity = first_option_contract.quantity
    # close out first option contract in portfolio
    first_option_contract.close()
    client.refresh_portfolio()
    p = client.portfolio
    for oo in p.open_orders:
        # cancel order to close out contract
        if oo.symbol == symbol and oo.quantity == quantity:
            oo.cancel()


# Gets all available option contracts for AAPL
oc = client.get_option_chain('AAPL')
all_options = oc.all()
print("There are %s available option contracts for AAPL" % len(all_options))


two_weeks_from_today = datetime.now() + timedelta(days=14)
print("AAPL in-the-money put options expiring within two weeks:")
put_options_near_expiration_itm = oc.search(before=two_weeks_from_today, puts=True, calls=False, scope=OptionScope.IN_THE_MONEY)
for option in put_options_near_expiration_itm:
    print("%s:\n\tbid: %s\n\task: %s\n\tlast price: %s\n\texpires:%s" % (option.symbol, option.bid, option.ask, option.last, option.expiration.strftime("%m/%d/%Y") ))


option_to_buy = put_options_near_expiration_itm[0]
trade4 = OptionTrade(portfolio_id=p.portfolio_id, symbol=option_to_buy.symbol, quantity=1, transaction_type=TransactionType.BUY)
trade4.validate()
trade4.execute()
client.refresh_portfolio()

p = client.portfolio
for oo in p.open_orders:
    if oo.symbol == option_to_buy.symbol:
        oo.cancel()

    ```

## Safe read-only first run

**Do not run `example.py` for a smoke test.** The historical example contains buy, sell, short, option, and order-cancellation operations.

A read-only snapshot script is included in this fork:

```bash
python readonly_test.py
```

To print a structured JSON snapshot for later analysis:

```bash
python readonly_agent.py
```

Both scripts require a local `credentials.json` created from `credentials_example.json`. Never paste credentials or the contents of `auth.json` into a chat, and never commit either file. The authentication helper now reads credentials from environment variables supplied by the Python process and does not put the password in Node's command-line arguments.

Before the first login, install the repository's Node dependency in the Codespace:

```bash
npm install
```

These scripts are intended for portfolio inspection only. The trade methods elsewhere in this legacy library still exist; the read-only scripts do not call them. The library's transaction execution path now reserves a persistent slot in `transaction_guard.py` before submitting a stock or option transaction. The hard-coded limit is **3 attempts per America/New_York calendar day**. A reserved slot is deliberately never refunded, including ambiguous failures, to avoid accidental extra submissions after a timeout or crash. The local SQLite ledger is ignored by Git. Offline tests cover the limit and persistence. This guard is not a substitute for reviewing the code and confirming the ledger is stored on persistent storage; do not run automated trading until end-to-end validation is complete.


## Analysis-only mode (current default)

This fork is configured for **analysis and proposals only**. `safety_policy.py`
sets `TRADING_ENABLED = False`; stock/option execution, prepared transaction
execution, and order cancellation raise `TradingDisabledError` before sending
a mutating request. Do not change this setting for this project goal.

The portfolio diagnostics are deterministic and run locally. There is no paid AI
API configured and no model usage fee is required for the current rule-based
analysis. Market/news enrichment is not yet implemented; adding it later must
prefer free sources and clearly label data timestamps and limitations.

Run offline safety tests with:

```bash
python -m unittest discover -s tests -v
```

Never run `example.py` as a test: the legacy example contains transaction code.


## Alpaca Paper Trading read-only agent

The repository now also includes an **optional Alpaca Paper Trading** data source. It does not replace or remove the existing Investopedia code.

### Configure credentials locally

Create an Alpaca **Paper Trading** API key pair in the Alpaca dashboard. Never use live-trading keys for this project. Set these environment variables in your Codespace terminal (replace the placeholders locally; do not commit them or paste them into chat):

```bash
export APCA_API_KEY_ID="your-paper-key-id"
export APCA_API_SECRET_KEY="your-paper-secret-key"
```

For persistence, store the two values as Codespaces secrets and expose them as environment variables to the workspace. Do not create a committed credentials file.

### Run the snapshot

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python alpaca_readonly_agent.py
```

The Alpaca adapter is intentionally minimal and sends only `GET` requests to the fixed `https://paper-api.alpaca.markets` host: account, positions, and one month of portfolio history. It does not implement order submission or cancellation. The output contains portfolio information, so treat it as private before sharing it.

The Alpaca adapter classifies option assets separately using their asset class and
preserves the underlying symbol when supplied. Positions with an unrecognized side are
retained in an `other` category rather than silently omitted. The local diagnostics also
report gross long, gross short, options, other tracked positions, and net stock exposure.
Exposure percentages are shown relative to account value when that value is positive. Position concentration is measured against the total absolute market value
of positions with usable values: a position at 25% or more receives an informational
flag, while one at 50% or more receives a warning. These are configurable descriptive
thresholds, not personalized risk limits. Missing market values are excluded and
explicitly flagged.

The local diagnostics also calculate a simple return for the requested history window. The
calculation uses Alpaca's `base_value` when it is positive; otherwise it falls back to
the first valid equity observation. It reports the starting and ending values, absolute
change, and percentage change. This is a return for the available history window, not
necessarily a calendar-year or lifetime return. If the history-quality check detects
repeated zero or negative values before a positive latest value, the performance result
is deliberately marked unavailable rather than reporting a misleading loss.

The report includes a `portfolio_history_data_quality` section with timestamp and
equity point counts, an alignment indicator, duplicate timestamp count, and (when
timestamps are numeric) a count of adjacent out-of-order timestamp pairs. These
informational flags identify potentially unreliable history series; they do not
alter the underlying provider data or imply portfolio losses.

The report also includes `open_positions_intraday_pl`, which sums Alpaca's reported
`unrealized_intraday_pl` values with the same category breakdown and missing-data
accounting. This is the provider's reported intraday unrealized P/L for open positions;
it should not be interpreted as realized P/L or the entire account's daily return.

The diagnostics also summarize reported unrealized profit/loss for currently open
positions. The JSON field `open_positions_unrealized_pl` contains a total and a
long/short/options/other breakdown, plus counts of positions with and without a usable
`unrealized_pl` value. If any position is missing that value, an
`INCOMPLETE_UNREALIZED_PNL` informational flag is added. This is unrealized P/L on
open positions only; it is not realized profit, a tax calculation, or a complete
account-level return.

This is an initial integration; offline tests do not prove that your Alpaca keys are valid or that a live API request succeeds. The legacy Investopedia integration remains available separately. **Never run `example.py`**, which contains order execution and cancellation examples.
