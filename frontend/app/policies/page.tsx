"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Plus, Power, Trash2 } from "lucide-react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { policyApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import ProtectedRoute from "@/components/ProtectedRoute";

export default function PoliciesPage() {
  return (
    <ProtectedRoute>
      <PoliciesPageContent />
    </ProtectedRoute>
  );
}

function PoliciesPageContent() {
  const queryClient = useQueryClient();

  const { data: policies } = useQuery({
    queryKey: ["policies"],
    queryFn: () => policyApi.getPolicies(),
  });

  const { data: templates } = useQuery({
    queryKey: ["policy-templates"],
    queryFn: policyApi.getTemplates,
  });

  const toggleMutation = useMutation({
    mutationFn: (policyId: string) => policyApi.togglePolicy(policyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["policies"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (policyId: string) => policyApi.deletePolicy(policyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["policies"] });
    },
  });

  const createFromTemplateMutation = useMutation({
    mutationFn: (template: string) => policyApi.createFromTemplate(template),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["policies"] });
    },
  });

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      {/* Header */}
      <header className="border-b bg-white">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Link href="/" className="flex items-center space-x-2 text-gray-600 hover:text-gray-900">
                <FileText className="h-6 w-6" />
                <span className="font-semibold">Project Rampart</span>
              </Link>
              <span className="text-gray-400">/</span>
              <h1 className="text-xl font-bold text-gray-900">Policy Management</h1>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8">
        {/* Info Banner */}
        <Card className="mb-6 border-blue-200 bg-blue-50">
          <CardContent className="pt-6">
            <p className="text-sm text-blue-900">
              📋 <strong>Note:</strong> Policy management is currently under development. 
              These settings will apply to both JWT and API key authenticated requests once implemented.
            </p>
          </CardContent>
        </Card>

        {/* Compliance Templates */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Compliance Templates</CardTitle>
            <CardDescription>
              Quick-start policies for common compliance frameworks
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {templates?.templates?.map((template: any) => (
                <div
                  key={template.id}
                  className="border rounded-lg p-4 hover:bg-slate-50 transition"
                >
                  <h3 className="font-semibold mb-2">{template.name}</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    {template.description}
                  </p>
                  <Button
                    size="sm"
                    onClick={() => createFromTemplateMutation.mutate(template.id)}
                    disabled={createFromTemplateMutation.isPending}
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Create Policy
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Active Policies */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Active Policies</CardTitle>
                <CardDescription>
                  {policies?.length || 0} policies configured
                </CardDescription>
              </div>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Create Policy
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {policies && policies.length > 0 ? (
              <div className="space-y-4">
                {policies.map((policy: any) => (
                  <div
                    key={policy.id}
                    className="border rounded-lg p-4 hover:bg-slate-50 transition"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center space-x-3">
                        <h3 className="font-semibold">{policy.name}</h3>
                        <Badge variant={policy.enabled ? "default" : "secondary"}>
                          {policy.enabled ? "Enabled" : "Disabled"}
                        </Badge>
                        <Badge variant="outline" className="capitalize">
                          {policy.policy_type.replace(/_/g, " ")}
                        </Badge>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => toggleMutation.mutate(policy.id)}
                          disabled={toggleMutation.isPending}
                        >
                          <Power className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => deleteMutation.mutate(policy.id)}
                          disabled={deleteMutation.isPending}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                    {policy.description && (
                      <p className="text-sm text-muted-foreground mb-3">
                        {policy.description}
                      </p>
                    )}
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center space-x-4">
                        <span className="text-muted-foreground">
                          {policy.rules?.length || 0} rules
                        </span>
                        {policy.tags && policy.tags.length > 0 && (
                          <div className="flex items-center space-x-1">
                            {policy.tags.map((tag: string) => (
                              <Badge key={tag} variant="outline" className="text-xs">
                                {tag}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                      <span className="text-xs text-muted-foreground">
                        Updated {formatDate(policy.updated_at)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">No policies configured</p>
                <p className="text-sm text-muted-foreground mb-4">
                  Create a policy or use a compliance template
                </p>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Create Your First Policy
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
