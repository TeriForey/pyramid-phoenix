from OpenSSL import crypto
import base64
import urllib

def make_cert_req(access_token):
    key_pair = crypto.PKey()
    key_pair.generate_key(crypto.TYPE_RSA, 2048)

    cert_req = crypto.X509Req()

    # Create public key object
    cert_req.set_pubkey(key_pair)

    # Add the public key to the request
    cert_req.sign(key_pair, 'md5')

    der_cert_req = crypto.dump_certificate_request(crypto.FILETYPE_ASN1,
                                                   cert_req)

    encoded_cert_req = base64.b64encode(der_cert_req)

    header = 'Authorization: Bearer %s' % access_token
    post_data = urllib.urlencode({'certificate_request': encoded_cert_req})

    return header, post_data

if __name__ == '__main__':
    import uuid
    header, post_data = make_cert_req(uuid.uuid4())

    print(header)
    print(post_data)
