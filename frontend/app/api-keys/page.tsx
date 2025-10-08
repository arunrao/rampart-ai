'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Copy, Eye, EyeOff, Trash2, Plus, Key, Activity, Calendar, Shield } from 'lucide-react';
import { fetchJSON, fetchWithAuth } from '@/utils/api';

interface RampartAPIKey {
  id: string;
  name: string;
  key_preview: string;
  permissions: string[];
  rate_limit_per_minute: number;
  rate_limit_per_hour: number;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
  expires_at: string | null;
  usage_stats?: {
    total_requests: number;
    tokens_used: number;
    cost_usd: number;
  };
}

interface CreateKeyRequest {
  name: string;
  permissions: string[];
  rate_limit_per_minute: number;
  rate_limit_per_hour: number;
  expires_in_days?: number;
}

const AVAILABLE_PERMISSIONS = [
  { value: 'security:analyze', label: 'Security Analysis', description: 'Analyze content for threats' },
  { value: 'security:batch', label: 'Batch Security Analysis', description: 'Analyze multiple pieces of content' },
  { value: 'filter:pii', label: 'PII Filtering', description: 'Detect and redact personal information' },
  { value: 'filter:toxicity', label: 'Toxicity Detection', description: 'Detect toxic content' },
  { value: 'llm:chat', label: 'Secure LLM Chat', description: 'Make secure LLM API calls' },
  { value: 'llm:stream', label: 'Secure LLM Streaming', description: 'Stream LLM responses securely' },
  { value: 'analytics:read', label: 'Analytics Access', description: 'Read usage analytics and metrics' },
  { value: 'test:run', label: 'Security Testing', description: 'Run security test suites' },
];

export default function APIKeysPage() {
  const [keys, setKeys] = useState<RampartAPIKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [showNewKey, setShowNewKey] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [createForm, setCreateForm] = useState<CreateKeyRequest>({
    name: '',
    permissions: ['security:analyze', 'filter:pii', 'llm:chat'],
    rate_limit_per_minute: 60,
    rate_limit_per_hour: 1000,
    expires_in_days: undefined,
  });

  useEffect(() => {
    loadAPIKeys();
  }, []);

  const loadAPIKeys = async () => {
    try {
      const data = await fetchJSON<RampartAPIKey[]>('rampart-keys');
      setKeys(data);
      setError(null);
    } catch (error) {
      setError('Failed to load API keys');
      console.error('Error loading API keys:', error);
    } finally {
      setLoading(false);
    }
  };

  const createAPIKey = async () => {
    if (!createForm.name.trim()) {
      setError('Please enter a name for the API key');
      return;
    }

    setCreating(true);
    setError(null);
    try {
      const response = await fetchWithAuth('rampart-keys', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(createForm),
      });

      if (response.ok) {
        const data = await response.json();
        setNewKey(data.key);
        setShowNewKey(true);
        setShowCreateForm(false);
        await loadAPIKeys();
        
        // Reset form
        setCreateForm({
          name: '',
          permissions: ['security:analyze', 'filter:pii', 'llm:chat'],
          rate_limit_per_minute: 60,
          rate_limit_per_hour: 1000,
          expires_in_days: undefined,
        });
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to create API key');
      }
    } catch (error) {
      setError('Failed to create API key');
      console.error('Error creating API key:', error);
    } finally {
      setCreating(false);
    }
  };

  const deleteAPIKey = async (keyId: string) => {
    if (!confirm('Are you sure you want to delete this API key? This action cannot be undone.')) {
      return;
    }

    try {
      const response = await fetchWithAuth(`rampart-keys/${keyId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        await loadAPIKeys();
        setError(null);
      } else {
        setError('Failed to delete API key');
      }
    } catch (error) {
      setError('Failed to delete API key');
      console.error('Error deleting API key:', error);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    alert('API key copied to clipboard!');
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusBadge = (key: RampartAPIKey) => {
    if (!key.is_active) {
      return <Badge variant="secondary">Inactive</Badge>;
    }
    if (key.expires_at && new Date(key.expires_at) < new Date()) {
      return <Badge variant="destructive">Expired</Badge>;
    }
    return <Badge variant="default">Active</Badge>;
  };

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-2 text-gray-600">Loading API keys...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-6">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Link href="/" className="flex items-center space-x-2 text-muted-foreground hover:text-foreground">
                <Key className="h-6 w-6" />
                <span className="font-semibold">Project Rampart</span>
              </Link>
              <span className="text-muted-foreground">/</span>
              <h1 className="text-xl font-bold text-foreground">API Keys</h1>
            </div>
            <Button onClick={() => setShowCreateForm(!showCreateForm)}>
              <Plus className="w-4 h-4 mr-2" />
              {showCreateForm ? 'Cancel' : 'Create API Key'}
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8 space-y-6">

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Create Form */}
      {showCreateForm && (
        <Card>
          <CardHeader>
            <CardTitle>Create New API Key</CardTitle>
            <CardDescription>
              Generate a new API key for your application to access Rampart services
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <Label htmlFor="name">Key Name</Label>
                <Input
                  id="name"
                  placeholder="e.g., Production App, Development, Testing"
                  value={createForm.name}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCreateForm({ ...createForm, name: e.target.value })}
                />
              </div>

              <div>
                <Label>Permissions</Label>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  {AVAILABLE_PERMISSIONS.map((perm) => (
                    <label key={perm.value} className="flex items-center space-x-2 p-2 border rounded cursor-pointer hover:bg-accent">
                      <input
                        type="checkbox"
                        checked={createForm.permissions.includes(perm.value)}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                          if (e.target.checked) {
                            setCreateForm({
                              ...createForm,
                              permissions: [...createForm.permissions, perm.value]
                            });
                          } else {
                            setCreateForm({
                              ...createForm,
                              permissions: createForm.permissions.filter(p => p !== perm.value)
                            });
                          }
                        }}
                      />
                      <div>
                        <div className="font-medium text-sm">{perm.label}</div>
                        <div className="text-xs text-muted-foreground">{perm.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="rate_minute">Requests per minute</Label>
                  <Input
                    id="rate_minute"
                    type="number"
                    min="1"
                    max="10000"
                    value={createForm.rate_limit_per_minute}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCreateForm({ ...createForm, rate_limit_per_minute: parseInt(e.target.value) })}
                  />
                </div>
                <div>
                  <Label htmlFor="rate_hour">Requests per hour</Label>
                  <Input
                    id="rate_hour"
                    type="number"
                    min="1"
                    max="100000"
                    value={createForm.rate_limit_per_hour}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCreateForm({ ...createForm, rate_limit_per_hour: parseInt(e.target.value) })}
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="expires">Expires in (days, optional)</Label>
                <Input
                  id="expires"
                  type="number"
                  min="1"
                  max="365"
                  placeholder="Leave empty for no expiration"
                  value={createForm.expires_in_days || ''}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCreateForm({ 
                    ...createForm, 
                    expires_in_days: e.target.value ? parseInt(e.target.value) : undefined 
                  })}
                />
              </div>

              <div className="flex justify-end space-x-2">
                <Button variant="outline" onClick={() => setShowCreateForm(false)}>
                  Cancel
                </Button>
                <Button onClick={createAPIKey} disabled={creating}>
                  {creating ? 'Creating...' : 'Create API Key'}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* New Key Display */}
      {newKey && (
        <Alert className="border-green-200 bg-green-50">
          <Key className="h-4 w-4" />
          <AlertDescription>
            <div className="space-y-2">
              <p className="font-medium">Your new API key has been created!</p>
              <p className="text-sm text-gray-600">
                Copy this key now - you won't be able to see it again.
              </p>
              <div className="flex items-center space-x-2 bg-white p-2 rounded border">
                <code className="flex-1 text-sm font-mono">
                  {showNewKey ? newKey : '••••••••••••••••••••••••••••••••••••••••••••'}
                </code>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowNewKey(!showNewKey)}
                >
                  {showNewKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </Button>
                <Button
                  size="sm"
                  onClick={() => copyToClipboard(newKey || '')}
                >
                  <Copy className="w-4 h-4" />
                </Button>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setNewKey(null)}
              >
                I've saved the key
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* API Keys List */}
      <div className="grid gap-4">
        {keys.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Key className="w-12 h-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium text-foreground mb-2">No API keys yet</h3>
              <p className="text-muted-foreground text-center mb-4">
                Create your first API key to start using Rampart in your applications
              </p>
              <Button onClick={() => setShowCreateForm(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Create API Key
              </Button>
            </CardContent>
          </Card>
        ) : (
          keys.map((key) => (
            <Card key={key.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center space-x-2">
                      <span>{key.name}</span>
                      {getStatusBadge(key)}
                    </CardTitle>
                    <CardDescription className="font-mono text-sm">
                      {key.key_preview}
                    </CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => deleteAPIKey(key.id)}
                    className="text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <h4 className="font-medium mb-2 flex items-center">
                      <Shield className="w-4 h-4 mr-1" />
                      Permissions
                    </h4>
                    <div className="space-y-1">
                      {key.permissions.map((perm) => (
                        <Badge key={perm} variant="secondary" className="text-xs">
                          {perm}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="font-medium mb-2 flex items-center">
                      <Activity className="w-4 h-4 mr-1" />
                      Usage Stats
                    </h4>
                    <div className="text-sm text-muted-foreground space-y-1">
                      <div>Requests: {key.usage_stats?.total_requests || 0}</div>
                      <div>Tokens: {key.usage_stats?.tokens_used || 0}</div>
                      <div>Cost: ${(key.usage_stats?.cost_usd || 0).toFixed(4)}</div>
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="font-medium mb-2 flex items-center">
                      <Calendar className="w-4 h-4 mr-1" />
                      Dates
                    </h4>
                    <div className="text-sm text-muted-foreground space-y-1">
                      <div>Created: {formatDate(key.created_at)}</div>
                      <div>Last used: {key.last_used_at ? formatDate(key.last_used_at) : 'Never'}</div>
                      {key.expires_at && (
                        <div>Expires: {formatDate(key.expires_at)}</div>
                      )}
                    </div>
                  </div>
                </div>
                
                <div className="mt-4 pt-4 border-t">
                  <div className="text-sm text-muted-foreground">
                    <strong>Rate Limits:</strong> {key.rate_limit_per_minute}/min, {key.rate_limit_per_hour}/hour
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Usage Instructions */}
      <Card>
        <CardHeader>
          <CardTitle>How to use your API keys</CardTitle>
          <CardDescription>
            Use these API keys to authenticate your applications with Rampart
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <h4 className="font-medium mb-2">JavaScript/TypeScript</h4>
              <pre className="bg-muted p-3 rounded text-sm overflow-x-auto">
{`const response = await fetch('http://localhost:8000/api/v1/security/analyze', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer rmp_live_your_api_key_here',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    content: 'User input to analyze',
    context_type: 'input'
  })
});`}
              </pre>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">Python</h4>
              <pre className="bg-muted p-3 rounded text-sm overflow-x-auto">
{`import requests

response = requests.post(
    'http://localhost:8000/api/v1/security/analyze',
    headers={
        'Authorization': 'Bearer rmp_live_your_api_key_here',
        'Content-Type': 'application/json'
    },
    json={
        'content': 'User input to analyze',
        'context_type': 'input'
    }
)`}
              </pre>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">cURL</h4>
              <pre className="bg-muted p-3 rounded text-sm overflow-x-auto">
{`curl -X POST http://localhost:8000/api/v1/security/analyze \\
  -H "Authorization: Bearer rmp_live_your_api_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{"content": "User input to analyze", "context_type": "input"}'`}
              </pre>
            </div>
          </div>
        </CardContent>
      </Card>
      </main>
    </div>
  );
}
