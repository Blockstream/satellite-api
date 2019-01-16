require 'openssl'

def hash_hmac(digest, key, data)
  d = OpenSSL::Digest.new(digest)
  OpenSSL::HMAC.hexdigest(d, key, data)
end
