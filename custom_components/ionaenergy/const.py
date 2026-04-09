"""Constants for the iONA Energy integration."""

DOMAIN = "ionaenergy"

# Authentication
AUTH_URL = "https://webapp.iona-energy.com/auth"

# Dynamic tariff (SDACe hub) — same Bearer as N2G where supported
GROSS_SHARE_URL = (
    "https://mvp.sdacehub.de/dynamic-tariff-be/prices/gross_share"
)

# Configuration keys
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EXPIRES_IN = "expires_in"
