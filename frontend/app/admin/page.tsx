"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Clock,
  Coins,
  DollarSign,
  Gauge,
  Key,
  ShieldOff,
  Users,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import ProtectedRoute from "@/components/ProtectedRoute";
import { useAuth } from "@/contexts/AuthContext";
import { adminApi, type AdminRange } from "@/lib/api";
import { formatCurrency, formatDate, formatNumber } from "@/lib/utils";

const RANGES: { value: AdminRange; label: string }[] = [
  { value: "24h", label: "24h" },
  { value: "7d", label: "7d" },
  { value: "30d", label: "30d" },
  { value: "90d", label: "90d" },
];

const COLORS = {
  requests: "hsl(221.2 83.2% 53.3%)",
  errors: "hsl(0 84.2% 60.2%)",
  cost: "hsl(142.1 76.2% 36.3%)",
  tokens: "hsl(262.1 83.3% 57.8%)",
};

export default function AdminPage() {
  return (
    <ProtectedRoute>
      <AdminGate />
    </ProtectedRoute>
  );
}

function AdminGate() {
  const { isSuperAdmin } = useAuth();
  if (!isSuperAdmin) {
    return (
      <div className="min-h-screen bg-background p-6">
        <main className="container mx-auto px-6 py-16 max-w-xl text-center space-y-4">
          <ShieldOff className="h-12 w-12 mx-auto text-muted-foreground" />
          <h1 className="text-2xl font-bold">Super-admin access required</h1>
          <p className="text-muted-foreground">
            Your account is not listed in <code className="text-xs bg-muted px-1 py-0.5 rounded">SUPER_ADMIN_EMAILS</code>.
          </p>
          <Link href="/" className="text-primary underline text-sm">Back to dashboard</Link>
        </main>
      </div>
    );
  }
  return <AdminDashboard />;
}

function AdminDashboard() {
  const [range, setRange] = useState<AdminRange>("24h");

  const stats = useQuery({
    queryKey: ["admin", "stats", range],
    queryFn: () => adminApi.getStats(range),
    refetchInterval: 30_000,
  });
  const series = useQuery({
    queryKey: ["admin", "timeseries", range],
    queryFn: () => adminApi.getTimeseries(range),
    refetchInterval: 30_000,
  });
  const byUser = useQuery({
    queryKey: ["admin", "cost-by-user", range],
    queryFn: () => adminApi.getCostByUser(range, 15),
    refetchInterval: 60_000,
  });
  const byEndpoint = useQuery({
    queryKey: ["admin", "cost-by-endpoint", range],
    queryFn: () => adminApi.getCostByEndpoint(range),
    refetchInterval: 60_000,
  });

  const s = stats.data;
  const req = s?.requests;
  const errorRate = req?.total ? (req.errors / req.total) * 100 : 0;
  const hourly = series.data?.interval === "hour";
  const points = (series.data?.points ?? []).map((p: any) => ({
    ...p,
    label: hourly
      ? new Date(p.bucket).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })
      : new Date(p.bucket).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
  }));

  return (
    <div className="min-h-screen bg-background p-6">
      <header className="border-b bg-card">
        <div className="container mx-auto px-6 py-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <Link href="/" className="flex items-center space-x-2 text-muted-foreground hover:text-foreground">
              <Gauge className="h-6 w-6" />
              <span className="font-semibold">Project Rampart</span>
            </Link>
            <span className="text-muted-foreground">/</span>
            <h1 className="text-xl font-bold text-foreground">Super Admin</h1>
            <Badge variant="outline">system-wide</Badge>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex rounded-lg border bg-background p-1">
              {RANGES.map((r) => (
                <button
                  key={r.value}
                  onClick={() => setRange(r.value)}
                  className={`px-3 py-1 text-sm rounded-md transition-colors ${
                    range === r.value ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
            {s?.generated_at && (
              <span className="text-xs text-muted-foreground hidden md:inline">
                Updated {formatDate(s.generated_at)}
              </span>
            )}
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8 space-y-8">
        {stats.isError && (
          <Card className="border-destructive">
            <CardContent className="p-4 text-sm text-destructive">
              Failed to load admin stats: {(stats.error as any)?.response?.data?.detail ?? String(stats.error)}
            </CardContent>
          </Card>
        )}

        {/* Traffic KPIs */}
        <section>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Traffic · last {range}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <Kpi
              title="Requests"
              icon={Activity}
              value={formatNumber(req?.total ?? 0)}
              sub={`${formatNumber(req?.unique_users ?? 0)} unique users`}
            />
            <Kpi
              title="Error rate"
              icon={AlertTriangle}
              value={`${errorRate.toFixed(1)}%`}
              valueClass={errorRate > 5 ? "text-red-600" : errorRate > 1 ? "text-amber-600" : "text-green-600"}
              sub={`${formatNumber(req?.errors ?? 0)} errors · ${formatNumber(req?.blocked ?? 0)} blocked · ${formatNumber(req?.auth_failures ?? 0)} auth failures`}
            />
            <Kpi
              title="Latency"
              icon={Clock}
              value={req?.avg_latency_ms != null ? `${req.avg_latency_ms.toFixed(0)}ms` : "—"}
              sub={req?.p95_latency_ms != null ? `p95 ${req.p95_latency_ms.toFixed(0)}ms` : "No data"}
            />
            <Kpi
              title="Users & keys"
              icon={Users}
              value={formatNumber(s?.users?.active ?? 0)}
              sub={`${formatNumber(s?.users?.total ?? 0)} total · +${s?.users?.new_last_7d ?? 0} this week · ${formatNumber(s?.api_keys?.active ?? 0)} active keys`}
            />
          </div>
        </section>

        {/* Cost KPIs */}
        <section>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Cost & usage · last {range}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <Kpi
              title="Cost"
              icon={DollarSign}
              value={formatCurrency(s?.usage?.cost_usd ?? 0)}
              sub={`${formatCurrency(s?.usage_all_time?.cost_usd ?? 0)} all-time`}
            />
            <Kpi
              title="Tokens"
              icon={Coins}
              value={formatNumber(s?.usage?.tokens ?? 0)}
              sub={`${formatNumber(s?.usage_all_time?.tokens ?? 0)} all-time`}
            />
            <Kpi
              title="API-key requests"
              icon={Key}
              value={formatNumber(s?.usage?.requests ?? 0)}
              sub={`${formatNumber(s?.usage?.active_keys ?? 0)} keys with traffic`}
            />
            <Kpi
              title="Avg cost / request"
              icon={DollarSign}
              value={formatCurrency(s?.usage?.requests ? s.usage.cost_usd / s.usage.requests : 0)}
              sub={
                s?.usage?.requests
                  ? `${formatNumber(Math.round(s.usage.tokens / s.usage.requests))} tokens / request`
                  : "No API-key traffic"
              }
            />
          </div>
        </section>

        {/* Charts */}
        <section className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Request volume</CardTitle>
              <CardDescription>Requests and errors per {hourly ? "hour" : "day"} (from audit log)</CardDescription>
            </CardHeader>
            <CardContent className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={points} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={24} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} width={48} />
                  <Tooltip contentStyle={{ fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Area type="monotone" dataKey="requests" stroke={COLORS.requests} fill={COLORS.requests} fillOpacity={0.15} />
                  <Area type="monotone" dataKey="errors" stroke={COLORS.errors} fill={COLORS.errors} fillOpacity={0.15} />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Spend & tokens</CardTitle>
              <CardDescription>Cost (USD) and tokens per {hourly ? "hour" : "day"} (from API-key usage)</CardDescription>
            </CardHeader>
            <CardContent className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={points} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={24} />
                  <YAxis yAxisId="cost" tick={{ fontSize: 11 }} width={56} tickFormatter={(v) => `$${Number(v).toFixed(2)}`} />
                  <YAxis yAxisId="tokens" orientation="right" tick={{ fontSize: 11 }} width={56} tickFormatter={(v) => formatNumber(Number(v))} />
                  <Tooltip
                    contentStyle={{ fontSize: 12 }}
                    formatter={(v: any, name: any) => (name === "cost_usd" ? formatCurrency(Number(v)) : formatNumber(Number(v)))}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar yAxisId="cost" dataKey="cost_usd" name="cost_usd" fill={COLORS.cost} radius={[3, 3, 0, 0]} />
                  <Bar yAxisId="tokens" dataKey="tokens" name="tokens" fill={COLORS.tokens} radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </section>

        {/* Breakdown tables */}
        <section className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Top spenders</CardTitle>
              <CardDescription>
                Users ranked by API-key cost · {formatCurrency(byUser.data?.total_cost_usd ?? 0)} shown
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table
                empty="No API-key usage in this window."
                headers={["User", "Requests", "Tokens", "Cost", "Keys", "Last used"]}
                rows={(byUser.data?.users ?? []).map((u: any) => [
                  <span key="e" className="font-medium truncate block max-w-[220px]" title={u.email}>{u.email}</span>,
                  formatNumber(u.requests),
                  formatNumber(u.tokens),
                  <span key="c" className="font-mono">{formatCurrency(u.cost_usd)}</span>,
                  u.active_keys,
                  u.last_used_at ? formatDate(u.last_used_at) : "—",
                ])}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Cost by endpoint</CardTitle>
              <CardDescription>Which features are consuming spend</CardDescription>
            </CardHeader>
            <CardContent>
              <Table
                empty="No API-key usage in this window."
                headers={["Endpoint", "Requests", "Tokens", "Cost", "Keys"]}
                rows={(byEndpoint.data?.endpoints ?? []).map((e: any) => [
                  <code key="p" className="text-xs">{e.endpoint}</code>,
                  formatNumber(e.requests),
                  formatNumber(e.tokens),
                  <span key="c" className="font-mono">{formatCurrency(e.cost_usd)}</span>,
                  e.unique_keys,
                ])}
              />
            </CardContent>
          </Card>
        </section>

        <Card>
          <CardHeader>
            <CardTitle>Busiest endpoints</CardTitle>
            <CardDescription>Top 10 by request count in the last {range}, from the audit log (all auth methods)</CardDescription>
          </CardHeader>
          <CardContent>
            <Table
              empty="No audited requests in this window."
              headers={["Endpoint", "Requests", "Errors", "Error rate", "Avg latency"]}
              rows={(s?.top_endpoints ?? []).map((e: any) => [
                <code key="p" className="text-xs">{e.endpoint}</code>,
                formatNumber(e.count),
                formatNumber(e.errors),
                `${e.count ? ((e.errors / e.count) * 100).toFixed(1) : "0.0"}%`,
                e.avg_latency_ms != null ? `${e.avg_latency_ms.toFixed(0)}ms` : "—",
              ])}
            />
          </CardContent>
        </Card>

        <UsersTable />
        <AuditLogTable />
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------

function UsersTable() {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"created_at" | "cost_usd" | "requests" | "last_seen">("cost_usd");
  const [offset, setOffset] = useState(0);
  const limit = 25;

  const q = useQuery({
    queryKey: ["admin", "users", search, sort, offset],
    queryFn: () => adminApi.getUsers({ search: search || undefined, sort, limit, offset }),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle>All users</CardTitle>
            <CardDescription>{formatNumber(q.data?.total ?? 0)} accounts · all-time usage per user</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Input
              placeholder="Search email…"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
              className="w-56 h-9"
            />
            <select
              value={sort}
              onChange={(e) => { setSort(e.target.value as any); setOffset(0); }}
              className="h-9 rounded-md border bg-background px-2 text-sm"
            >
              <option value="cost_usd">Sort: cost</option>
              <option value="requests">Sort: requests</option>
              <option value="last_seen">Sort: last seen</option>
              <option value="created_at">Sort: newest</option>
            </select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Table
          empty="No users match."
          headers={["Email", "Status", "Keys", "Requests", "Tokens", "Cost", "Last seen", "Joined"]}
          rows={(q.data?.users ?? []).map((u: any) => [
            <span key="e" className="font-medium">{u.email}</span>,
            <Badge key="s" variant={u.is_active ? "secondary" : "destructive"}>{u.is_active ? "active" : "disabled"}</Badge>,
            `${u.active_api_key_count}/${u.api_key_count}`,
            formatNumber(u.requests),
            formatNumber(u.tokens),
            <span key="c" className="font-mono">{formatCurrency(u.cost_usd)}</span>,
            u.last_seen ? formatDate(u.last_seen) : "—",
            formatDate(u.created_at),
          ])}
        />
        <Pager total={q.data?.total ?? 0} limit={limit} offset={offset} onChange={setOffset} />
      </CardContent>
    </Card>
  );
}

function AuditLogTable() {
  const [endpoint, setEndpoint] = useState("");
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const q = useQuery({
    queryKey: ["admin", "audit", endpoint, errorsOnly, offset],
    queryFn: () => adminApi.getAuditLogs({ endpoint: endpoint || undefined, errors_only: errorsOnly, limit, offset }),
    refetchInterval: 15_000,
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle>Recent requests</CardTitle>
            <CardDescription>{formatNumber(q.data?.total ?? 0)} audit-log entries</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Input
              placeholder="Filter endpoint…"
              value={endpoint}
              onChange={(e) => { setEndpoint(e.target.value); setOffset(0); }}
              className="w-56 h-9"
            />
            <Button
              variant={errorsOnly ? "default" : "outline"}
              size="sm"
              onClick={() => { setErrorsOnly(!errorsOnly); setOffset(0); }}
            >
              <AlertTriangle className="h-4 w-4 mr-1" /> Errors only
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Table
          empty="No audit-log entries."
          headers={["Time", "User", "Key", "Method", "Endpoint", "Status", "Latency", "IP"]}
          rows={(q.data?.logs ?? []).map((l: any) => [
            <span key="t" className="whitespace-nowrap">{formatDate(l.timestamp)}</span>,
            <span key="u" className="truncate block max-w-[180px]" title={l.email ?? l.user_id ?? ""}>{l.email ?? l.user_id ?? "—"}</span>,
            l.api_key_preview ? <code key="k" className="text-xs">{l.api_key_preview}</code> : "—",
            <code key="m" className="text-xs">{l.http_method}</code>,
            <code key="p" className="text-xs">{l.endpoint}</code>,
            <StatusBadge key="s" code={l.status_code} />,
            l.processing_time_ms != null ? `${l.processing_time_ms.toFixed(0)}ms` : "—",
            <span key="ip" className="font-mono text-xs">{l.ip_address}</span>,
          ])}
        />
        <Pager total={q.data?.total ?? 0} limit={limit} offset={offset} onChange={setOffset} />
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Small presentational helpers
// ---------------------------------------------------------------------------

function Kpi({
  title, icon: Icon, value, sub, valueClass = "",
}: { title: string; icon: any; value: string; sub?: string; valueClass?: string }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold ${valueClass}`}>{value}</div>
        {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
      </CardContent>
    </Card>
  );
}

function Table({ headers, rows, empty }: { headers: string[]; rows: React.ReactNode[][]; empty: string }) {
  if (!rows.length) return <p className="text-sm text-muted-foreground py-6 text-center">{empty}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
            {headers.map((h) => <th key={h} className="py-2 pr-4 font-medium">{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, i) => (
            <tr key={i} className="border-b last:border-0 hover:bg-accent/40">
              {cells.map((c, j) => <td key={j} className="py-2 pr-4 align-middle">{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Pager({ total, limit, offset, onChange }: { total: number; limit: number; offset: number; onChange: (o: number) => void }) {
  if (total <= limit) return null;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  return (
    <div className="flex items-center justify-between pt-4 text-sm text-muted-foreground">
      <span>Page {page} of {pages}</span>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Previous</Button>
        <Button variant="outline" size="sm" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Next</Button>
      </div>
    </div>
  );
}

function StatusBadge({ code }: { code: number | null }) {
  if (code == null) return <span>—</span>;
  const cls = code >= 500 ? "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300"
    : code >= 400 ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
    : "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300";
  return <Badge className={`${cls} border-transparent`}>{code}</Badge>;
}
