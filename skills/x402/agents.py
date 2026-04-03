# skills/x402/agents.py
# X402PaymentAgent – enables the Evolution Agent to interact with x402-gated resources.
#
# The x402 protocol lets HTTP servers require micropayments (usually USDC on Base)
# before returning a response.  This agent handles the full payment flow autonomously:
#
#   context = {"action": "fetch", "url": "https://api.example.com/premium"}
#   agent = X402PaymentAgent()
#   result = agent.act(context)
#
# Supported actions:
#   fetch        – GET/POST a URL, paying automatically if a 402 is returned
#   pay          – pay a resource explicitly (forced payment, skip auto-pay guard)
#   status       – return wallet and ledger summary
#   history      – return the session payment ledger
#   check        – probe a URL for x402 requirements without paying

import logging
from typing import Any, Dict, List

from evolution.agents import BaseAgent
from skills.x402.client import (
    X402Client,
    X402Error,
    X402PaymentRequired,
    X402Wallet,
    PaymentRequirements,
)

logger = logging.getLogger(__name__)


class X402PaymentAgent(BaseAgent):
    """
    Skill agent for autonomous x402 micropayment flows.

    The agent wraps an :class:`~skills.x402.client.X402Client` and exposes its
    capabilities through the standard ``act(context)`` interface so the Evolution
    Agent supervisor and NANDA bridge can dispatch payment tasks without knowing
    the underlying protocol details.

    Required environment variables (for real on-chain payments):
        X402_PRIVATE_KEY     – hex-encoded EVM private key
        X402_WALLET_ADDRESS  – 0x-prefixed EVM address matching the private key

    If these are absent, the agent runs in **simulation mode**: it performs the
    full x402 handshake and records payment intentions without broadcasting real
    on-chain transactions.

    Skill identifier: ``x402/agents``
    """

    SKILL_ID = "x402/agents"
    SKILL_NAME = "x402 Payment Agent"
    CAPABILITIES = [
        "x402_fetch",
        "x402_pay",
        "x402_check",
        "payment_history",
        "wallet_status",
    ]

    def __init__(
        self,
        private_key: str = None,
        wallet_address: str = None,
        preferred_network: str = "base",
        max_auto_pay_usdc: float = 1.0,
    ):
        super().__init__("X402Agent")
        wallet = X402Wallet(private_key=private_key, address=wallet_address)
        self.client = X402Client(
            wallet=wallet,
            preferred_network=preferred_network,
            max_auto_pay_usdc=max_auto_pay_usdc,
        )

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def act(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an x402 payment action described by *context*.

        Context keys
        ------------
        action (str)
            One of ``"fetch"``, ``"pay"``, ``"status"``, ``"history"``,
            ``"check"``.

        For ``"fetch"``::

            {
                "action": "fetch",
                "url": "https://api.example.com/premium",
                "method": "GET",          # optional, default "GET"
                "headers": {},            # optional extra headers
                "max_usdc": 0.50,        # optional per-request override
            }

        For ``"pay"``::

            {
                "action": "pay",
                "url": "https://api.example.com/resource",
                "method": "GET",
            }

        For ``"check"``::

            {"action": "check", "url": "https://api.example.com/resource"}

        For ``"status"``::

            {"action": "status"}

        For ``"history"``::

            {"action": "history"}

        Returns
        -------
        dict
            ``{"success": bool, "action": str, "result": ..., "error": str}``
        """
        action = context.get("action", "fetch")
        dispatch = {
            "fetch": self._handle_fetch,
            "pay": self._handle_pay,
            "check": self._handle_check,
            "status": self._handle_status,
            "history": self._handle_history,
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
        except X402PaymentRequired as exc:
            logger.warning("[%s] Payment required but auto_pay=False: %s", self.name, exc)
            return {
                "success": False,
                "action": action,
                "error": str(exc),
                "payment_requirements": exc.requirements,
            }
        except X402Error as exc:
            logger.error("[%s] x402 error during '%s': %s", self.name, action, exc)
            return {"success": False, "action": action, "error": str(exc)}
        except Exception as exc:
            logger.exception(
                "[%s] Unexpected error during '%s': %s", self.name, action, exc
            )
            return {"success": False, "action": action, "error": str(exc)}

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _handle_fetch(self, context: Dict[str, Any]) -> Dict[str, Any]:
        url = context.get("url")
        if not url:
            raise ValueError("'url' is required for action='fetch'.")
        method = context.get("method", "GET").upper()
        extra_headers = context.get("headers", {})
        max_usdc = context.get("max_usdc")

        # Per-request auto-pay limit override
        original_limit = self.client.max_auto_pay_usdc
        if max_usdc is not None:
            self.client.max_auto_pay_usdc = float(max_usdc)

        try:
            print(f"[{self.name}] Fetching (x402-aware): {method} {url}")
            result = self.client.fetch(
                url=url, method=method, auto_pay=True, headers=extra_headers
            )
            paid_msg = (
                f" (paid {result['payment_record']['amount_usdc']:.6f} USDC)"
                if result.get("paid") and result.get("payment_record")
                else " (no payment required)"
            )
            print(f"[{self.name}] Fetch complete{paid_msg} – status {result['status_code']}")
            return result
        finally:
            self.client.max_auto_pay_usdc = original_limit

    def _handle_pay(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Unconditionally attempt a paid fetch (bypasses auto_pay guard)."""
        url = context.get("url")
        if not url:
            raise ValueError("'url' is required for action='pay'.")
        method = context.get("method", "GET").upper()
        print(f"[{self.name}] Forced payment fetch: {method} {url}")
        # Use a very high limit so the payment always proceeds
        original_limit = self.client.max_auto_pay_usdc
        self.client.max_auto_pay_usdc = float("inf")
        try:
            return self.client.fetch(url=url, method=method, auto_pay=True)
        finally:
            self.client.max_auto_pay_usdc = original_limit

    def _handle_check(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Probe a URL for x402 requirements without paying."""
        url = context.get("url")
        if not url:
            raise ValueError("'url' is required for action='check'.")
        print(f"[{self.name}] Checking x402 requirements: {url}")
        result = self.client.fetch(url=url, auto_pay=False)
        # auto_pay=False raises X402PaymentRequired on 402 – if we get here,
        # the resource is either free or returned a different error.
        return {
            "x402_required": False,
            "status_code": result["status_code"],
            "body": result["body"],
        }

    def _handle_status(self, _context: Dict[str, Any]) -> Dict[str, Any]:
        """Return wallet and session payment summary."""
        print(f"[{self.name}] Fetching x402 wallet status...")
        wallet = self.client.wallet
        return {
            "simulation_mode": wallet.simulation_mode,
            "wallet_address": wallet.address or "(not configured)",
            "preferred_network": self.client.preferred_network,
            "max_auto_pay_usdc": self.client.max_auto_pay_usdc,
            "session_payments": len(self.client.get_payment_ledger()),
            "session_total_usdc": round(self.client.total_spent_usdc(), 6),
        }

    def _handle_history(self, _context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return the full session payment ledger."""
        print(f"[{self.name}] Fetching payment history...")
        return self.client.get_payment_ledger()

    # ------------------------------------------------------------------
    # Convenience helpers (direct method API)
    # ------------------------------------------------------------------

    def fetch(self, url: str, method: str = "GET") -> Dict[str, Any]:
        """Fetch a URL, auto-paying via x402 if required."""
        return self._handle_fetch({"url": url, "method": method})

    def check(self, url: str) -> Dict[str, Any]:
        """Check whether a URL requires x402 payment without paying."""
        try:
            return self._handle_check({"url": url})
        except X402PaymentRequired as exc:
            return {
                "x402_required": True,
                "url": url,
                "payment_requirements": exc.requirements,
            }

    def status(self) -> Dict[str, Any]:
        """Return wallet status summary."""
        return self._handle_status({})

    def payment_history(self) -> List[Dict[str, Any]]:
        """Return the session payment ledger."""
        return self._handle_history({})
