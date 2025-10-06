"use client";

import { useQuery } from "@tanstack/react-query";
import { Shield, Activity, AlertTriangle, FileText } from "lucide-react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { observabilityApi, securityApi, contentFilterApi } from "@/lib/api";
import { formatCurrency, formatNumber } from "@/lib/utils";
import ProtectedRoute from "@/components/ProtectedRoute";

export default function HomePage() {
  return (
    <ProtectedRoute>
      <HomePageContent />
    </ProtectedRoute>
  );
}

function HomePageContent() {
  const { data: analyticsData } = useQuery({
    queryKey: ["analytics"],
    queryFn: observabilityApi.getAnalyticsSummary,
    refetchInterval: 5000,
  });

  const { data: securityStats } = useQuery({
    queryKey: ["security-stats"],
    queryFn: securityApi.getSecurityStats,
    refetchInterval: 5000,
  });

  const { data: filterStats } = useQuery({
    queryKey: ["filter-stats"],
    queryFn: contentFilterApi.getFilterStats,
    refetchInterval: 5000,
  });

  const stats = [
    {
      title: "Total Requests",
      value: formatNumber(analyticsData?.total_requests || 0),
      description: `${analyticsData?.total_traces || 0} traces, ${analyticsData?.api_key_requests || 0} API calls`,
      icon: Activity,
      href: "/observability",
    },
    {
      title: "Security Incidents",
      value: formatNumber(securityStats?.open_incidents || 0),
      description: `${securityStats?.total_incidents || 0} total detected`,
      icon: AlertTriangle,
      href: "/security",
    },
    {
      title: "Content Filtered",
      value: formatNumber(filterStats?.total_filtered || 0),
      description: `${filterStats?.total_pii_detected || 0} PII detected`,
      icon: Shield,
      href: "/content-filter",
    },
    {
      title: "Active Policies",
      value: "0",
      description: "Compliance rules enforced",
      icon: FileText,
      href: "/policies",
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Main Content */}
      <main className="container mx-auto px-6 py-12">
        {/* Hero Section */}
        <div className="mb-12 text-center">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            Secure Your AI Applications
          </h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Comprehensive security and observability platform combining prompt injection detection,
            data exfiltration monitoring, content filtering, and policy management.
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          {stats.map((stat) => (
            <Link key={stat.title} href={stat.href}>
              <Card className="hover:shadow-lg transition-shadow cursor-pointer">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">
                    {stat.title}
                  </CardTitle>
                  <stat.icon className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stat.value}</div>
                  <p className="text-xs text-muted-foreground">
                    {stat.description}
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>

        {/* Cost & Performance */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-12">
          <Card>
            <CardHeader>
              <CardTitle>Cost Overview</CardTitle>
              <CardDescription>Total LLM API costs</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {formatCurrency(analyticsData?.total_cost || 0)}
              </div>
              <p className="text-sm text-muted-foreground mt-2">
                {formatNumber(analyticsData?.total_tokens || 0)} tokens used
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Performance</CardTitle>
              <CardDescription>Average response time</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {analyticsData?.average_latency_ms?.toFixed(0) || 0}ms
              </div>
              <p className="text-sm text-muted-foreground mt-2">
                Across {formatNumber(analyticsData?.total_requests || 0)} operations
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Features */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Shield className="h-5 w-5 text-blue-600" />
                <span>Security & Trust Layer</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-start space-x-2">
                <div className="w-2 h-2 bg-blue-600 rounded-full mt-2" />
                <div>
                  <p className="font-medium">Prompt Injection Detection</p>
                  <p className="text-sm text-muted-foreground">
                    Analyze inputs for hidden instructions and jailbreak attempts
                  </p>
                </div>
              </div>
              <div className="flex items-start space-x-2">
                <div className="w-2 h-2 bg-blue-600 rounded-full mt-2" />
                <div>
                  <p className="font-medium">Data Exfiltration Monitoring</p>
                  <p className="text-sm text-muted-foreground">
                    Scan outputs for sensitive data leakage
                  </p>
                </div>
              </div>
              <div className="flex items-start space-x-2">
                <div className="w-2 h-2 bg-blue-600 rounded-full mt-2" />
                <div>
                  <p className="font-medium">Zero-click Attack Prevention</p>
                  <p className="text-sm text-muted-foreground">
                    Detect suspicious indirect prompts
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Activity className="h-5 w-5 text-green-600" />
                <span>Observability Layer</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-start space-x-2">
                <div className="w-2 h-2 bg-green-600 rounded-full mt-2" />
                <div>
                  <p className="font-medium">Trace Collection</p>
                  <p className="text-sm text-muted-foreground">
                    Track all LLM calls with detailed spans
                  </p>
                </div>
              </div>
              <div className="flex items-start space-x-2">
                <div className="w-2 h-2 bg-green-600 rounded-full mt-2" />
                <div>
                  <p className="font-medium">Cost Tracking</p>
                  <p className="text-sm text-muted-foreground">
                    Monitor token usage and API costs
                  </p>
                </div>
              </div>
              <div className="flex items-start space-x-2">
                <div className="w-2 h-2 bg-green-600 rounded-full mt-2" />
                <div>
                  <p className="font-medium">Performance Metrics</p>
                  <p className="text-sm text-muted-foreground">
                    Latency monitoring and optimization
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
