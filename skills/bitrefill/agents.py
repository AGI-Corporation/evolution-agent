# skills/bitrefill/agents.py
# BitrefillTradingAgent – enables the Evolution Agent to trade using Bitrefill.
#
# Usage via supervisor skill context:
#
#   context = {
#       "action": "search",
#       "query": "amazon",
#       "country": "US",
#   }
#   agent = BitrefillTradingAgent()
#   result = agent.act(context)
#
# Supported actions: "search", "buy", "status", "list_orders", "balance"

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from evolution.agents import BaseAgent
from skills.bitrefill.api import BitrefillAPIError, BitrefillClient

logger = logging.getLogger(__name__)


class BitrefillTradingAgent(BaseAgent):
    """
    A skill agent that enables autonomous trading on Bitrefill.

    Supports product discovery, order placement, order tracking, and
    account balance queries.  Integrates with the Evolution Agent
    supervisor as a loadable external skill.

    Required environment variables:
        BITREFILL_API_KEY    – your Bitrefill API key (username)
        BITREFILL_API_SECRET – your Bitrefill API secret (password, optional)

    Skill identifier: ``bitrefill/agents``
    """

    SKILL_ID = "bitrefill/agents"
    SKILL_NAME = "Bitrefill Trading Agent"
    CAPABILITIES = [
        "product_search",
        "order_creation",
        "order_tracking",
        "balance_check",
    ]

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        super().__init__("BitrefillTrader")
        self.client = BitrefillClient(api_key=api_key, api_secret=api_secret)
        self._order_history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def act(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a Bitrefill trading action described by *context*.

        Context keys
        ------------
        action (str)
            One of ``"search"``, ``"buy"``, ``"status"``,
            ``"list_orders"``, ``"balance"``.

        For ``"search"``::

            {"action": "search", "query": "netflix", "country": "US"}

        For ``"buy"``::

            {
                "action": "buy",
                "product_id": "netflix-us",
                "value": 25.0,
                "payment_method": "lightning",   # optional, default "bitcoin"
                "currency": "USD",               # optional, default "USD"
                "email": "user@example.com",     # optional
                "phone": "+15551234567",         # optional
                "send_email": False,             # optional
            }

        For ``"status"``::

            {"action": "status", "order_id": "<order-id>"}

        For ``"list_orders"``::

            {"action": "list_orders", "limit": 20, "skip": 0}

        For ``"balance"``::

            {"action": "balance"}

        Returns
        -------
        dict
            ``{"success": bool, "action": str, "result": ..., "error": str}``
        """
        action = context.get("action", "search")
        dispatch = {
            "search": self._handle_search,
            "buy": self._handle_buy,
            "status": self._handle_status,
            "list_orders": self._handle_list_orders,
            "balance": self._handle_balance,
        }
        handler = dispatch.get(action)
        if not handler:
            return {
                "success": False,
                "action": action,
                "error": (
                    f"Unknown action '{action}'. "
                    f"Valid actions: {list(dispatch.keys())}"
                ),
            }
        try:
            result = handler(context)
            return {"success": True, "action": action, "result": result}
        except BitrefillAPIError as exc:
            logger.error("[%s] API error during '%s': %s", self.name, action, exc)
            return {"success": False, "action": action, "error": str(exc)}
        except Exception as exc:
            logger.exception(
                "[%s] Unexpected error during '%s': %s", self.name, action, exc
            )
            return {"success": False, "action": action, "error": str(exc)}

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _handle_search(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        query = context.get("query", "")
        country = context.get("country")
        print(
            f"[{self.name}] Searching Bitrefill products: "
            f"query='{query}' country={country}"
        )
        products = self.client.search_products(query=query, country=country)
        print(f"[{self.name}] Found {len(products)} product(s).")
        return products

    def _handle_buy(self, context: Dict[str, Any]) -> Dict[str, Any]:
        product_id = context.get("product_id")
        value = context.get("value")
        if not product_id or value is None:
            raise ValueError(
                "'product_id' and 'value' are required for action='buy'."
            )
        payment_method = context.get("payment_method", "bitcoin")
        currency = context.get("currency", "USD")
        email = context.get("email")
        phone = context.get("phone")
        send_email = bool(context.get("send_email", False))

        print(
            f"[{self.name}] Placing order: product={product_id}, "
            f"value={value}, payment={payment_method}"
        )
        order = self.client.create_order(
            product_id=product_id,
            value=value,
            currency=currency,
            email=email,
            phone=phone,
            payment_method=payment_method,
            send_email=send_email,
        )
        order_id = order.get("id") or order.get("orderId", "unknown")
        self._order_history.append(
            {
                "order_id": order_id,
                "product_id": product_id,
                "value": value,
                "timestamp": datetime.now().isoformat(),
            }
        )
        print(f"[{self.name}] Order created: {order_id}")
        return order

    def _handle_status(self, context: Dict[str, Any]) -> Dict[str, Any]:
        order_id = context.get("order_id")
        if not order_id:
            raise ValueError("'order_id' is required for action='status'.")
        print(f"[{self.name}] Fetching order status: {order_id}")
        return self.client.get_order(order_id)

    def _handle_list_orders(self, context: Dict[str, Any]) -> Dict[str, Any]:
        limit = int(context.get("limit", 20))
        skip = int(context.get("skip", 0))
        print(f"[{self.name}] Listing orders (limit={limit}, skip={skip})")
        return self.client.get_orders(limit=limit, skip=skip)

    def _handle_balance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        print(f"[{self.name}] Fetching Bitrefill account balance...")
        return self.client.get_balance()

    # ------------------------------------------------------------------
    # Convenience helpers (direct method API)
    # ------------------------------------------------------------------

    def search(self, query: str, country: str = None) -> List[Dict[str, Any]]:
        """Search for Bitrefill products by keyword."""
        return self._handle_search({"query": query, "country": country})

    def buy(
        self,
        product_id: str,
        value: float,
        payment_method: str = "bitcoin",
        email: str = None,
        phone: str = None,
        currency: str = "USD",
        send_email: bool = False,
    ) -> Dict[str, Any]:
        """Place a Bitrefill order and return the order details."""
        return self._handle_buy(
            {
                "product_id": product_id,
                "value": value,
                "payment_method": payment_method,
                "currency": currency,
                "email": email,
                "phone": phone,
                "send_email": send_email,
            }
        )

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Retrieve the status of an existing order."""
        return self._handle_status({"order_id": order_id})

    def order_history(self) -> List[Dict[str, Any]]:
        """Return the in-session order history (not persisted across restarts)."""
        return list(self._order_history)
