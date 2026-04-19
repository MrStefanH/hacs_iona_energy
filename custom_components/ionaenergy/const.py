"""Constants for the iONA Energy integration."""

DOMAIN = "ionaenergy"

# Authentication
AUTH_URL = "https://webapp.iona-energy.com/auth"

# Dynamic tariff (SDACe hub) — same Bearer as N2G where supported
GROSS_SHARE_URL = (
    "https://mvp.sdacehub.de/dynamic-tariff-be/prices/gross_share"
)

# EEX Day-Ahead Spot (EnviaM shared API) — Bearer + x-identity
SPOT_PRICES_URL = (
    "https://api.enviam.de/shared/v2/enviaM/service/eex/v1/spotPrices"
)
SPOT_PRICES_IDENTITY_HEADER = "net2grid"
# EnviaM query value (e.g. today, twodays) — lowercase per API examples
SPOT_PRICES_TIME_SLICE = "twodays"

# Configuration keys
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EXPIRES_IN = "expires_in"
