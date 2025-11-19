import time
import json
from dataclasses import dataclass, asdict
from typing import List, Optional

from flask import Flask, request, jsonify
from flask_cors import CORS
from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError

# ------------------------
# Helpers: SHA-1 and keys
# ------------------------

def _left_rotate(n, b):
    """Left rotate a 32-bit integer n by b bits."""
    return ((n << b) | (n >> (32 - b))) & 0xffffffff


def sha1_hex(message: bytes) -> str:
    """Pure-Python SHA-1 implementation (no hashlib). Returns hex string."""

    # Initialize variables:
    h0 = 0x67452301
    h1 = 0xEFCDAB89
    h2 = 0x98BADCFE
    h3 = 0x10325476
    h4 = 0xC3D2E1F0

    # Pre-processing:
    original_length = len(message) * 8
    message += b'\x80'
    while (len(message) * 8) % 512 != 448:
        message += b'\x00'

    message += original_length.to_bytes(8, byteorder='big')

    # Process the message in 512-bit chunks:
    for i in range(0, len(message), 64):
        chunk = message[i:i+64]
        w = [int.from_bytes(chunk[j:j+4], 'big') for j in range(0, 64, 4)]

        for j in range(16, 80):
            w.append(_left_rotate(w[j-3] ^ w[j-8] ^ w[j-14] ^ w[j-16], 1))

        a, b, c, d, e = h0, h1, h2, h3, h4

        # Main loop:
        for j in range(80):
            if 0 <= j <= 19:
                f = (b & c) | (~b & d)
                k = 0x5A827999
            elif 20 <= j <= 39:
                f = b ^ c ^ d
                k = 0x6ED9EBA1
            elif 40 <= j <= 59:
                f = (b & c) | (b & d) | (c & d)
                k = 0x8F1BBCDC
            else:
                f = b ^ c ^ d
                k = 0xCA62C1D6

            temp = (_left_rotate(a, 5) + f + e + k + w[j]) & 0xffffffff
            e = d
            d = c
            c = _left_rotate(b, 30)
            b = a
            a = temp

        # Add this chunk's hash to result so far:
        h0 = (h0 + a) & 0xffffffff
        h1 = (h1 + b) & 0xffffffff
        h2 = (h2 + c) & 0xffffffff
        h3 = (h3 + d) & 0xffffffff
        h4 = (h4 + e) & 0xffffffff

    # Produce final SHA-1 digest:
    return "".join(f"{x:08x}" for x in [h0, h1, h2, h3, h4])


def generate_keypair():
    """Return (private_key_hex, public_key_hex)."""
    sk = SigningKey.generate(curve=SECP256k1)
    vk = sk.verifying_key
    return sk.to_string().hex(), vk.to_string().hex()


def sign_message(private_key_hex: str, message: bytes) -> str:
    """Sign message bytes with ECDSA using the given private key."""
    sk = SigningKey.from_string(bytes.fromhex(private_key_hex), curve=SECP256k1)
    sig = sk.sign(message)
    return sig.hex()


def verify_signature(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
    """Verify an ECDSA signature with the given public key."""
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=SECP256k1)
        sig = bytes.fromhex(signature_hex)
        return vk.verify(sig, message)
    except (BadSignatureError, ValueError):
        return False

# ------------------------
# Data models
# ------------------------

@dataclass
class Transaction:
    """
    A single text-message transaction signed by the sender.

    Fields:
    - sender:    hex-encoded public key of sender, or "SYSTEM" for rewards
    - recipient: hex-encoded public key of recipient
    - message:   arbitrary text content
    - signature: hex-encoded ECDSA signature over (sender|recipient|message)
    - public_key: public key used to verify signature (same as sender)
    """
    sender: str
    recipient: str
    message: str
    signature: Optional[str] = None
    public_key: Optional[str] = None

    def to_dict(self):
        d = asdict(self)
        # public_key is only needed for verification, not for storage
        d.pop("public_key", None)
        return d

    def message_bytes(self) -> bytes:
        """
        Deterministic representation of what is signed.
        """
        payload = f"{self.sender}|{self.recipient}|{self.message}"
        return payload.encode("utf8")

    def is_system_reward(self) -> bool:
        return self.sender == "SYSTEM"

    def verify(self) -> bool:
        """
        Verify the transaction's signature.

        System reward transactions are allowed to skip signatures.
        """
        if self.is_system_reward():
            return True

        if not self.signature or not self.public_key:
            return False

        return verify_signature(
            self.public_key,
            self.message_bytes(),
            self.signature
        )


@dataclass
class Block:
    """
    A block in the blockchain.
    """
    index: int
    timestamp: float
    transactions: List[dict]
    previous_hash: str
    nonce: int = 0
    hash: Optional[str] = None

    def compute_hash(self) -> str:
        """
        Hash the block content with SHA-1.
        """
        block_content = {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }
        block_string = json.dumps(block_content, sort_keys=True).encode("utf8")
        return sha1_hex(block_string)

# ------------------------
# Blockchain
# ------------------------

class Blockchain:
    """
    Minimal SHA-1-based blockchain with proof-of-work and text transactions.
    """

    def __init__(self, difficulty: int = 4, block_reward: float = 50.0):
        self.difficulty = difficulty
        self.block_reward = block_reward
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self.create_genesis_block()

    def create_genesis_block(self):
        genesis_block = Block(
            index=0,
            timestamp=time.time(),
            transactions=[],
            previous_hash="0" * 40,  # SHA-1 hex length is 40
            nonce=0
        )
        genesis_block.hash = genesis_block.compute_hash()
        self.chain.append(genesis_block)

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def add_transaction(self, tx: Transaction) -> bool:
        """
        Verify and add a new transaction to the pending pool.
        """
        if not tx.verify():
            return False
        self.pending_transactions.append(tx)
        return True

    def proof_of_work(self, block: Block) -> str:
        """
        Simple PoW: find a nonce such that hash starts with difficulty zeros.
        """
        prefix = "0" * self.difficulty
        while True:
            h = block.compute_hash()
            if h.startswith(prefix):
                return h
            block.nonce += 1

    def mine_pending_transactions(self, miner_address: str) -> Block:
        """
        Create a new block with current pending transactions and a reward.
        """
        # Add mining reward first (system transaction, no signature)
        reward_tx = Transaction(
            sender="SYSTEM",
            recipient=miner_address,
            message=f"Block reward to {miner_address}",
            signature=None
        )
        self.pending_transactions.append(reward_tx)

        transactions_dicts = [tx.to_dict() for tx in self.pending_transactions]

        new_block = Block(
            index=self.last_block.index + 1,
            timestamp=time.time(),
            transactions=transactions_dicts,
            previous_hash=self.last_block.hash
        )

        block_hash = self.proof_of_work(new_block)
        new_block.hash = block_hash

        # Add block and clear pending
        self.chain.append(new_block)
        self.pending_transactions = []

        return new_block

    def is_chain_valid(self) -> bool:
        """
        Verify hash chain and proof-of-work.
        """
        prefix = "0" * self.difficulty

        for i in range(1, len(self.chain)):
            current = self.chain[i]
            prev = self.chain[i - 1]

            # Check hash
            if current.hash != current.compute_hash():
                return False

            # Check link
            if current.previous_hash != prev.hash:
                return False

            # Check PoW
            if not current.hash.startswith(prefix):
                return False

        return True

# ------------------------
# Flask app
# ------------------------

app = Flask(__name__)
CORS(app)  # allow requests from the React dev server
blockchain = Blockchain(difficulty=3)  # easier difficulty for demo

@app.route("/wallets/new", methods=["GET"])
def new_wallet():
    """
    Generate a new ECDSA keypair and return it.
    """
    private_key, public_key = generate_keypair()
    return jsonify({
        "private_key": private_key,
        "public_key": public_key
    })

@app.route("/transactions/new_with_key", methods=["POST"])
def new_transaction_with_key():
    """
    Create a new text-message transaction, signed on the server side.

    Expected JSON body:
    {
        "sender": "<sender public key hex>",
        "recipient": "<recipient public key hex>",
        "message": "<text>",
        "private_key": "<sender private key hex>"
    }
    """
    data = request.get_json()
    required = ["sender", "recipient", "message", "private_key"]
    if not data or not all(k in data for k in required):
        return jsonify({"error": "Missing fields"}), 400

    sender = data["sender"]
    recipient = data["recipient"]
    message_text = data["message"]
    private_key_hex = data["private_key"]

    # Build a dummy transaction to get canonical message bytes
    dummy_tx = Transaction(sender=sender, recipient=recipient, message=message_text)
    msg_bytes = dummy_tx.message_bytes()

    # Sign on the server (educational demo, not secure in real life)
    signature_hex = sign_message(private_key_hex, msg_bytes)

    tx = Transaction(
        sender=sender,
        recipient=recipient,
        message=message_text,
        signature=signature_hex,
        public_key=sender
    )

    if not tx.verify():
        return jsonify({"error": "Signature did not verify"}), 400

    blockchain.add_transaction(tx)
    return jsonify({
        "message": "Transaction added",
        "transaction": tx.to_dict()
    }), 201

@app.route("/mine", methods=["POST"])
def mine():
    """
    Mine a new block from pending transactions.
    Body must contain:
    {
        "miner_address": "<public key of miner>"
    }
    """
    data = request.get_json()
    miner_address = data.get("miner_address") if data else None
    if not miner_address:
        return jsonify({"error": "miner_address required"}), 400

    block = blockchain.mine_pending_transactions(miner_address)
    return jsonify({
        "message": "Block mined",
        "block": {
            "index": block.index,
            "timestamp": block.timestamp,
            "transactions": block.transactions,
            "previous_hash": block.previous_hash,
            "nonce": block.nonce,
            "hash": block.hash,
        }
    }), 201

@app.route("/chain", methods=["GET"])
def full_chain():
    """
    Return the full blockchain.
    """
    chain_data = []
    for b in blockchain.chain:
        chain_data.append({
            "index": b.index,
            "timestamp": b.timestamp,
            "transactions": b.transactions,
            "previous_hash": b.previous_hash,
            "nonce": b.nonce,
            "hash": b.hash,
        })
    return jsonify({
        "length": len(chain_data),
        "chain": chain_data,
        "valid": blockchain.is_chain_valid()
    })

@app.route("/pending", methods=["GET"])
def pending_transactions():
    """
    Return current pending transactions.
    """
    return jsonify([tx.to_dict() for tx in blockchain.pending_transactions])

if __name__ == "__main__":
    app.run(port=5000, debug=True)