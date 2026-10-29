# Gemini portfolio assistant setup

The Gemini assistant analyzes an Alpaca Paper Trading snapshot. It is strictly
read-only: it does not submit, modify, or cancel orders.

## 1. Create a free Gemini API key

1. Open https://aistudio.google.com/apikey.
2. Create an API key in a project eligible for the Gemini API free tier.
3. Do not enable paid billing or upgrade the project for this setup.

Google controls free-tier model availability and quotas. Check the active limits
for `gemini-2.5-flash` in Google AI Studio before use.

## 2. Configure Codespaces secrets

In GitHub repository Settings, add this Codespaces secret:

- `GEMINI_API_KEY`: your Google AI Studio API key

Keep the existing Alpaca Paper Trading secrets:

- `APCA_API_KEY_ID`
- `APCA_API_SECRET_KEY`

Do not put keys in source files, command-line arguments, commits, or chat
messages. If a secret was added after a Codespace was created and is not visible
in its terminal, restart/rebuild the Codespace.

## 3. Install dependencies and run tests

No new Python package is required; the client uses the existing `requests`
dependency.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## 4. Ask a portfolio question

```bash
python ask_portfolio.py "Analyze my portfolio concentration and explain the main risks."
```

The script reads the Alpaca Paper account through the existing GET-only client,
computes local diagnostics, and sends minimized context to Gemini 2.5 Flash.
Optionally, `GEMINI_MODEL` can override the default model; use only a model
available to your free-tier project.

## Privacy and safety

The minimized context sent to Google includes selected account balances,
position symbols/quantities/market values, and locally computed diagnostics.
Google's free-tier terms state that submitted content may be used to improve
products. Do not use this feature if you do not want those selected financial
details sent to Google.

The request has no tools or function calling. The AI receives no order
capabilities. All Alpaca access remains read-only, and responses are educational
descriptions of the supplied snapshot, not financial advice.
