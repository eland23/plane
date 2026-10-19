"""Golden synthetic asset identities; no original records or object keys."""
import base64

FIXTURES = [
    {'key':'fixture-m/inline.png','key_sha256':'aeb82a514507ba86ad2d0679e3c87c543abe64a5198b81de45db63c6ac1784bc','body':base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aY9sAAAAASUVORK5CYII='),'sha256':'cc900c569ef53cccb5c8c476fada89d5a7a6079860e94c8ba658adf4aa2ef0fd','headers':{'ContentType':'image/png','Metadata':{'fixture':'M'}}},
    {'key':'fixture-m/attachment.bin','key_sha256':'b77553ef08f1a5331bd3d392b6ece34c16f2ff48f203edb89318128cc0ca440a','body':b'Plane fixture M\x00\x01\xff','sha256':'afe2651d21f5afd5212e29ea37925ae21634af409aad0a1873850a8cd8d23df5','headers':{'ContentType':'application/octet-stream','Metadata':{'fixture':'M'}}},
]
