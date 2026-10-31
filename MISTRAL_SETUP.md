# Mistral portfolio assistant setup

The optional Mistral assistant analyzes an Alpaca Paper Trading snapshot. It is
strictly read-only: it does not submit, modify, or cancel orders.

## 1. Configure Codespaces secrets

In GitHub, open the repository settings and add these Codespaces secrets:

- `MISTRAL_API_KEY`: your Mistral API key
- `APCA_API_KEY_ID`: your Alpaca Paper Trading key ID
- `APCA_API_SECRET_KEY`: your Alpaca Paper Trading secret key

Do not put these values in source files, command-line arguments, commits, or chat
messages. If a secret was added after a Codespace was created and is not visible
in its terminal, restart/rebuild the Codespace so its environment is refreshed.

## 2. Install dependencies and run tests

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## 3. Ask a portfolio question

```bash
python ask_portfolio.py "Analyze my portfolio concentration and explain the main risks."
```

The script fetches the current Alpaca Paper account snapshot using read-only GET
requests, computes the local diagnostics, and sends a minimized context plus
your question to Mistral's Chat Completions API.

By default it uses `mistral-small-latest`. You can override this with the
`MISTRAL_MODEL` environment variable if your Mistral account has access to a
different model.

## Privacy and limitations

The portfolio context sent to Mistral includes selected account balances,
position symbols/quantities/market values, and locally computed diagnostics.
Do not use this feature if you do not want those selected financial details sent
to Mistral for processing. API availability, free-tier quotas, and rate limits
are controlled by Mistral and may change.

The assistant receives no trading tools. Its answers are educational descriptions
of the supplied snapshot, not financial advice. It has no live news or market
data unless those are separately added in a future, clearly scoped change.
