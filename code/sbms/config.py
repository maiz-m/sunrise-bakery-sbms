"""Database settings. Override with environment variables on each member's machine."""
import os

DB_HOST = os.environ.get("SBMS_DB_HOST", "localhost")
DB_PORT = int(os.environ.get("SBMS_DB_PORT", "3306"))
DB_USER = os.environ.get("SBMS_DB_USER", "root")
DB_PASSWORD = os.environ.get("SBMS_DB_PASSWORD", "")
DB_NAME = os.environ.get("SBMS_DB_NAME", "sbms")

# Warnings
NEAR_EXPIRY_DAYS = 3        # ingredient batches expiring within this many days are flagged
LOW_PRODUCT_STOCK = 5       # shown as "Low" on the product catalogue

# Account lockout
MAX_FAILED_LOGINS = 5       # wrong passwords in a row before the account is locked
LOCKOUT_MINUTES = 15        # how long the lock lasts (an administrator can unlock sooner)
