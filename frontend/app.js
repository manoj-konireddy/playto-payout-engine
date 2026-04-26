const { useEffect, useMemo, useState } = React;

const defaultMerchantId = "1";

function fmtPaise(paise) {
  return `INR ${(paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
}

function App() {
  const [merchantId, setMerchantId] = useState(defaultMerchantId);
  const [dashboard, setDashboard] = useState(null);
  const [amount, setAmount] = useState("");
  const [bankAccountId, setBankAccountId] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const headers = useMemo(
    () => ({
      "Content-Type": "application/json",
      "X-Merchant-Id": merchantId,
    }),
    [merchantId]
  );

  async function loadDashboard() {
    const res = await fetch("/api/v1/merchant/dashboard", { headers });
    const data = await res.json();
    if (!res.ok) {
      setError(data.error || "Failed to load dashboard");
      return;
    }
    setError("");
    setDashboard(data);
    if (!bankAccountId && data.bank_accounts.length > 0) {
      setBankAccountId(String(data.bank_accounts[0].id));
    }
  }

  useEffect(() => {
    loadDashboard();
    const poll = setInterval(loadDashboard, 3000);
    return () => clearInterval(poll);
  }, [merchantId]);

  async function requestPayout(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = {
        amount_paise: Number(amount),
        bank_account_id: Number(bankAccountId),
      };
      const res = await fetch("/api/v1/payouts", {
        method: "POST",
        headers: {
          ...headers,
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Payout request failed");
      } else {
        setAmount("");
      }
      await loadDashboard();
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      <h1 className="text-2xl font-semibold">Playto Payout Dashboard</h1>

      <section className="bg-white p-4 rounded-xl shadow-sm flex gap-4 items-end">
        <label className="block">
          <span className="text-sm text-slate-600">Merchant ID</span>
          <input
            className="mt-1 border rounded px-3 py-2 w-40"
            value={merchantId}
            onChange={(e) => setMerchantId(e.target.value)}
          />
        </label>
      </section>

      {dashboard && (
        <section className="grid md:grid-cols-3 gap-4">
          <StatCard label="Available Balance" value={fmtPaise(dashboard.available_balance_paise)} />
          <StatCard label="Held Balance" value={fmtPaise(dashboard.held_balance_paise)} />
          <StatCard
            label="Ledger (Credits - Debits)"
            value={fmtPaise(dashboard.ledger_invariant.computed_available_paise)}
          />
        </section>
      )}

      <section className="bg-white p-4 rounded-xl shadow-sm">
        <h2 className="font-semibold mb-3">Request Payout</h2>
        <form onSubmit={requestPayout} className="grid md:grid-cols-3 gap-3">
          <input
            className="border rounded px-3 py-2"
            type="number"
            min="1"
            placeholder="Amount in paise"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
          />
          <select
            className="border rounded px-3 py-2"
            value={bankAccountId}
            onChange={(e) => setBankAccountId(e.target.value)}
            required
          >
            <option value="">Select bank account</option>
            {(dashboard?.bank_accounts || []).map((b) => (
              <option key={b.id} value={b.id}>
                {b.label}
              </option>
            ))}
          </select>
          <button
            disabled={busy}
            className="bg-indigo-600 text-white rounded px-3 py-2 disabled:opacity-60"
          >
            {busy ? "Submitting..." : "Request payout"}
          </button>
        </form>
        {error && <p className="text-red-600 text-sm mt-2">{error}</p>}
      </section>

      <section className="bg-white p-4 rounded-xl shadow-sm">
        <h2 className="font-semibold mb-3">Payout History</h2>
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="py-2">ID</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Attempts</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {(dashboard?.payouts || []).map((p) => (
                <tr key={p.id} className="border-b">
                  <td className="py-2">{p.id}</td>
                  <td>{fmtPaise(p.amount_paise)}</td>
                  <td className="capitalize">{p.status}</td>
                  <td>{p.attempt_count}</td>
                  <td>{new Date(p.updated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="bg-white p-4 rounded-xl shadow-sm">
        <h2 className="font-semibold mb-3">Recent Ledger Entries</h2>
        <ul className="space-y-2 text-sm">
          {(dashboard?.recent_ledger || []).map((entry) => (
            <li key={entry.id} className="border rounded p-2 flex justify-between">
              <span>{entry.description}</span>
              <span className={entry.entry_type === "credit" ? "text-green-700" : "text-red-700"}>
                {entry.entry_type === "credit" ? "+" : "-"} {fmtPaise(entry.amount_paise)}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="bg-white p-4 rounded-xl shadow-sm">
      <p className="text-sm text-slate-600">{label}</p>
      <p className="text-xl font-semibold">{value}</p>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
