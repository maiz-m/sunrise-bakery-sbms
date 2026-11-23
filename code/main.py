"""Start the Sunrise Bakery Management System.

    python main.py
"""
import logging

from sbms.ui.app import main

if __name__ == "__main__":
    logging.basicConfig(filename="sbms.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
