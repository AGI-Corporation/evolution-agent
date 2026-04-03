# skills/x402/__init__.py
"""
x402 payment skill for the Evolution Agent.

Implements the x402 protocol (https://www.x402.org) – the HTTP-native stablecoin
micropayment standard for autonomous AI agents.  When a server returns HTTP 402,
the agent automatically constructs a signed payment authorization (EIP-3009 on
EVM chains) and retries the request.

Skill ID: x402/agents

Quickstart::

    from skills.x402 import X402PaymentAgent

    agent = X402PaymentAgent()          # simulation mode if no wallet env vars
    result = agent.fetch("https://api.example.com/premium")
    print(result["body"])

Environment variables:
    X402_PRIVATE_KEY     – hex EVM private key (omit for simulation mode)
    X402_WALLET_ADDRESS  – 0x EVM address matching the private key
"""

from skills.x402.agents import X402PaymentAgent
from skills.x402.client import (
    X402Client,
    X402Error,
    X402PaymentRequired,
    X402Wallet,
    X402WalletError,
    PaymentRequirements,
)

__all__ = [
    "X402PaymentAgent",
    "X402Client",
    "X402Wallet",
    "X402Error",
    "X402PaymentRequired",
    "X402WalletError",
    "PaymentRequirements",
]
