# Cravy Hotel

## Run locally

From this folder, run:

```powershell
py server.py
```

The site runs at `http://localhost:8000`.
If port 8000 is already in use, choose another port before starting the server:

```powershell
$env:PORT = "8001"
py server.py
```

## Configure Daraja M-Pesa

Create a Daraja app and set its credentials in the PowerShell window where you
will start the server. Do not put credentials in frontend files or commit them.

```powershell
$env:DARAJA_CONSUMER_KEY = "<your consumer key>"
$env:DARAJA_CONSUMER_SECRET = "<your consumer secret>"
$env:DARAJA_SHORTCODE = "<your shortcode>"
$env:DARAJA_PASSKEY = "<your passkey>"
$env:DARAJA_CALLBACK_URL = "https://<your-public-host>/callback"
$env:DARAJA_ENV = "sandbox"
py server.py
```

`DARAJA_ENV` can be `sandbox` or `production`. The optional
`DARAJA_TRANSACTION_TYPE` defaults to `CustomerPayBillOnline`; set it to the
transaction type provided for your Daraja shortcode if different.

Select **M-Pesa prompt** in checkout to send a `POST /pay` request. The server
gets a short-lived Daraja access token and sends an STK Push for the server-
calculated KES order total. Safaricom sends its result to `POST /callback`,
which prints the raw callback body in the server terminal. The callback handler
only logs and acknowledges the message; it does not verify or store payment
status.

Safaricom cannot reach `localhost`. Use a publicly reachable HTTPS callback URL
while developing, or deploy the server with HTTPS. Menu prices currently use
the requested placeholder conversion of KSh 130 per former USD.
