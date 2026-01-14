import struct

# --- Protocol Constants ---
MAGIC_COOKIE = 0xabcddcba
MSG_OFFER = 0x2
MSG_REQUEST = 0x3
MSG_PAYLOAD = 0x4


# --- Helper Functions ---

def pad_string(text, length=32):
    """Encodes text to bytes and pads with null bytes to fixed length."""
    encoded = text.encode('utf-8')
    if len(encoded) > length:
        return encoded[:length]  # Truncate
    return encoded + b'\x00' * (length - len(encoded))  # Pad


def decode_string(data):
    """Decodes bytes to string, removing null padding."""
    return data.decode('utf-8').rstrip('\x00')


# --- Packet Packing/Unpacking Functions ---

def pack_offer(server_port, server_name):
    """
    Format: Magic(4) + Type(1) + Port(2) + Name(32)
    Struct: ! I B H 32s
    """
    padded_name = pad_string(server_name)
    return struct.pack('!IBH32s', MAGIC_COOKIE, MSG_OFFER, server_port, padded_name)


def unpack_offer(data):
    """Returns (server_port, server_name) or None if invalid"""
    if len(data) != 39:
        return None

    try:
        cookie, msg_type, port, name_bytes = struct.unpack('!IBH32s', data)
        if cookie != MAGIC_COOKIE or msg_type != MSG_OFFER:
            return None
        return port, decode_string(name_bytes)
    except struct.error:
        return None


def pack_request(num_rounds, client_name):
    """
    Format: Magic(4) + Type(1) + Rounds(1) + Name(32)
    Struct: ! I B B 32s
    """
    padded_name = pad_string(client_name)
    return struct.pack('!IBB32s', MAGIC_COOKIE, MSG_REQUEST, num_rounds, padded_name)


def unpack_request(data):
    """Returns (num_rounds, client_name) or None"""
    if len(data) != 38:
        return None

    try:
        cookie, msg_type, rounds, name_bytes = struct.unpack('!IBB32s', data)
        if cookie != MAGIC_COOKIE or msg_type != MSG_REQUEST:
            return None
        return rounds, decode_string(name_bytes)
    except struct.error:
        return None


def pack_client_payload(decision):
    """
    Format: Magic(4) + Type(1) + Decision(5)
    Struct: ! I B 5s
    """
    return struct.pack('!IB5s', MAGIC_COOKIE, MSG_PAYLOAD, decision.encode('utf-8'))


def unpack_client_payload(data):
    """Returns decision string or None"""
    if len(data) != 10:
        return None

    try:
        cookie, msg_type, decision_bytes = struct.unpack('!IB5s', data)
        if cookie != MAGIC_COOKIE or msg_type != MSG_PAYLOAD:
            return None
        return decision_bytes.decode('utf-8')
    except struct.error:
        return None


def pack_server_payload(result, card_rank, card_suit):
    """
    Format: Magic(4) + Type(1) + Result(1) + CardRank(2) + CardSuit(1)
    Struct: ! I B B H B
    """
    return struct.pack('!IBBHB', MAGIC_COOKIE, MSG_PAYLOAD, result, card_rank, card_suit)


def unpack_server_payload(data):
    """Returns (result, card_rank, card_suit)"""
    if len(data) != 9:
        return None

    try:
        cookie, msg_type, result, rank, suit = struct.unpack('!IBBHB', data)
        if cookie != MAGIC_COOKIE or msg_type != MSG_PAYLOAD:
            return None
        return result, rank, suit
    except struct.error:
        return None