#!/usr/bin/env python3
"""DCF Magic — lightweight server for portfolio management and FMP price caching."""

import json
import os
import re
import urllib.request
import urllib.error
from datetime import date
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PORT = 8000
DATA_FILE = Path(__file__).parent / "portfolio.json"
ENV_FILE = Path(__file__).parent / ".env"


def load_env():
    """Read FMP_API_KEY from .env file."""
    if not ENV_FILE.exists():
        return ""
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith("FMP_API_KEY="):
            return line.split("=", 1)[1].strip()
    return ""


def load_portfolio():
    if not DATA_FILE.exists():
        DATA_FILE.write_text(json.dumps({"stocks": []}, indent=2))
    return json.loads(DATA_FILE.read_text())


def save_portfolio(data):
    DATA_FILE.write_text(json.dumps(data, indent=2))


def fetch_fmp_price(symbol):
    """Fetch current price from FMP /stable/profile endpoint."""
    api_key = load_env()
    if not api_key:
        raise ValueError("FMP_API_KEY not set in .env")

    url = f"https://financialmodelingprep.com/stable/profile?symbol={symbol}&apikey={api_key}"
    req = urllib.request.Request(url, headers={"User-Agent": "DCFMagic/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())

    if isinstance(data, dict) and data.get("Error Message"):
        raise ValueError(data["Error Message"])
    if isinstance(data, list) and len(data) > 0:
        return data[0].get("price")
    raise ValueError(f"No data returned for {symbol}")


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._serve_file("index.html", "text/html")
        elif self.path == "/portfolio":
            self._serve_file("portfolio.html", "text/html")
        elif self.path == "/api/stocks":
            portfolio = load_portfolio()
            self._json_response(portfolio["stocks"])
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/stocks":
            body = self._read_body()
            portfolio = load_portfolio()
            symbol = body.get("symbol", "").upper().strip()
            if not symbol:
                return self._json_response({"error": "symbol required"}, 400)
            if any(s["symbol"] == symbol for s in portfolio["stocks"]):
                return self._json_response({"error": f"{symbol} already exists"}, 409)
            stock = {
                "symbol": symbol,
                "eps": body.get("eps", 0),
                "pe": body.get("pe", 0),
                "growthRate": body.get("growthRate", 0),
                "desiredReturn": body.get("desiredReturn", 15),
                "epsMultiple": body.get("epsMultiple", 18),
                "cachedPrice": None,
                "cachedPriceDate": None,
            }
            # Auto-fetch current price on add
            try:
                price = fetch_fmp_price(symbol)
                if price is not None:
                    stock["cachedPrice"] = price
                    stock["cachedPriceDate"] = date.today().isoformat()
            except Exception:
                pass  # price fetch is best-effort
            portfolio["stocks"].append(stock)
            save_portfolio(portfolio)
            self._json_response(stock, 201)

        elif self.path == "/api/refresh-prices":
            portfolio = load_portfolio()
            today = date.today().isoformat()
            updated = 0
            errors = []
            for stock in portfolio["stocks"]:
                if stock.get("cachedPriceDate") == today:
                    continue
                try:
                    price = fetch_fmp_price(stock["symbol"])
                    if price is not None:
                        stock["cachedPrice"] = price
                        stock["cachedPriceDate"] = today
                        updated += 1
                except Exception as e:
                    errors.append({"symbol": stock["symbol"], "error": str(e)})
            save_portfolio(portfolio)
            self._json_response({
                "updated": updated,
                "errors": errors,
                "stocks": portfolio["stocks"],
            })

        elif re.match(r"^/api/stocks/([A-Za-z0-9.-]+)/price$", self.path):
            symbol = re.match(r"^/api/stocks/([A-Za-z0-9.-]+)/price$", self.path).group(1).upper()
            portfolio = load_portfolio()
            stock = next((s for s in portfolio["stocks"] if s["symbol"] == symbol), None)
            if not stock:
                return self._json_response({"error": "Stock not found"}, 404)
            today = date.today().isoformat()
            if stock.get("cachedPriceDate") == today:
                return self._json_response(stock)
            try:
                price = fetch_fmp_price(symbol)
                if price is not None:
                    stock["cachedPrice"] = price
                    stock["cachedPriceDate"] = today
                    save_portfolio(portfolio)
                self._json_response(stock)
            except Exception as e:
                self._json_response({"error": str(e)}, 502)

        else:
            self._json_response({"error": "Not found"}, 404)

    def do_PUT(self):
        match = re.match(r"^/api/stocks/([A-Za-z0-9.-]+)$", self.path)
        if not match:
            return self._json_response({"error": "Not found"}, 404)
        symbol = match.group(1).upper()
        body = self._read_body()
        portfolio = load_portfolio()
        stock = next((s for s in portfolio["stocks"] if s["symbol"] == symbol), None)
        if not stock:
            return self._json_response({"error": "Stock not found"}, 404)
        for key in ("eps", "pe", "growthRate", "desiredReturn", "epsMultiple"):
            if key in body:
                stock[key] = body[key]
        save_portfolio(portfolio)
        self._json_response(stock)

    def do_DELETE(self):
        match = re.match(r"^/api/stocks/([A-Za-z0-9.-]+)$", self.path)
        if not match:
            return self._json_response({"error": "Not found"}, 404)
        symbol = match.group(1).upper()
        portfolio = load_portfolio()
        before = len(portfolio["stocks"])
        portfolio["stocks"] = [s for s in portfolio["stocks"] if s["symbol"] != symbol]
        if len(portfolio["stocks"]) == before:
            return self._json_response({"error": "Stock not found"}, 404)
        save_portfolio(portfolio)
        self._json_response({"deleted": symbol})

    # --- Helpers ---

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw)

    def _json_response(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, filename, content_type):
        filepath = Path(__file__).parent / filename
        if not filepath.exists():
            self.send_error(404)
            return
        content = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        print(f"  {args[0]}")


if __name__ == "__main__":
    load_portfolio()  # ensure file exists
    print(f"DCF Magic running at http://localhost:{PORT}")
    HTTPServer(("", PORT), Handler).serve_forever()
