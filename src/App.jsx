import React, { useEffect, useState } from "react";
import GhoseCoin from "./assets/GhoseCoin.png";
import "./App.css";

const API_BASE = "http://localhost:5000";

function App() {
  const [chain, setChain] = useState([]);
  const [pending, setPending] = useState([]);
  const [wallet, setWallet] = useState({ private_key: "", public_key: "" });

  const [txForm, setTxForm] = useState({
    recipient: "",
    message: "",
  });

  const [minerAddress, setMinerAddress] = useState("");
  const [status, setStatus] = useState("");

  // --- Data fetch helpers ---

  const fetchChain = async () => {
    const res = await fetch(`${API_BASE}/chain`);
    const data = await res.json();
    setChain(data.chain);
  };

  const fetchPending = async () => {
    const res = await fetch(`${API_BASE}/pending`);
    const data = await res.json();
    setPending(data);
  };

  const refreshData = async () => {
    await Promise.all([fetchChain(), fetchPending()]);
  };

  // Load chain and pending on start
  useEffect(() => {
    (async () => {
      try {
        await refreshData();
      } catch (err) {
        console.error("Error loading initial data:", err);
        setStatus("Failed to load initial data");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Wallet ---
  const handleNewWallet = async () => {
    try {
      const res = await fetch(`${API_BASE}/wallets/new`);
      if (!res.ok) {
        setStatus("Failed to generate wallet");
        return;
      }

      const data = await res.json();

      if (!data.private_key || !data.public_key) {
        setStatus("Server returned invalid wallet data");
        console.error("Wallet response:", data);
        return;
      }

      setWallet({
        private_key: data.private_key,
        public_key: data.public_key,
      });

      setMinerAddress(data.public_key);
      setStatus("New wallet generated!");
    } catch (err) {
      console.error(err);
      setStatus("Error contacting server");
    }
  };

  // --- Transactions (text-based) ---

  const signAndSendTransaction = async (event) => {
    event.preventDefault();

    if (!wallet.private_key || !wallet.public_key) {
      setStatus("Generate a wallet first.");
      return;
    }

    if (!txForm.recipient || !txForm.message) {
      setStatus("Fill out recipient and message.");
      return;
    }

    // Educational demo: send private key to backend so it signs.
    const body = {
      sender: wallet.public_key,
      recipient: txForm.recipient,
      message: txForm.message,
      private_key: wallet.private_key,
    };

    const res = await fetch(`${API_BASE}/transactions/new_with_key`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json();
      setStatus(`Transaction failed: ${err.error || "unknown error"}`);
      return;
    }

    setStatus("Transaction submitted");
    setTxForm({ recipient: "", message: "" });
    await fetchPending();
  };

  // --- Mining ---

  const handleMine = async () => {
    if (!minerAddress) {
      setStatus("Set miner address first (usually your public key).");
      return;
    }

    const res = await fetch(`${API_BASE}/mine`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ miner_address: minerAddress }),
    });

    const data = await res.json();
    if (!res.ok) {
      setStatus(`Mining failed: ${data.error || "unknown error"}`);
      return;
    }

    setStatus(`Mined block #${data.block.index}`);
    await refreshData();
  };

  // --- Render ---

  return (
    <div
      style={{
        padding: "1.5rem",
        fontFamily: "sans-serif",
        position: "relative",
        minHeight: "100vh",
      }}
    >
      <img
        src={GhoseCoin}
        alt="GhoseCoin Logo"
        className="ghose-logo"
        style={{
          position: "absolute",
          top: "15px",
          right: "15px",
          width: "150px",
          height: "150px",
          objectFit: "contain",
          userSelect: "none",
          pointerEvents: "none",
        }}
      />

      <h1>SHA-1 Blockchain Demo (Text Messages)</h1>

      {status && (
        <p>
          <strong>Status:</strong> {status}
        </p>
      )}

      {/* Two-column layout */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: "1.5rem",
          marginTop: "1rem",
        }}
      >
        {/* Left column: wallet, tx, mining, pending */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Wallet section */}
          <section style={{ marginBottom: "1.5rem" }}>
            <h2>Wallet</h2>
            <button type="button" onClick={handleNewWallet}>
              Generate Wallet
            </button>

            {wallet.public_key && (
              <div
                style={{
                  marginTop: "0.75rem",
                  textAlign: "left",
                  wordBreak: "break-all", // allow long strings to wrap
                }}
              >
                <p>
                  <strong>Public key:</strong>{" "}
                  <code style={{ wordBreak: "break-all" }}>
                    {wallet.public_key}
                  </code>
                </p>
                <p>
                  <strong>Private key:</strong>{" "}
                  <code style={{ wordBreak: "break-all" }}>
                    {wallet.private_key}
                  </code>
                </p>
              </div>
            )}
          </section>

          {/* New message transaction */}
          <section style={{ marginBottom: "1.5rem" }}>
            <h2>New Message Transaction</h2>
            <form onSubmit={signAndSendTransaction}>
              <div style={{ marginBottom: "0.5rem", textAlign: "left" }}>
                <label>Recipient public key:</label>
                <br />
                <input
                  style={{ width: "100%" }}
                  value={txForm.recipient}
                  onChange={(e) =>
                    setTxForm({ ...txForm, recipient: e.target.value })
                  }
                />
              </div>
              <div style={{ marginBottom: "0.5rem", textAlign: "left" }}>
                <label>Message:</label>
                <br />
                <input
                  style={{ width: "100%" }}
                  type="text"
                  value={txForm.message}
                  onChange={(e) =>
                    setTxForm({ ...txForm, message: e.target.value })
                  }
                />
              </div>
              <button type="submit" style={{ marginTop: "0.5rem" }}>
                Send message transaction
              </button>
            </form>
          </section>

          {/* Mining */}
          <section style={{ marginBottom: "1.5rem" }}>
            <h2>Mine Block</h2>
            <div style={{ textAlign: "left" }}>
              <label>Miner address (your public key):</label>
              <br />
              <input
                style={{ width: "100%" }}
                value={minerAddress}
                onChange={(e) => setMinerAddress(e.target.value)}
              />
            </div>
            <button onClick={handleMine} style={{ marginTop: "0.75rem" }}>
              Mine pending transactions
            </button>
          </section>

          {/* Pending transactions */}
          <section style={{ marginBottom: "1.5rem" }}>
            <h2>Pending Transactions</h2>
            {pending.length === 0 && <p>None</p>}
            {pending.map((tx, idx) => (
              <div
                key={idx}
                style={{
                  border: "1px solid #ccc",
                  padding: "0.5rem",
                  marginBottom: "0.5rem",
                  textAlign: "left",
                  wordBreak: "break-all", // 👈 this keeps it in the column
                }}
              >
                <p>
                  <strong>From:</strong> {tx.sender}
                </p>
                <p>
                  <strong>To:</strong> {tx.recipient}
                </p>
                <p>
                  <strong>Message:</strong> {tx.message}
                </p>
              </div>
            ))}
          </section>
        </div>

        {/* Right column: blockchain */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <section>
            <h2>Blockchain</h2>
            {chain.map((block) => (
              <div
                key={block.index}
                style={{
                  border: "1px solid #666",
                  padding: "0.75rem",
                  marginBottom: "0.75rem",
                  textAlign: "left",
                  wordBreak: "break-all",
                }}
              >
                <p>
                  <strong>Index:</strong> {block.index}
                </p>
                <p>
                  <strong>Timestamp:</strong>{" "}
                  {new Date(block.timestamp * 1000).toLocaleString()}
                </p>
                <p>
                  <strong>Previous hash:</strong>{" "}
                  <code>{block.previous_hash}</code>
                </p>
                <p>
                  <strong>Hash (SHA-1):</strong> <code>{block.hash}</code>
                </p>
                <p>
                  <strong>Nonce:</strong> {block.nonce}
                </p>
                <p>
                  <strong>Transactions:</strong>
                </p>
                <ul>
                  {block.transactions.map((tx, idx) => (
                    <li key={idx}>
                      {tx.sender} → {tx.recipient}: "{tx.message}"
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </section>
        </div>
      </div>
    </div>
  );
}

export default App;
