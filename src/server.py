import time
import json
import random
from dataclasses import dataclass, asdict
from typing import List, Optional
from flask import Flask, request, jsonify
from flask_cors import CORS
from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError


# Helper function used by our manual SHA-1
# Rotates a 32 bit integer n to the left by b bits
def _left_rotate(n, b):
    return ((n << b) | (n >> (32 - b))) & 0xffffffff

# Manual implementation of SHA-1 encryption
def sha1_hex(message: bytes) -> str:
    # Constants defined by SHA1 standard
    # Think of them as the "seed" for our hashing process
    h0 = 0x67452301
    h1 = 0xEFCDAB89
    h2 = 0x98BADCFE
    h3 = 0x10325476
    h4 = 0xC3D2E1F0

    # Record original length
    originalLength = len(message) * 8
    
    # Add a '1' bit (10000000 in binary)
    message += b'\x80'
    
    # SHA-1 requires the final block (before length) to end at 448 mod 512 bits
    # Add zero bytes until that condition is met (padding)
    while (len(message) * 8) % 512 != 448:
        message += b'\x00'
    
    # Append the original length which takes up the final 64 bits of the padded message.
    message += originalLength.to_bytes(8, byteorder='big')

    # Process the message in 512-bit chunks (64 bytes each)
    for i in range(0, len(message), 64):
        chunk = message[i:i+64]
        
        # Break the chunk into sixteen 32-bit words
        # These become the foundation of the 80-word schedule
        w = [int.from_bytes(chunk[j:j+4], 'big') for j in range(0, 64, 4)]

        # Each new word is based on XORs of earlier words, then left-rotated by 1.
        # This ensures diffusion and unpredictability.
        for j in range(16, 80):
            w.append(_left_rotate(w[j-3] ^ w[j-8] ^ w[j-14] ^ w[j-16], 1))
        
        # Initialize the working variables for this chunk
        # Each round updates these values
        a, b, c, d, e = h0, h1, h2, h3, h4
        
        # SHA1 compression run for 80 rounds
        for j in range(80):
            
            # SHA-1 uses different functions (f) and constants (k) 
            # depending on the round we're in.
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

            # Core SHA-1 round operation
            # Rotate a, add f, add e, add constant k, add message word w[j]
            temp = (_left_rotate(a, 5) + f + e + k + w[j]) & 0xffffffff
            
            # Shift pipeline forward
            e = d
            d = c
            c = _left_rotate(b, 30)
            b = a
            a = temp
        
        # Add this chunk's results back into the main hash values
        h0 = (h0 + a) & 0xffffffff
        h1 = (h1 + b) & 0xffffffff
        h2 = (h2 + c) & 0xffffffff
        h3 = (h3 + d) & 0xffffffff
        h4 = (h4 + e) & 0xffffffff
    
    # Return the concatenated hex string of all five hash registers.
    return "".join(f"{x:08x}" for x in [h0, h1, h2, h3, h4])



# --- Wallet and signature helpers using ECDSA (secp256k1) ---

# Generate a keypair used for Wallets
def generate_keypair():
    # Generate a new ECDSA private key on the secp256k1 curve
    sk = SigningKey.generate(curve=SECP256k1)
    # Derive the matching public key
    vk = sk.verifying_key
    # Return both keys as hex strings
    return sk.to_string().hex(), vk.to_string().hex()

# Sign a message using sender's Private Key
def sign_message(private_key_hex: str, message: bytes) -> str:
    # Convert the private key object to a string from its hex representation
    sk = SigningKey.from_string(bytes.fromhex(private_key_hex), curve=SECP256k1)
    # Create a digital signature over the message bytes
    sig = sk.sign(message)
    # Return signature as hex so it can be sent it over JSON
    return sig.hex()


def verify_signature(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
    # Verify a signature using the public key
    try:
        # Turn Public Key Hex to String
        vk = VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=SECP256k1)
        # Rebuild the signature bytes from hex
        sig = bytes.fromhex(signature_hex)
        # Return True if sig is valid
        return vk.verify(sig, message)
    
    # If verification fails or inputs are malformed, it is treated as invalid
    except (BadSignatureError, ValueError):
        return False



# --- Transaction object represents one message transfer on the chain ---


@dataclass
class Transaction:
    # The "sender" is represented by their public key in hex, or "SYSTEM" for rewards
    sender: str
    # The "recipient" is another public key in hex
    recipient: str
    # Message carried by this transaction (acts as the payload/transaction)
    message: str
    # Digital signature of this transaction (optional until signed)
    signature: Optional[str] = None
    # Public key used to verify the signature (for normal transactions)
    public_key: Optional[str] = None

    def to_dict(self):
        # Convert the dataclass to a plain dictionary
        d = asdict(self)
        # The public key is not exposed in the transaction dict here
        # since the sender field already identifies the sender
        d.pop("public_key", None)
        return d

    def message_bytes(self) -> bytes:
        # Build the canonical message string that we sign and verify
        # This ensures that sender, recipient, and message are all bound together
        payload = f"{self.sender}|{self.recipient}|{self.message}"
        return payload.encode("utf8")

    def is_system_reward(self) -> bool:
        # System reward transactions do not require signatures
        return self.sender == "SYSTEM"

    def verify(self) -> bool:
        # Validate the transaction
        if self.is_system_reward():
            # Skip signature checks for system generated rewards
            return True
        
        # For normal transactions we need both a signature and a public key
        if not self.signature or not self.public_key:
            return False
        
        # Use our ECDSA verification function to check it
        return verify_signature(
            self.public_key,
            self.message_bytes(),
            self.signature
        )



# --- Block object represents one block in the blockchain ---

@dataclass
class Block:
    # Sequential index of the block in the chain
    index: int
    # Timestamp for when the block was created
    timestamp: float
    # List of transactions stored as dictionaries
    transactions: List[dict]
    # Hash of the previous block in the chain
    previous_hash: str
    # Nonce used for proof of work
    nonce: int = 0
    # Cached hash of this block (set after mining)
    hash: Optional[str] = None

    def compute_hash(self) -> str:
        # Prepare the data that defines this block
        block_content = {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }
        # Convert to a canonical JSON string so ordering is consistent
        block_string = json.dumps(block_content, sort_keys=True).encode("utf8")
        # Hash the block data using the SHA-1 implementation
        return sha1_hex(block_string)
    
    
# --- Core Blockchain logic ---


class Blockchain:
    def __init__(self, difficulty: int = 4, block_reward: float = 50.0):
        # Difficulty controls how many leading zeros the block hash must have
        self.difficulty = difficulty
        # Block reward is the amount/transaction granted to the miner each time
        self.block_reward = block_reward
        # The chain is a list of Block objects
        self.chain: List[Block] = []
        # Pending transactions are transactions that are not yet mined into a block
        self.pending_transactions: List[Transaction] = []
        # Create the first block in the chain
        self.create_genesis_block()

    def create_genesis_block(self):
        # Genesis block is the first block and has no previous block
        genesis_block = Block(
            index=0,
            timestamp=time.time(),
            transactions=[],
            # Previous hash is just 40 zeros because SHA-1 hashes are 40 hex characters
            previous_hash="0" * 40,
            nonce=0
        )
        # Compute and set the hash of the genesis block
        genesis_block.hash = genesis_block.compute_hash()
        # Add it to the chain
        self.chain.append(genesis_block)

    @property
    def last_block(self) -> Block:
        # Convenience property to get the most recent block in the chain
        return self.chain[-1]

    def add_transaction(self, tx: Transaction) -> bool:
        # Only accept the transaction if it is verified
        if not tx.verify():
            return False
        # Add it to the pool of pending transactions
        self.pending_transactions.append(tx)
        return True

    def proof_of_work(self, block: Block) -> str:
        # Proof of work tries different nonce values until the hash
        # of the block starts with a certain number of zeros
        prefix = "0" * self.difficulty
        while True:
            # Compute the current hash for this nonce
            h = block.compute_hash()
            # Check if the hash satisfies the difficulty condition (0-3 leading 0's depending on difficulty of block)
            if h.startswith(prefix):
                # If so we have found a valid proof
                return h
            # Otherwise increase the nonce and try again
            block.nonce += 1

    def mine_pending_transactions(self, miner_address: str) -> Block:
        # Create a reward transaction paying the miner
        reward_tx = Transaction(
            sender="SYSTEM",
            recipient=miner_address,
            message=f"Block reward to {miner_address}",
            signature=None
        )
        
        # Add the reward transaction to the pending pool
        self.pending_transactions.append(reward_tx)

        # Convert each Transaction into a dictionary for storage in the block
        transactions_dicts = [tx.to_dict() for tx in self.pending_transactions]

        # Create a new block including all pending transactions
        new_block = Block(
            index=self.last_block.index + 1,
            timestamp=time.time(),
            transactions=transactions_dicts,
            previous_hash=self.last_block.hash
        )

        # Run proof of work to find a valid hash for this block
        block_hash = self.proof_of_work(new_block)
        new_block.hash = block_hash

        # Add the newly mined block to the chain
        self.chain.append(new_block)
        
        # Clear the pending transactions now that they are in a block
        self.pending_transactions = []

        # Return the mined block so the API can display it
        return new_block

    def is_chain_valid(self) -> bool:
        # Validate the entire chain starting from block 1
        prefix = "0" * self.difficulty
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            prev = self.chain[i - 1]

            # Recompute the hash and check it matches the stored hash
            if current.hash != current.compute_hash():
                return False

            # Check the link between this block and the previous block
            if current.previous_hash != prev.hash:
                return False

            # Ensure the hash still satisfies the difficulty requirement
            if not current.hash.startswith(prefix):
                return False

        # If we pass all checks the chain is valid
        return True



# --- Flask API to interact with our blockchain from the front end ---

app = Flask(__name__)
# Allow cross origin requests so our React front end can talk to this API
CORS(app) 

# Difficulty is chosen randomly between 1 and 3 (Initial 0's of Hash) Only up to 3 for demo purposes. Harder/More secure = more 0's
DIFFICULTY = random.randint(1, 3)  

# Initialize the global blockchain instance
blockchain = Blockchain(difficulty=DIFFICULTY)

@app.route("/wallets/new", methods=["GET"])
def new_wallet():
    # Endpoint creates a new wallet (a new keypair)
    private_key, public_key = generate_keypair()
    # Return both keys so the user can save their private key
    return jsonify({
        "private_key": private_key,
        "public_key": public_key
    })

@app.route("/transactions/new_with_key", methods=["POST"])
def new_transaction_with_key():
    # Create and sign a new transaction
    data = request.get_json()

    # Form a valid transaction
    required = ["sender", "recipient", "message", "private_key"]
    if not data or not all(k in data for k in required):
        return jsonify({"error": "Missing fields"}), 400

    sender = data["sender"]
    recipient = data["recipient"]
    message_text = data["message"]
    private_key_hex = data["private_key"]

    # Build a temporary transaction object so it can get its message bytes
    dummy_tx = Transaction(sender=sender, recipient=recipient, message=message_text)
    msg_bytes = dummy_tx.message_bytes()

    # Sign the transaction payload using the provided private key
    signature_hex = sign_message(private_key_hex, msg_bytes)

    # Create the real transaction object with signature and public key
    tx = Transaction(
        sender=sender,
        recipient=recipient,
        message=message_text,
        signature=signature_hex,
        public_key=sender
    )

    # Check that the signature verifies
    if not tx.verify():
        return jsonify({"error": "Signature did not verify"}), 400

    # If yes, add it to the pending transactions
    blockchain.add_transaction(tx)
    return jsonify({
        "message": "Transaction added",
        "transaction": tx.to_dict()
    }), 201

@app.route("/mine", methods=["POST"])
def mine():
    # Endpoint to mine all current pending transactions into a new block
    data = request.get_json()
    miner_address = data.get("miner_address") if data else None

    # Find the Miner's address to send the block reward
    if not miner_address:
        return jsonify({"error": "miner_address required"}), 400

    # Perform mining and get back the new block
    block = blockchain.mine_pending_transactions(miner_address)

    # Return details about the mined block
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
    # Endpoint to view the entire blockchain and its validity
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

    # Report whether the chain passes the validity checks
    return jsonify({
        "length": len(chain_data),
        "chain": chain_data,
        "valid": blockchain.is_chain_valid()
    })

@app.route("/pending", methods=["GET"])
def pending_transactions():
    # Endpoint to see all transactions that are waiting to be mined
    return jsonify([tx.to_dict() for tx in blockchain.pending_transactions])

if __name__ == "__main__":
    app.run(port=5000, debug=True)