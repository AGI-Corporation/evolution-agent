# skills/x402/client.py
# x402 protocol client – HTTP-native stablecoin micropayments for AI agents.
#
# Protocol overview (https://www.x402.org / https://github.com/coinbase/x402):
#   1. Client makes a normal HTTP request.
#   2. Server responds 402 with a JSON payment-requirements body.
#   3. Client constructs a signed payment authorization (EIP-3009 on EVM chains
#      or similar on Solana) and retries the request with the `X-PAYMENT` header.
#   4. Server (or a payment facilitator) validates the proof and returns the
#      protected resource.
#
# Simulation mode: when no real wallet / web3 library is present the client
# operates in simulation mode, logging payment intentions without broadcasting
# real on-chain transactions.  This lets the Evolution Agent reason about
# x402-gated resources without requiring live wallet credentials.

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
    _requests_available = True
except ImportError:
    requests = None  # type: ignore
    _requests_available = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

X402_PAYMENT_HEADER = "X-PAYMENT"
X402_PAYMENT_RESPONSE_HEADER = "X-PAYMENT-RESPONSE"
X402_VERSION = "1"
# Grace period (seconds) subtracted from valid_after to account for clock skew
VALID_AFTER_GRACE_SECONDS = 5

# Supported EVM network names → chain-id
SUPPORTED_NETWORKS: Dict[str, int] = {
    "base": 8453,
    "base-sepolia": 84532,
    "ethereum": 1,
    "polygon": 137,
}

# Well-known stablecoin contract addresses (USDC on each network)
USDC_ADDRESSES: Dict[str, str] = {
    "base": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
    "base-sepolia": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    "ethereum": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "polygon": "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359",
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class X402Error(Exception):
    """Base exception for x402 protocol errors."""


class X402PaymentRequired(X402Error):
    """Raised when a server returns HTTP 402 and payment is required."""

    def __init__(self, url: str, requirements: Dict[str, Any]):
        self.url = url
        self.requirements = requirements
        accepts = requirements.get("accepts", [])
        super().__init__(
            f"HTTP 402 Payment Required for {url}. "
            f"{len(accepts)} payment option(s) available."
        )


class X402WalletError(X402Error):
    """Raised when wallet credentials are missing or signing fails."""


# ---------------------------------------------------------------------------
# PaymentRequirements parser
# ---------------------------------------------------------------------------

class PaymentRequirements:
    """
    Parsed representation of the server's payment requirements (HTTP 402 body).

    Schema (x402 spec)::

        {
            "accepts": [
                {
                    "scheme": "exact",
                    "network": "base",
                    "maxAmountRequired": "1000000",   // in token base units (e.g. 1 USDC = 1 000 000)
                    "resource": "/api/data",
                    "description": "Access to premium data",
                    "mimeType": "application/json",
                    "payTo": "0x...",
                    "maxTimeoutSeconds": 60,
                    "asset": "0x833589...",            // token contract address
                    "extra": {"name": "USD Coin", "version": "2"}
                }
            ],
            "error": "X-PAYMENT header required"
        }
    """

    def __init__(self, raw: Dict[str, Any]):
        self.raw = raw
        self.accepts: List[Dict[str, Any]] = raw.get("accepts", [])
        self.error_message: str = raw.get("error", "Payment required")

    def best_option(
        self, preferred_network: str = "base"
    ) -> Optional[Dict[str, Any]]:
        """
        Return the most suitable payment option.

        Preference order:
          1. Exact match on ``preferred_network``
          2. First available option
        """
        for opt in self.accepts:
            if opt.get("network", "").lower() == preferred_network.lower():
                return opt
        return self.accepts[0] if self.accepts else None

    @classmethod
    def from_response(cls, response_body: bytes) -> "PaymentRequirements":
        try:
            data = json.loads(response_body)
        except (ValueError, TypeError) as exc:
            raise X402Error(f"Could not parse 402 payment requirements: {exc}") from exc
        return cls(data)


# ---------------------------------------------------------------------------
# Wallet / signer (simulation-safe)
# ---------------------------------------------------------------------------

class X402Wallet:
    """
    Thin wrapper around wallet credentials.

    In simulation mode (no private key provided) the wallet generates
    deterministic *fake* authorization tokens so the rest of the agent
    pipeline can be exercised without live on-chain transactions.

    Real mode: provide a hex private key via ``X402_PRIVATE_KEY`` env var or
    the constructor.  The wallet will construct a proper EIP-3009
    ``transferWithAuthorization`` payload.

    EIP-3009 references:
    - https://eips.ethereum.org/EIPS/eip-3009
    - https://github.com/coinbase/x402/tree/main/python
    """

    def __init__(
        self,
        private_key: Optional[str] = None,
        address: Optional[str] = None,
    ):
        self.private_key = private_key or os.getenv("X402_PRIVATE_KEY", "")
        self.address = address or os.getenv("X402_WALLET_ADDRESS", "")
        self.simulation_mode = not bool(self.private_key and self.address)

        if self.simulation_mode:
            logger.warning(
                "[x402] Wallet running in SIMULATION mode. "
                "No real on-chain payments will be made. "
                "Set X402_PRIVATE_KEY and X402_WALLET_ADDRESS to enable real payments."
            )

    def build_payment_header(
        self, option: Dict[str, Any], resource_url: str
    ) -> str:
        """
        Construct the value for the ``X-PAYMENT`` header.

        Real mode: builds a signed EIP-3009 ``transferWithAuthorization``
        payload, base64-encoded as required by the x402 spec.

        Simulation mode: builds a structurally-valid but unsigned payload
        so downstream logic (parsing, logging, memory) can be exercised.
        """
        nonce = str(uuid.uuid4())
        valid_after = int(time.time()) - VALID_AFTER_GRACE_SECONDS
        valid_before = valid_after + int(option.get("maxTimeoutSeconds", 60))

        payload: Dict[str, Any] = {
            "x402Version": X402_VERSION,
            "scheme": option.get("scheme", "exact"),
            "network": option.get("network", "base"),
            "payload": {
                "signature": self._sign(option, nonce, valid_after, valid_before),
                "authorization": {
                    "from": self.address or "0x0000000000000000000000000000000000000000",
                    "to": option.get("payTo", ""),
                    "value": option.get("maxAmountRequired", "0"),
                    "validAfter": str(valid_after),
                    "validBefore": str(valid_before),
                    "nonce": nonce,
                },
            },
        }
        import base64
        return base64.b64encode(json.dumps(payload).encode()).decode()

    def _sign(
        self,
        option: Dict[str, Any],
        nonce: str,
        valid_after: int,
        valid_before: int,
    ) -> str:
        """
        Produce a signature string.

        Real: would use eth_account to sign an EIP-712 typed-data hash.
        Simulation: returns a clearly-marked fake signature.
        """
        if self.simulation_mode:
            return f"SIMULATION_SIG_{nonce[:8]}"

        # Real signing path (requires eth_account – optional dependency)
        try:
            from eth_account import Account
            from eth_account.structured_data.hashing import hash_domain

            chain_id = SUPPORTED_NETWORKS.get(
                option.get("network", "base").lower(), 8453
            )
            asset = option.get("asset", USDC_ADDRESSES.get("base", ""))

            # EIP-712 domain per EIP-3009 / x402 spec
            domain = {
                "name": option.get("extra", {}).get("name", "USD Coin"),
                "version": option.get("extra", {}).get("version", "2"),
                "chainId": chain_id,
                "verifyingContract": asset,
            }
            message = {
                "from": self.address,
                "to": option.get("payTo", ""),
                "value": int(option.get("maxAmountRequired", "0")),
                "validAfter": valid_after,
                "validBefore": valid_before,
                "nonce": uuid.UUID(nonce).bytes,
            }
            typed_data = {
                "types": {
                    "EIP712Domain": [
                        {"name": "name", "type": "string"},
                        {"name": "version", "type": "string"},
                        {"name": "chainId", "type": "uint256"},
                        {"name": "verifyingContract", "type": "address"},
                    ],
                    "TransferWithAuthorization": [
                        {"name": "from", "type": "address"},
                        {"name": "to", "type": "address"},
                        {"name": "value", "type": "uint256"},
                        {"name": "validAfter", "type": "uint256"},
                        {"name": "validBefore", "type": "uint256"},
                        {"name": "nonce", "type": "bytes32"},
                    ],
                },
                "primaryType": "TransferWithAuthorization",
                "domain": domain,
                "message": message,
            }
            signed = Account.sign_typed_data(
                self.private_key, full_message=typed_data
            )
            return signed.signature.hex()
        except ImportError:
            logger.warning(
                "[x402] eth_account not installed. Falling back to simulation signature. "
                "Install with: pip install eth-account"
            )
            return f"SIMULATION_SIG_{nonce[:8]}"
        except Exception as exc:
            raise X402WalletError(f"Failed to sign payment authorization: {exc}") from exc


# ---------------------------------------------------------------------------
# X402Client
# ---------------------------------------------------------------------------

class X402Client:
    """
    HTTP client that transparently handles x402 payment flows.

    Usage::

        wallet = X402Wallet()          # reads X402_PRIVATE_KEY / X402_WALLET_ADDRESS
        client = X402Client(wallet)

        # Fetches resource, paying automatically if a 402 is returned
        response = client.fetch("https://api.example.com/premium-data")
        print(response["data"])

    The client keeps a payment ledger for the current session so the
    Evolution Agent can reason about spending and audit its decisions.
    """

    def __init__(
        self,
        wallet: Optional[X402Wallet] = None,
        preferred_network: str = "base",
        max_auto_pay_usdc: float = 1.0,
    ):
        if not _requests_available:
            raise ImportError(
                "The 'requests' library is required. "
                "Install with: pip install requests"
            )
        self.wallet = wallet or X402Wallet()
        self.preferred_network = preferred_network
        # Maximum USDC amount (human-readable) the agent will auto-pay per request
        self.max_auto_pay_usdc = max_auto_pay_usdc
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self._payment_ledger: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(
        self,
        url: str,
        method: str = "GET",
        auto_pay: bool = True,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Fetch a URL, automatically handling x402 payment if required.

        Args:
            url:       Target URL.
            method:    HTTP method (default ``"GET"``).
            auto_pay:  If ``True`` (default), automatically attempt payment
                       when a 402 is received.  Set to ``False`` to raise
                       :exc:`X402PaymentRequired` instead.
            headers:   Additional request headers.
            **kwargs:  Extra keyword args forwarded to ``requests.Session.request``.

        Returns:
            A dict with keys ``"status_code"``, ``"headers"``, ``"body"``,
            ``"paid"``, ``"payment_record"`` (or ``None``).

        Raises:
            X402PaymentRequired: If ``auto_pay=False`` and server returns 402.
            X402Error:           On protocol or payment errors.
        """
        merged_headers = dict(headers or {})
        response = self._request(method, url, headers=merged_headers, **kwargs)

        if response.status_code != 402:
            return self._wrap_response(response, paid=False, payment_record=None)

        # --- 402 handling ---
        requirements = PaymentRequirements.from_response(response.content)

        if not auto_pay:
            raise X402PaymentRequired(url, requirements.raw)

        option = requirements.best_option(self.preferred_network)
        if option is None:
            raise X402Error(
                f"No acceptable payment option found for {url}. "
                f"Available: {[o.get('network') for o in requirements.accepts]}"
            )

        # Guard against overspending
        amount_base_units = int(option.get("maxAmountRequired", "0"))
        amount_usdc = amount_base_units / 1_000_000
        if amount_usdc > self.max_auto_pay_usdc:
            raise X402Error(
                f"Payment amount {amount_usdc:.6f} USDC exceeds "
                f"auto-pay limit of {self.max_auto_pay_usdc:.6f} USDC for {url}."
            )

        payment_header = self.wallet.build_payment_header(option, url)
        payment_record = self._record_payment(url, option, amount_usdc)

        # Retry with payment proof
        merged_headers[X402_PAYMENT_HEADER] = payment_header
        retried = self._request(method, url, headers=merged_headers, **kwargs)

        # Capture facilitator response if present
        payment_response = retried.headers.get(X402_PAYMENT_RESPONSE_HEADER)
        if payment_response:
            payment_record["facilitator_response"] = payment_response

        logger.info(
            "[x402] Paid %.6f USDC on %s for %s (simulation=%s)",
            amount_usdc,
            option.get("network"),
            url,
            self.wallet.simulation_mode,
        )
        return self._wrap_response(retried, paid=True, payment_record=payment_record)

    def get_payment_ledger(self) -> List[Dict[str, Any]]:
        """Return the session payment ledger (all payments made this run)."""
        return list(self._payment_ledger)

    def total_spent_usdc(self) -> float:
        """Sum of all USDC paid in this session."""
        return sum(p.get("amount_usdc", 0.0) for p in self._payment_ledger)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, url: str, **kwargs) -> "requests.Response":
        try:
            return self.session.request(method, url, timeout=30, **kwargs)
        except requests.RequestException as exc:
            raise X402Error(f"Network error: {exc}") from exc

    def _record_payment(
        self, url: str, option: Dict[str, Any], amount_usdc: float
    ) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "url": url,
            "network": option.get("network"),
            "asset": option.get("asset"),
            "pay_to": option.get("payTo"),
            "amount_usdc": amount_usdc,
            "simulation": self.wallet.simulation_mode,
        }
        self._payment_ledger.append(record)
        return record

    @staticmethod
    def _wrap_response(
        response: "requests.Response",
        *,
        paid: bool,
        payment_record: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        try:
            body = response.json()
        except (ValueError, AttributeError):
            body = response.text if hasattr(response, "text") else None
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": body,
            "paid": paid,
            "payment_record": payment_record,
        }
