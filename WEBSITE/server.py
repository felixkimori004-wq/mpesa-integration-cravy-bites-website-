import base64
import ipaddress
import json
import mimetypes
import os
import re
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4


ROOT = Path(__file__).parent
PORT = int(os.environ.get("PORT", "8000"))
ORDERS = []

MENU = [
    {
        "id": "jollof",
        "name": "Smoky Party Jollof",
        "description": "Smoky long-grain rice, sweet plantain & our signature pepper sauce.",
        "price": 1885,
        "category": "Nigerian",
        "tag": "Guest favourite",
        "image": "photo-1516684732162-798a0062be99",
    },
    {
        "id": "suya",
        "name": "Charcoal Beef Suya",
        "description": "Spiced flame-grilled beef, sliced onions & fresh tomato.",
        "price": 2340,
        "category": "Grills",
        "tag": "Spicy",
        "image": "photo-1544025162-d76694265947",
    },
    {
        "id": "salmon",
        "name": "Honey-glazed Salmon",
        "description": "Pan-seared salmon, citrus glaze & buttery seasonal greens.",
        "price": 3120,
        "category": "Grills",
        "tag": "Chef's pick",
        "image": "photo-1467003909585-2f8a72700288",
    },
    {
        "id": "pasta",
        "name": "Creamy Tuscan Pasta",
        "description": "Silky garlic cream, sun-dried tomato, parmesan & basil.",
        "price": 2210,
        "category": "Comfort",
        "tag": "Bestseller",
        "image": "photo-1473093295043-cdd812d0e601",
    },
    {
        "id": "chicken",
        "name": "Crispy Herb Chicken",
        "description": "Golden, juicy chicken with rosemary fries & house slaw.",
        "price": 2535,
        "category": "Comfort",
        "tag": "Popular",
        "image": "photo-1532550907401-a500c9a57435",
    },
    {
        "id": "salad",
        "name": "Garden Glow Salad",
        "description": "Avocado, ripe tomato, greens, crunchy seeds & lemon dressing.",
        "price": 1690,
        "category": "Fresh",
        "tag": "Fresh & light",
        "image": "photo-1512621776951-a57141f2eefd",
    },
    {
        "id": "burger",
        "name": "The Cravy Smash Burger",
        "description": "Double smashed beef, aged cheddar, pickles & secret sauce.",
        "price": 30,
        "category": "Comfort",
        "tag": "Bestseller",
        "image": "photo-1568901346375-23c9450c58cd",
    },
    {
        "id": "pancakes",
        "name": "Berry Brunch Pancakes",
        "description": "Fluffy buttermilk stacks, fresh berries & maple syrup.",
        "price": 4,
        "category": "Breakfast",
        "tag": "Brunch favourite",
        "image": "photo-1528207776546-365bb710ee93",
    },
]


def daraja_settings():
    required = {
        "DARAJA_CONSUMER_KEY": os.environ.get("DARAJA_CONSUMER_KEY", "").strip(),
        "DARAJA_CONSUMER_SECRET": os.environ.get("DARAJA_CONSUMER_SECRET", "").strip(),
        "DARAJA_SHORTCODE": os.environ.get("DARAJA_SHORTCODE", "").strip(),
        "DARAJA_PASSKEY": os.environ.get("DARAJA_PASSKEY", "").strip(),
        "DARAJA_CALLBACK_URL": os.environ.get("DARAJA_CALLBACK_URL", "").strip(),
    }
    if any(not value for value in required.values()):
        raise ValueError("Set the Daraja environment variables before accepting M-Pesa payments.")

    callback = urlparse(required["DARAJA_CALLBACK_URL"])
    if callback.scheme != "https" or not callback.hostname or callback.path.rstrip("/") != "/callback":
        raise ValueError("DARAJA_CALLBACK_URL must be a public HTTPS URL ending in /callback.")
    if callback.username or callback.password or callback.query or callback.fragment:
        raise ValueError("DARAJA_CALLBACK_URL must not contain credentials, query parameters, or a fragment.")
    hostname = callback.hostname.lower()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        raise ValueError("DARAJA_CALLBACK_URL must use a publicly reachable host.")
    try:
        callback_ip = ipaddress.ip_address(hostname)
    except ValueError:
        callback_ip = None
    if callback_ip is not None and not callback_ip.is_global:
        raise ValueError("DARAJA_CALLBACK_URL must use a publicly reachable host.")

    environment = os.environ.get("DARAJA_ENV", "sandbox").strip().lower()
    if environment not in {"sandbox", "production"}:
        raise ValueError("DARAJA_ENV must be sandbox or production.")
    required["api_host"] = "api.safaricom.co.ke" if environment == "production" else "sandbox.safaricom.co.ke"
    return required


def daraja_json_request(url, headers, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers=headers, method="GET" if payload is None else "POST")
    try:
        with urlopen(request, timeout=25) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        print(f"Daraja HTTP error ({error.code}): {details}", flush=True)
        raise RuntimeError("Safaricom could not accept the payment request. Check the server terminal.") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"Daraja request failed: {error}", flush=True)
        raise RuntimeError("Could not reach Safaricom. Please try again shortly.") from error
    if not isinstance(result, dict):
        raise RuntimeError("Safaricom returned an unexpected response.")
    return result


def start_stk_push(phone, amount):
    config = daraja_settings()
    credentials = f"{config['DARAJA_CONSUMER_KEY']}:{config['DARAJA_CONSUMER_SECRET']}".encode("utf-8")
    token_response = daraja_json_request(
        f"https://{config['api_host']}/oauth/v1/generate?grant_type=client_credentials",
        {"Authorization": f"Basic {base64.b64encode(credentials).decode('ascii')}"},
    )
    access_token = token_response.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        print("Daraja token response did not contain an access token.", flush=True)
        raise RuntimeError("Safaricom did not return an access token.")

    shortcode = config["DARAJA_SHORTCODE"]
    timestamp = datetime.now(timezone(timedelta(hours=3))).strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        f"{shortcode}{config['DARAJA_PASSKEY']}{timestamp}".encode("utf-8")
    ).decode("ascii")
    order_reference = f"CRAVY{uuid4().hex[:7].upper()}"
    stk_response = daraja_json_request(
        f"https://{config['api_host']}/mpesa/stkpush/v1/processrequest",
        {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        {
            "BusinessShortCode": shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": os.environ.get("DARAJA_TRANSACTION_TYPE", "CustomerPayBillOnline"),
            "Amount": amount,
            "PartyA": phone,
            "PartyB": shortcode,
            "PhoneNumber": phone,
            "CallBackURL": config["DARAJA_CALLBACK_URL"],
            "AccountReference": order_reference,
            "TransactionDesc": "Cravy Hotel order",
        },
    )
    if str(stk_response.get("ResponseCode", "")) != "0":
        print(f"Daraja rejected STK request: {json.dumps(stk_response)}", flush=True)
        raise RuntimeError(stk_response.get("ResponseDescription") or "Safaricom rejected the payment request.")
    return order_reference, stk_response


class CravyHandler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/menu":
            return self.send_json(200, {"items": MENU})
        if parsed.path == "/api/health":
            return self.send_json(200, {"status": "ok", "service": "Cravy Hotel"})
        if parsed.path == "/pay":
            body = json.dumps({"error": "Select M-Pesa at checkout to start a payment."}).encode("utf-8")
            self.send_response(405)
            self.send_header("Allow", "POST")
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        if parsed.path == "/callback":
            return self.send_json(200, {"status": "waiting", "message": "Safaricom callbacks are received by POST."})
        if parsed.path.startswith("/api/"):
            return self.send_json(404, {"error": "API route not found"})

        relative = unquote(parsed.path).lstrip("/")
        if not relative:
            relative = "index.html"
        requested = (ROOT / relative).resolve()
        if ROOT.resolve() not in requested.parents and requested != ROOT.resolve():
            return self.send_error(403)
        if not requested.is_file():
            return self.send_error(404)
        content_type = mimetypes.guess_type(str(requested))[0] or "application/octet-stream"
        body = requested.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/callback":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.send_json(400, {"error": "Invalid callback length."})
            if length <= 0 or length > 65_536:
                return self.send_json(400, {"error": "Callback body is empty or too large."})
            callback_body = self.rfile.read(length).decode("utf-8", errors="replace")
            print(f"\n--- Safaricom M-Pesa callback ---\n{callback_body}\n--- End callback ---\n", flush=True)
            return self.send_json(200, {"ResultCode": 0, "ResultDesc": "Accepted"})
        if path not in {"/api/orders", "/pay"}:
            return self.send_json(404, {"error": "API route not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 32_768:
                return self.send_json(400, {"error": "Please send a valid order."})
            data = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            return self.send_json(400, {"error": "Order details must be valid JSON."})

        if not isinstance(data, dict):
            return self.send_json(400, {"error": "Order details must be an object."})
        customer = data.get("customer", {})
        if not isinstance(customer, dict):
            return self.send_json(400, {"error": "Customer details must be an object."})
        name = str(customer.get("name", "")).strip()[:80]
        phone = str(customer.get("phone", "")).strip()[:30]
        address = str(customer.get("address", "")).strip()[:240]
        if not name or not phone or not address:
            return self.send_json(400, {"error": "Name, phone number and delivery address are required."})
        submitted_items = data.get("items")
        if not isinstance(submitted_items, list) or not submitted_items:
            return self.send_json(400, {"error": "Your cart is empty."})

        menu_by_id = {item["id"]: item for item in MENU}
        order_items = []
        for requested_item in submitted_items:
            if not isinstance(requested_item, dict):
                return self.send_json(400, {"error": "One of the order items is invalid."})
            item = menu_by_id.get(requested_item.get("id"))
            quantity = requested_item.get("quantity")
            if item is None or not isinstance(quantity, int) or isinstance(quantity, bool) or not 1 <= quantity <= 20:
                return self.send_json(400, {"error": "One of the order items or quantities is invalid."})
            order_items.append(
                {"id": item["id"], "name": item["name"], "price": item["price"], "quantity": quantity}
            )

        total = sum(item["price"] * item["quantity"] for item in order_items)
        if path == "/pay":
            if total > 150_000:
                return self.send_json(400, {"error": "M-Pesa payments are limited to KSh 150,000 per order."})
            normalized_phone = re.sub(r"\D", "", phone)
            if normalized_phone.startswith("0") and len(normalized_phone) == 10:
                normalized_phone = "254" + normalized_phone[1:]
            elif normalized_phone.startswith(("7", "1")):
                normalized_phone = "254" + normalized_phone
            if not re.fullmatch(r"254[71]\d{8}", normalized_phone):
                return self.send_json(400, {"error": "Enter a valid Kenyan M-Pesa number, such as 0712345678."})
            try:
                order_reference, payment_response = start_stk_push(normalized_phone, total)
            except ValueError as error:
                return self.send_json(503, {"error": str(error)})
            except RuntimeError as error:
                return self.send_json(502, {"error": str(error)})
            return self.send_json(
                202,
                {
                    "payment": {
                        "orderReference": order_reference,
                        "checkoutRequestId": payment_response.get("CheckoutRequestID"),
                        "customerMessage": payment_response.get(
                            "CustomerMessage", "Check your phone and enter your M-Pesa PIN."
                        ),
                    }
                },
            )
        order = {
            "id": uuid4().hex[:8].upper(),
            "customer": {"name": name, "phone": phone, "address": address},
            "items": order_items,
            "total": total,
            "currency": "KES",
            "payment": "Pay on delivery",
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "status": "Received",
        }
        ORDERS.append(order)
        print(f"Order {order['id']} received for {name}: KSh {total}", flush=True)
        return self.send_json(201, {"order": order})

    def log_message(self, format_string, *args):
        print(f"{self.address_string()} - {format_string % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), CravyHandler)
    print(f"Cravy Hotel is running at http://localhost:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Cravy Hotel server.", flush=True)
        server.server_close()
