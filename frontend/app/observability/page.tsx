"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, Clock, DollarSign, Zap } from "lucide-react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { observabilityApi } from "@/lib/api";
import { formatDate, formatCurrency, formatNumber, getStatusColor } from "@/lib/utils";
import ProtectedRoute from "@/components/ProtectedRoute";

export default function ObservabilityPage() {
  return (
    <ProtectedRoute>
      <ObservabilityPageContent />
    </ProtectedRoute>
  );
}

function ObservabilityPageContent() {
  const { data: traces } = useQuery({
    queryKey: ["traces"],
    queryFn: () => observabilityApi.getTraces({ limit: 50 }),
    refetchInterval: 5000,
  });

  const { data: analytics } = useQuery({
    queryKey: ["analytics"],
    queryFn: observabilityApi.getAnalyticsSummary,
    refetchInterval: 5000,
  });

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="border-b bg-white">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Link href="/" className="flex items-center space-x-2 text-gray-600 hover:text-gray-900">
                <Activity className="h-6 w-6" />
                <span className="font-semibold">Project Rampart</span>
              </Link>
              <span className="text-gray-400">/</span>
              <h1 className="text-xl font-bold text-gray-900">Observability</h1>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8">
        {/* Analytics Summary */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Traces</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatNumber(analytics?.total_traces || 0)}
              </div>
              <p className="text-xs text-muted-foreground">
                {formatNumber(analytics?.total_spans || 0)} spans
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Cost</CardTitle>
              <DollarSign className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatCurrency(analytics?.total_cost || 0)}
              </div>
              <p className="text-xs text-muted-foreground">
                {formatNumber(analytics?.total_tokens || 0)} tokens
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Avg Latency</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {analytics?.average_latency_ms?.toFixed(0) || 0}ms
              </div>
              <p className="text-xs text-muted-foreground">Response time</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Performance</CardTitle>
              <Zap className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">Good</div>
              <p className="text-xs text-muted-foreground">System health</p>
            </CardContent>
          </Card>
        </div>

        {/* Traces List */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Traces</CardTitle>
            <CardDescription>
              {traces?.length || 0} LLM API calls tracked
            </CardDescription>
          </CardHeader>
          <CardContent>
            {traces && traces.length > 0 ? (
              <div className="space-y-4">
                {traces.map((trace: any) => (
                  <div
                    key={trace.id}
                    className="border rounded-lg p-4 hover:bg-slate-50 transition"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center space-x-3">
                        <Badge className={getStatusColor(trace.status)}>
                          {trace.status}
                        </Badge>
                        <span className="font-medium">{trace.name}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {formatDate(trace.created_at)}
                      </span>
                    </div>
                    <div className="grid grid-cols-4 gap-4 text-sm">
                      <div>
                        <p className="text-muted-foreground">Tokens</p>
                        <p className="font-medium">{formatNumber(trace.total_tokens)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Cost</p>
                        <p className="font-medium">{formatCurrency(trace.total_cost)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Latency</p>
                        <p className="font-medium">{trace.total_latency_ms.toFixed(0)}ms</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Session</p>
                        <p className="font-medium text-xs truncate">
                          {trace.session_id || "N/A"}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <Activity className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">No traces recorded yet</p>
                <p className="text-sm text-muted-foreground">
                  Start making LLM API calls to see traces here
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
