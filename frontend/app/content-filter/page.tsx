"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Shield, Search } from "lucide-react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { contentFilterApi } from "@/lib/api";
import ProtectedRoute from "@/components/ProtectedRoute";

export default function ContentFilterPage() {
  return (
    <ProtectedRoute>
      <ContentFilterPageContent />
    </ProtectedRoute>
  );
}

function ContentFilterPageContent() {
  const [content, setContent] = useState("");
  const [filterResult, setFilterResult] = useState<any>(null);

  const { data: stats } = useQuery({
    queryKey: ["filter-stats"],
    queryFn: contentFilterApi.getFilterStats,
    refetchInterval: 5000,
  });

  const filterMutation = useMutation({
    mutationFn: (data: any) => contentFilterApi.filterContent(data),
    onSuccess: (data) => {
      setFilterResult(data);
    },
  });

  const handleFilter = () => {
    if (!content.trim()) return;
    
    filterMutation.mutate({
      content,
      filters: ["pii", "toxicity"],
      redact: true,
    });
  };

  return (
    <div className="min-h-screen bg-background p-6">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Link href="/" className="flex items-center space-x-2 text-muted-foreground hover:text-foreground">
                <Shield className="h-6 w-6" />
                <span className="font-semibold">Project Rampart</span>
              </Link>
              <span className="text-muted-foreground">/</span>
              <h1 className="text-xl font-bold text-foreground">Content Filter</h1>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8">

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Filtered</CardTitle>
              <Shield className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats?.total_filtered || 0}</div>
              <p className="text-xs text-muted-foreground mt-1">
                {stats?.jwt_filtered || 0} JWT, {stats?.api_key_filtered || 0} API key
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">PII Detected</CardTitle>
              <Shield className="h-4 w-4 text-orange-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-orange-600">
                {stats?.total_pii_detected || 0}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Unsafe Content</CardTitle>
              <Shield className="h-4 w-4 text-red-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">
                {stats?.unsafe_content_count || 0}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Avg Toxicity</CardTitle>
              <Shield className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats?.average_toxicity_score || 0}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* API Key Usage Breakdown */}
        {stats?.api_key_breakdown && stats.api_key_breakdown.length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>API Key Usage</CardTitle>
              <CardDescription>Content filtering by API key</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {stats.api_key_breakdown.map((key: any) => (
                  <div key={key.key_preview} className="flex items-center justify-between">
                    <div className="flex flex-col">
                      <span className="text-sm font-medium">{key.key_name}</span>
                      <span className="text-xs text-muted-foreground">{key.key_preview}</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <div className="w-32 bg-muted rounded-full h-2">
                        <div
                          className="bg-green-600 h-2 rounded-full"
                          style={{
                            width: `${(key.requests / (stats.api_key_filtered || 1)) * 100}%`,
                          }}
                        />
                      </div>
                      <span className="text-sm text-muted-foreground w-12 text-right">
                        {key.requests}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* PII Distribution */}
        {stats?.pii_type_distribution && Object.keys(stats.pii_type_distribution).length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>PII Type Distribution</CardTitle>
              <CardDescription>Types of PII detected (JWT traces only)</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {Object.entries(stats.pii_type_distribution).map(([type, count]) => (
                  <div key={type} className="flex items-center justify-between">
                    <span className="text-sm font-medium capitalize">
                      {type.replace(/_/g, " ")}
                    </span>
                    <div className="flex items-center space-x-2">
                      <div className="w-32 bg-muted rounded-full h-2">
                        <div
                          className="bg-orange-600 h-2 rounded-full"
                          style={{
                            width: `${((count as number) / (stats.total_pii_detected || 1)) * 100}%`,
                          }}
                        />
                      </div>
                      <span className="text-sm text-muted-foreground w-8 text-right">
                        {count as number}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Content Filter Tool */}
        <Card>
          <CardHeader>
            <CardTitle>Test Content Filter</CardTitle>
            <CardDescription>
              Analyze content for PII, toxicity, and other issues
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">
                  Content to Analyze
                </label>
                <textarea
                  className="w-full h-32 px-3 py-2 border border-border rounded-md bg-card text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder="Enter content to analyze for PII, toxicity, etc..."
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                />
              </div>
              <Button
                onClick={handleFilter}
                disabled={filterMutation.isPending || !content.trim()}
              >
                <Search className="h-4 w-4 mr-2" />
                Analyze Content
              </Button>

              {/* Results */}
              {filterResult && (
                <div className="mt-6 space-y-4">
                  <div className="flex items-center space-x-4">
                    <Badge
                      variant={filterResult.is_safe ? "default" : "destructive"}
                      className="text-base px-4 py-1"
                    >
                      {filterResult.is_safe ? "Safe" : "Unsafe"}
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      Processing time: {filterResult.processing_time_ms.toFixed(2)}ms
                    </span>
                  </div>

                  {filterResult.pii_detected && filterResult.pii_detected.length > 0 && (
                    <div className="border rounded-lg p-4 bg-orange-50 dark:bg-orange-950/30">
                      <h3 className="font-semibold mb-2 text-orange-900 dark:text-orange-100">
                        PII Detected ({filterResult.pii_detected.length})
                      </h3>
                      <div className="space-y-2">
                        {filterResult.pii_detected.map((pii: any, idx: number) => (
                          <div key={idx} className="text-sm">
                            <Badge variant="outline" className="mr-2">
                              {pii.type}
                            </Badge>
                            <span className="text-muted-foreground">
                              Confidence: {(pii.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {filterResult.toxicity_scores && (
                    <div className="border rounded-lg p-4 bg-red-50 dark:bg-red-950/30">
                      <h3 className="font-semibold mb-2 text-red-900 dark:text-red-100">
                        Toxicity Analysis
                      </h3>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <span className="text-muted-foreground">Toxicity:</span>
                          <span className="ml-2 font-medium">
                            {(filterResult.toxicity_scores.toxicity * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Severe:</span>
                          <span className="ml-2 font-medium">
                            {(filterResult.toxicity_scores.severe_toxicity * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Insult:</span>
                          <span className="ml-2 font-medium">
                            {(filterResult.toxicity_scores.insult * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Threat:</span>
                          <span className="ml-2 font-medium">
                            {(filterResult.toxicity_scores.threat * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  {filterResult.filtered_content && (
                    <div className="border rounded-lg p-4 bg-blue-50 dark:bg-blue-950/30">
                      <h3 className="font-semibold mb-2 text-blue-900 dark:text-blue-100">
                        Filtered Content
                      </h3>
                      <p className="text-sm">{filterResult.filtered_content}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
