# skills/bitrefill/api.py
# Bitrefill API v1 client – product catalog, order creation, and order tracking.

import os
import logging
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore

logger = logging.getLogger(__name__)

BITREFILL_API_BASE = "https://api.bitrefill.com/v1"


class BitrefillAPIError(Exception):
    """Raised when the Bitrefill API returns an error or a network failure occurs."""

    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


class BitrefillClient:
    """
    HTTP client for the Bitrefill API v1.

    Authentication is via HTTP Basic Auth using an API key (username) and an
    optional API secret (password). Credentials are read from the environment
    variables BITREFILL_API_KEY and BITREFILL_API_SECRET, or passed directly.

    Example::

        client = BitrefillClient()
        products = client.search_products("amazon", country="US")
        order = client.create_order("amazon-us", 25.0, payment_method="lightning")
    """

    def __init__(self, api_key: str = None, api_secret: str = None):
        if requests is None:
            raise ImportError(
                "The 'requests' library is required. Install it with: pip install requests"
            )
        self.api_key = api_key or os.getenv("BITREFILL_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BITREFILL_API_SECRET", "")
        self.base_url = BITREFILL_API_BASE

        self.session = requests.Session()
        if self.api_key:
            self.session.auth = (self.api_key, self.api_secret)
        self.session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            body: dict = {}
            try:
                body = exc.response.json()
            except Exception:
                pass
            raise BitrefillAPIError(
                f"Bitrefill API error {exc.response.status_code}: "
                f"{body.get('message', str(exc))}",
                status_code=exc.response.status_code,
                response=body,
            ) from exc
        except requests.RequestException as exc:
            raise BitrefillAPIError(
                f"Network error contacting Bitrefill API: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Product catalog
    # ------------------------------------------------------------------

    def get_products(
        self,
        country: str = None,
        language: str = "en",
        category: str = None,
        query: str = None,
        limit: int = 20,
        skip: int = 0,
    ) -> Dict[str, Any]:
        """
        Retrieve the Bitrefill product catalog (gift cards, mobile top-ups, etc.).

        Args:
            country:  ISO 3166-1 alpha-2 country code (e.g. ``"US"``, ``"GB"``).
            language: Language for product names (default ``"en"``).
            category: Filter by category slug (e.g. ``"gaming"``, ``"food-and-drink"``).
            query:    Free-text search term.
            limit:    Maximum number of results per page (default 20).
            skip:     Pagination offset (default 0).

        Returns:
            dict with a ``"products"`` list and pagination metadata.
        """
        params: Dict[str, Any] = {"limit": limit, "skip": skip, "language": language}
        if country:
            params["country"] = country
        if category:
            params["category"] = category
        if query:
            params["query"] = query
        return self._request("GET", "/products", params=params)

    def get_product(self, product_id: str) -> Dict[str, Any]:
        """
        Get details for a specific product including available denominations.

        Args:
            product_id: The Bitrefill product identifier / slug.

        Returns:
            Product detail dict.
        """
        return self._request("GET", f"/products/{product_id}")

    def search_products(
        self, query: str, country: str = None
    ) -> List[Dict[str, Any]]:
        """
        Search for products by name or keyword and return the matching list.

        Args:
            query:   Search term (e.g. ``"amazon"``, ``"netflix"``, ``"visa"``).
            country: Optional ISO country filter.

        Returns:
            List of matching product dicts.
        """
        result = self.get_products(query=query, country=country, limit=50)
        return result.get("products", [])

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def create_order(
        self,
        product_id: str,
        value: float,
        currency: str = "USD",
        email: str = None,
        phone: str = None,
        payment_method: str = "bitcoin",
        send_email: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a Bitrefill order for a gift card or mobile top-up.

        Args:
            product_id:     Product slug obtained from :meth:`get_products`.
            value:          Denomination value in the product's listed currency.
            currency:       Fiat currency code for the denomination (default ``"USD"``).
            email:          Recipient email address (for email-delivery products).
            phone:          Recipient phone number (for phone top-up products).
            payment_method: Crypto payment method – ``"bitcoin"``, ``"ethereum"``,
                            ``"litecoin"``, ``"usdt"``, or ``"lightning"``
                            (default ``"bitcoin"``).
            send_email:     Whether to email the gift card to the recipient.

        Returns:
            Order dict including payment address/invoice and order ID.
        """
        payload: Dict[str, Any] = {
            "products": [{"id": product_id, "value": value}],
            "paymentCurrency": payment_method,
            "currency": currency,
            "sendEmail": send_email,
        }
        if email:
            payload["email"] = email
        if phone:
            payload["phone"] = phone
        return self._request("POST", "/order", json=payload)

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Retrieve the status and details of an existing order.

        Args:
            order_id: The order identifier returned by :meth:`create_order`.

        Returns:
            Order status dict.
        """
        return self._request("GET", f"/order/{order_id}")

    def get_orders(self, limit: int = 20, skip: int = 0) -> Dict[str, Any]:
        """
        List past orders for the authenticated account.

        Args:
            limit: Maximum number of results per page (default 20).
            skip:  Pagination offset (default 0).

        Returns:
            dict with an ``"orders"`` list.
        """
        return self._request("GET", "/orders", params={"limit": limit, "skip": skip})

    def get_balance(self) -> Dict[str, Any]:
        """
        Get the current account balance (requires authenticated API key).

        Returns:
            Balance dict with available credit information.
        """
        return self._request("GET", "/account/balance")
