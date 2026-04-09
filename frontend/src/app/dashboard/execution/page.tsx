"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatPrice, timeAgo } from "@/lib/utils";
import type { ExchangeAccountResponse, OrderResponse } from "@/types";

export default function ExecutionPage() {
  const [accounts, setAccounts] = useState<ExchangeAccountResponse[]>([]);
  const [orders, setOrders] = useState<OrderResponse[]>([]);
  const [loading, setLoading] = useState(true);

  // Add account form
  const [showForm, setShowForm] = useState(false);
  const [formExchange, setFormExchange] = useState("demo");
  const [formLabel, setFormLabel] = useState("");
  const [formKey, setFormKey] = useState("");
  const [formSecret, setFormSecret] = useState("");
  const [formAuto, setFormAuto] = useState(false);
  const [formError, setFormError] = useState("");

  const load = async () => {
    try {
      const [accs, ords] = await Promise.all([
        api.getExchangeAccounts(),
        api.getOrders(),
      ]);
      setAccounts(accs);
      setOrders(ords.items);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleAddAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    try {
      await api.createExchangeAccount({
        exchange: formExchange,
        label: formLabel || `${formExchange} account`,
        api_key: formKey || "demo",
        api_secret: formSecret || "demo",
        auto_execute: formAuto,
      });
      setShowForm(false);
      setFormLabel("");
      setFormKey("");
      setFormSecret("");
      load();
    } catch (err: any) {
      setFormError(err.message);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Execution</h1>
          <p className="text-sm text-gray-400">
            Manage exchange accounts and execute signals
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          {showForm ? "Cancel" : "+ Add Account"}
        </button>
      </div>

      {/* Add Account Form */}
      {showForm && (
        <form
          onSubmit={handleAddAccount}
          className="mb-6 space-y-3 rounded-xl border border-gray-800 bg-surface-card p-6"
        >
          {formError && (
            <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">
              {formError}
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs text-gray-400">Exchange</label>
              <select
                value={formExchange}
                onChange={(e) => setFormExchange(e.target.value)}
                className="w-full rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white"
              >
                <option value="demo">Demo (Paper Trading)</option>
                <option value="binance">Binance</option>
                <option value="bybit">Bybit</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">Label</label>
              <input
                type="text"
                value={formLabel}
                onChange={(e) => setFormLabel(e.target.value)}
                placeholder="My Account"
                className="w-full rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-brand-500"
              />
            </div>
          </div>
          {formExchange !== "demo" && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs text-gray-400">API Key</label>
                <input
                  type="password"
                  value={formKey}
                  onChange={(e) => setFormKey(e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">API Secret</label>
                <input
                  type="password"
                  value={formSecret}
                  onChange={(e) => setFormSecret(e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-brand-500"
                />
              </div>
            </div>
          )}
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={formAuto}
              onChange={(e) => setFormAuto(e.target.checked)}
              className="rounded"
            />
            Enable auto-execution for high-confidence signals
          </label>
          <button
            type="submit"
            className="rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            Add Account
          </button>
        </form>
      )}

      {/* Accounts */}
      <div className="mb-8">
        <h2 className="mb-3 text-lg font-bold text-white">
          Exchange Accounts ({accounts.length})
        </h2>
        {accounts.length === 0 ? (
          <div className="rounded-xl border border-gray-800 bg-surface-card p-8 text-center text-gray-400">
            No accounts. Add a Demo account to start paper trading.
          </div>
        ) : (
          <div className="space-y-2">
            {accounts.map((acc) => (
              <div
                key={acc.id}
                className="flex items-center justify-between rounded-xl border border-gray-800 bg-surface-card p-4"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-bold uppercase ${
                      acc.exchange === "demo"
                        ? "bg-purple-500/20 text-purple-400"
                        : "bg-yellow-500/20 text-yellow-400"
                    }`}
                  >
                    {acc.exchange}
                  </span>
                  <span className="font-medium text-white">{acc.label}</span>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className={acc.auto_execute ? "text-green-400" : "text-gray-500"}>
                    {acc.auto_execute ? "Auto ON" : "Manual"}
                  </span>
                  <span className="text-gray-500">
                    Min: {(acc.min_confidence * 100).toFixed(0)}%
                  </span>
                  <span className="text-gray-500">
                    Size: {acc.max_position_pct}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Orders */}
      <div>
        <h2 className="mb-3 text-lg font-bold text-white">
          Order History ({orders.length})
        </h2>
        {orders.length === 0 ? (
          <div className="rounded-xl border border-gray-800 bg-surface-card p-8 text-center text-gray-400">
            No orders yet. Execute a signal to see trades here.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-gray-800">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-gray-700 bg-surface-card text-gray-400">
                <tr>
                  <th className="p-3">Symbol</th>
                  <th className="p-3">Side</th>
                  <th className="p-3">Qty</th>
                  <th className="p-3">Price</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Exchange</th>
                  <th className="p-3">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {orders.map((order) => (
                  <tr key={order.id} className="bg-surface-card text-gray-300">
                    <td className="p-3 font-medium text-white">{order.symbol}</td>
                    <td
                      className={`p-3 font-bold uppercase ${
                        order.side === "buy" ? "text-green-400" : "text-red-400"
                      }`}
                    >
                      {order.side}
                    </td>
                    <td className="p-3">{order.quantity}</td>
                    <td className="p-3">
                      {order.filled_price ? formatPrice(order.filled_price) : "—"}
                    </td>
                    <td className="p-3">
                      <span
                        className={`rounded px-2 py-0.5 text-xs ${
                          order.status === "filled"
                            ? "bg-green-500/20 text-green-400"
                            : order.status === "failed"
                              ? "bg-red-500/20 text-red-400"
                              : "bg-yellow-500/20 text-yellow-400"
                        }`}
                      >
                        {order.status}
                      </span>
                    </td>
                    <td className="p-3 text-gray-500">{order.exchange}</td>
                    <td className="p-3 text-gray-500">{timeAgo(order.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
