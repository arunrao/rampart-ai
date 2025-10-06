"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Shield, TrendingUp } from "lucide-react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { securityApi } from "@/lib/api";
import { formatDate, getSeverityColor, getStatusColor } from "@/lib/utils";
import ProtectedRoute from "@/components/ProtectedRoute";

export default function SecurityPage() {
  return (
    <ProtectedRoute>
      <SecurityPageContent />
    </ProtectedRoute>
  );
}

function SecurityPageContent() {
  const { data: incidents } = useQuery({
    queryKey: ["incidents"],
    queryFn: () => securityApi.getIncidents(),
    refetchInterval: 5000,
  });

  const { data: stats } = useQuery({
    queryKey: ["security-stats"],
    queryFn: securityApi.getSecurityStats,
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
                <Shield className="h-6 w-6" />
                <span className="font-semibold">Project Rampart</span>
              </Link>
              <span className="text-gray-400">/</span>
              <h1 className="text-xl font-bold text-gray-900">Security Dashboard</h1>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8">

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Incidents</CardTitle>
              <AlertTriangle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats?.total_incidents || 0}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Open Incidents</CardTitle>
              <AlertTriangle className="h-4 w-4 text-red-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">{stats?.open_incidents || 0}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Avg Risk Score</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats?.average_risk_score || 0}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Analyses</CardTitle>
              <Shield className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats?.total_analyses || 0}</div>
              <p className="text-xs text-muted-foreground mt-1">
                {stats?.jwt_analyses || 0} JWT, {stats?.api_key_analyses || 0} API key
              </p>
            </CardContent>
          </Card>
        </div>

        {/* API Key Usage Breakdown */}
        {stats?.api_key_breakdown && stats.api_key_breakdown.length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>API Key Usage</CardTitle>
              <CardDescription>Security analyses by API key</CardDescription>
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
                      <div className="w-32 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-green-600 h-2 rounded-full"
                          style={{
                            width: `${(key.requests / (stats.api_key_analyses || 1)) * 100}%`,
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

        {/* Threat Distribution */}
        {stats?.threat_distribution && Object.keys(stats.threat_distribution).length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Threat Distribution</CardTitle>
              <CardDescription>Types of security threats detected (JWT traces only)</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {Object.entries(stats.threat_distribution).map(([threat, count]) => (
                  <div key={threat} className="flex items-center justify-between">
                    <span className="text-sm font-medium capitalize">
                      {threat.replace(/_/g, " ")}
                    </span>
                    <div className="flex items-center space-x-2">
                      <div className="w-32 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full"
                          style={{
                            width: `${((count as number) / (stats.total_incidents || 1)) * 100}%`,
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

        {/* Incidents List */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Security Incidents</CardTitle>
            <CardDescription>
              {incidents?.length || 0} incidents detected
            </CardDescription>
          </CardHeader>
          <CardContent>
            {incidents && incidents.length > 0 ? (
              <div className="space-y-4">
                {incidents.map((incident: any) => (
                  <div
                    key={incident.id}
                    className="border rounded-lg p-4 hover:bg-slate-50 transition"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center space-x-3">
                        <Badge className={getSeverityColor(incident.severity)}>
                          {incident.severity}
                        </Badge>
                        <Badge className={getStatusColor(incident.status)}>
                          {incident.status}
                        </Badge>
                        <span className="text-sm font-medium capitalize">
                          {incident.threat_type.replace(/_/g, " ")}
                        </span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {formatDate(incident.detected_at)}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mb-2">
                      {incident.content_preview}
                    </p>
                    {incident.trace_id && (
                      <div className="text-xs text-muted-foreground">
                        Trace ID: {incident.trace_id}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <Shield className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">No security incidents detected</p>
                <p className="text-sm text-muted-foreground">
                  Your AI applications are secure
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
