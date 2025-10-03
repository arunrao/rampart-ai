"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

interface ProviderKey {
  id: string;
  provider: string;
  masked_key: string;
  last_4: string;
  status: string;
  created_at: string;
  updated_at: string;
}

interface Provider {
  id: string;
  name: string;
  description: string;
  key_format: string;
  docs_url: string;
}

export default function SettingsPage() {
  const router = useRouter();
  const [keys, setKeys] = useState<ProviderKey[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  
  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const getAuthToken = () => {
    return localStorage.getItem("auth_token");
  };

  const loadData = async () => {
    const token = getAuthToken();
    if (!token) {
      router.push("/login");
      return;
    }

    try {
      // Load providers
      const providersRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/providers/supported`);
      const providersData = await providersRes.json();
      setProviders(providersData.providers);

      // Load user's keys
      const keysRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/providers/keys`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (keysRes.status === 401) {
        router.push("/login");
        return;
      }

      const keysData = await keysRes.json();
      setKeys(keysData.keys);
    } catch (err: any) {
      setError("Failed to load settings");
    } finally {
      setLoading(false);
    }
  };

  const handleAddKey = (provider: Provider) => {
    setSelectedProvider(provider);
    setApiKey("");
    setShowModal(true);
    setError("");
    setSuccess("");
  };

  const handleSaveKey = async () => {
    if (!selectedProvider || !apiKey) return;

    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const token = getAuthToken();
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/providers/keys/${selectedProvider.id}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ api_key: apiKey }),
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to save API key");
      }

      setSuccess(`${selectedProvider.name} API key saved successfully`);
      setShowModal(false);
      setApiKey("");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to save API key");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteKey = async (provider: string) => {
    if (!confirm(`Are you sure you want to delete your ${provider} API key?`)) {
      return;
    }

    try {
      const token = getAuthToken();
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/providers/keys/${provider}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error("Failed to delete API key");
      }

      setSuccess("API key deleted successfully");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to delete API key");
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("user_email");
    router.push("/login");
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-white">Settings</h1>
            <p className="text-gray-400 mt-2">
              Manage your API keys and account settings
            </p>
          </div>
          <button
            onClick={handleLogout}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-md"
          >
            Logout
          </button>
        </div>

        {/* Alerts */}
        {error && (
          <div className="mb-4 bg-red-500/10 border border-red-500 text-red-500 px-4 py-3 rounded">
            {error}
          </div>
        )}
        {success && (
          <div className="mb-4 bg-green-500/10 border border-green-500 text-green-500 px-4 py-3 rounded">
            {success}
          </div>
        )}

        {/* API Keys Section */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h2 className="text-xl font-semibold text-white mb-4">API Keys</h2>
          <p className="text-gray-400 mb-6">
            Add your LLM provider API keys to start using Project Rampart
          </p>

          <div className="space-y-4">
            {providers.map((provider) => {
              const existingKey = keys.find((k) => k.provider === provider.id);

              return (
                <div
                  key={provider.id}
                  className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg border border-gray-600"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-medium text-white">
                        {provider.name}
                      </h3>
                      {existingKey && (
                        <span className="px-2 py-1 bg-green-500/20 text-green-400 text-xs rounded">
                          Active
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-400 mt-1">
                      {provider.description}
                    </p>
                    {existingKey && (
                      <p className="text-sm text-gray-500 mt-2 font-mono">
                        {existingKey.masked_key}
                      </p>
                    )}
                  </div>

                  <div className="flex gap-2">
                    {existingKey ? (
                      <>
                        <button
                          onClick={() => handleAddKey(provider)}
                          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm"
                        >
                          Update
                        </button>
                        <button
                          onClick={() => handleDeleteKey(provider.id)}
                          className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-md text-sm"
                        >
                          Delete
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => handleAddKey(provider)}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm"
                      >
                        Add Key
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Account Info */}
        <div className="mt-8 bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h2 className="text-xl font-semibold text-white mb-4">Account</h2>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-400">Email:</span>
              <span className="text-white">{localStorage.getItem("user_email")}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Modal for adding/updating API key */}
      {showModal && selectedProvider && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 max-w-md w-full">
            <h3 className="text-xl font-semibold text-white mb-4">
              {selectedProvider.name} API Key
            </h3>
            
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-300 mb-2">
                API Key
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={selectedProvider.key_format}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-400 mt-2">
                Format: {selectedProvider.key_format}
              </p>
              <a
                href={selectedProvider.docs_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-400 hover:text-blue-300 mt-1 inline-block"
              >
                Get your API key →
              </a>
            </div>

            {error && (
              <div className="mb-4 bg-red-500/10 border border-red-500 text-red-500 px-3 py-2 rounded text-sm">
                {error}
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={handleSaveKey}
                disabled={saving || !apiKey}
                className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? "Saving..." : "Save"}
              </button>
              <button
                onClick={() => {
                  setShowModal(false);
                  setApiKey("");
                  setError("");
                }}
                className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-md"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
