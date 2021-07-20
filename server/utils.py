import hmac
import hashlib


def hmac_sha256_digest(key, data):
    assert (isinstance(key, str))
    assert (isinstance(data, str))
    return hmac.new(key.encode(), msg=data.encode(),
                    digestmod=hashlib.sha256).hexdigest()
