# main_app.py
# The host application - evolved and maintained by the Evolution Engine
# This file can be modified autonomously by the Supervisor/Engine agents

import time
import os
import traceback


def calculate_division(a, b):
    """
    Example function. Intentionally has a division-by-zero risk
    to demonstrate the self-fix capability.
    Run: python main_app.py 2> logs/system.log
    Then start the supervisor: python -m evolution.supervisor
    """
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b


def main():
    print("[main_app] System Online.")
    print("[main_app] Evolution Engine is watching...")

    # This area is managed by the Evolution Engine.
    # Agents may inject or modify logic here.

    while True:
        try:
            # --- EVOLVING SECTION ---
            # Agents can inject or modify logic below this line

            print("[main_app] Heartbeat: OK")

            # Uncomment the line below to trigger a ZeroDivisionError
            # and demonstrate the self-healing capability:
            # result = calculate_division(10, 0)

            # ------------------------
            time.sleep(5)

        except Exception as e:
            # Fallback logging if system encounters an error
            os.makedirs("logs", exist_ok=True)
            with open("logs/system.log", "a") as f:
                f.write(f"CRITICAL ERROR: {e}\n")
                f.write(traceback.format_exc())
            print(f"[main_app] Error logged: {e}")
            break


if __name__ == "__main__":
    main()
