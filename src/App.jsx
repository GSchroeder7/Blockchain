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
    <div className="app-container">
      {/* Top banner */}
      <div className="banner">
        <h1 className="banner-title">
          GhoseCoin - Blockchain Implementation (Using Messages)
        </h1>

        <img src={GhoseCoin} alt="GhoseCoin Logo" className="ghose-logo" />
      </div>

      {status && (
        <p className="status">
          <strong>Status:</strong> {status}
        </p>
      )}

      {/* Two-column layout */}
      <div className="two-column">
        {/* Left column: wallet, tx, mining, pending */}
        <div className="left-column">
          {/* Wallet section */}
          <section className="panel">
            <h2 className="panel-heading">Wallet</h2>
            <button
              type="button"
              className="btn-primary"
              onClick={handleNewWallet}
            >
              Generate Wallet
            </button>

            {wallet.public_key && (
              <div className="wallet-keys">
                <p>
                  <strong>Public key:</strong> <code>{wallet.public_key}</code>
                </p>
                <p>
                  <strong>Private key:</strong>{" "}
                  <code>{wallet.private_key}</code>
                </p>
              </div>
            )}
          </section>

          {/* New message transaction */}
          <section className="panel">
            <h2 className="panel-heading">New Message Transaction</h2>
            <form onSubmit={signAndSendTransaction}>
              <div className="field-group">
                <label>Recipient public key:</label>
                <br />
                <input
                  className="field-input"
                  value={txForm.recipient}
                  onChange={(e) =>
                    setTxForm({ ...txForm, recipient: e.target.value })
                  }
                />
              </div>
              <div className="field-group">
                <label>Message:</label>
                <br />
                <input
                  className="field-input"
                  type="text"
                  value={txForm.message}
                  onChange={(e) =>
                    setTxForm({ ...txForm, message: e.target.value })
                  }
                />
              </div>
              <button type="submit" className="btn-primary">
                Send message transaction
              </button>
            </form>
          </section>

          {/* Mining */}
          <section className="panel">
            <h2 className="panel-heading">Mine Block</h2>
            <div className="field-group">
              <label>Miner address (your public key):</label>
              <br />
              <input
                className="field-input"
                value={minerAddress}
                onChange={(e) => setMinerAddress(e.target.value)}
              />
            </div>
            <button onClick={handleMine} className="btn-primary">
              Mine pending transactions
            </button>
          </section>

          {/* Pending transactions */}
          <section className="panel">
            <h2 className="panel-heading">Pending Transactions</h2>
            {pending.length === 0 && <p className="pending-empty">None</p>}
            {pending.map((tx, idx) => (
              <div key={idx} className="pending-card">
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
        <div className="right-column right-column-panel">
          <section>
            <h2 className="panel-heading">Blockchain</h2>
            {chain.map((block) => (
              <div key={block.index} className="block-card">
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
                    <li
                      key={idx}
                      className="trans-card"
                      style={{ marginBottom: "0.75rem" }}
                    >
                      <div style={{ wordBreak: "break-all" }}>
                        <strong>From:</strong>
                        <br />
                        {tx.sender}
                      </div>

                      <div
                        style={{
                          marginTop: "0.25rem",
                          wordBreak: "break-all",
                        }}
                      >
                        <strong>To:</strong>
                        <br />
                        {tx.recipient}
                      </div>

                      <div style={{ marginTop: "0.25rem" }}>
                        <strong>Message:</strong>
                        <br />"{tx.message}"
                      </div>
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
