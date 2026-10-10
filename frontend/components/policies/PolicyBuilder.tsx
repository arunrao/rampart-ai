"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, Eye, Ban, Eraser, Loader2, X } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { policyApi } from "@/lib/api";

/**
 * Plain-language policy builder. Users pick what to look for and what to do about it;
 * the mapping to rule conditions/actions/priorities happens here so they never see them.
 */

type Action = "redact" | "flag" | "block";

interface Protection {
  condition: string;
  label: string;
  help: string;
  example: string;
  /** Actions that make sense for this protection; the first one is the default. */
  actions: Action[];
  group: "Personal data" | "Money & secrets" | "Conduct" | "Privacy requests";
}

const PROTECTIONS: Protection[] = [
  {
    condition: "contains_pii",
    label: "Personal information",
    help: "Names, home addresses, dates of birth, Social Security numbers, card and account numbers.",
    example: "My SSN is 123-45-6789",
    actions: ["redact", "flag", "block"],
    group: "Personal data",
  },
  {
    condition: "contains_phi",
    label: "Health information",
    help: "Patient details, diagnoses, prescriptions, medical record numbers.",
    example: "Patient diagnosed with hypertension",
    actions: ["redact", "flag", "block"],
    group: "Personal data",
  },
  {
    condition: "contains_card_data",
    label: "Credit card numbers",
    help: "Full card numbers, in any common format.",
    example: "Card 4111 1111 1111 1111",
    actions: ["redact", "block", "flag"],
    group: "Money & secrets",
  },
  {
    condition: "contains_cvv",
    label: "Card security codes (CVV)",
    help: "The 3–4 digit code from the back of a card. These should never be stored or sent anywhere.",
    example: "cvv: 123",
    actions: ["block", "flag"],
    group: "Money & secrets",
  },
  {
    condition: "encryption_required",
    label: "Passwords & API keys",
    help: "Things like password=…, api_key: … or access_token=… typed in plain text.",
    example: "password=hunter2secret",
    actions: ["block", "flag", "redact"],
    group: "Money & secrets",
  },
  {
    condition: "profanity",
    label: "Profanity",
    help: "Common swear words.",
    example: "this is bullshit",
    actions: ["block", "flag"],
    group: "Conduct",
  },
  {
    condition: "data_sale_opt_out",
    label: "\u201cDon\u2019t sell my data\u201d requests",
    help: "Someone asking to opt out of data sharing or withdraw consent.",
    example: "Please do not sell my information",
    actions: ["flag"],
    group: "Privacy requests",
  },
  {
    condition: "right_to_delete",
    label: "\u201cDelete my data\u201d requests",
    help: "Someone asking you to erase their information.",
    example: "Delete my data from your systems",
    actions: ["flag"],
    group: "Privacy requests",
  },
];

const ACTION_META: Record<Action, { label: string; help: string; icon: typeof Eye }> = {
  redact: { label: "Remove it", help: "Replace the sensitive part so it never reaches the model.", icon: Eraser },
  flag: { label: "Just tell me", help: "Let it through, but record it so you can review later.", icon: Eye },
  block: { label: "Stop the request", help: "Don\u2019t let this content through at all.", icon: Ban },
};

// Blocking rules should run first, then redaction, then flags.
const PRIORITY: Record<Action, number> = { block: 10, redact: 5, flag: 1 };

const GROUPS = ["Personal data", "Money & secrets", "Conduct", "Privacy requests"] as const;

// Conditions that templates use but the builder doesn't offer (context-driven or always-on).
const EXTRA_CONDITION_LABELS: Record<string, string> = {
  unencrypted_pan: "Unmasked card numbers",
  audit_log_required: "Every request (for the audit log)",
  data_retention_exceeded: "Data kept past its retention limit",
  unauthorized_access: "Access that isn\u2019t authorised",
};

const ALL_ACTION_LABELS: Record<string, string> = {
  redact: "remove it",
  flag: "tell me",
  block: "stop the request",
  alert: "send an alert",
  allow: "let it through",
};

/** Plain-language one-liner for a stored rule, e.g. "Personal information → remove it". */
export function describeRule(rule: { condition: string; action: string }): string {
  const what =
    PROTECTIONS.find((p) => p.condition === rule.condition)?.label ??
    EXTRA_CONDITION_LABELS[rule.condition] ??
    rule.condition;
  return `${what} \u2192 ${ALL_ACTION_LABELS[rule.action] ?? rule.action}`;
}

interface Props {
  onClose: () => void;
}

export default function PolicyBuilder({ onClose }: Props) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [choices, setChoices] = useState<Record<string, Action | null>>({});
  const [created, setCreated] = useState<any>(null);
  const [testText, setTestText] = useState("");
  const [testResult, setTestResult] = useState<any>(null);

  const selected = PROTECTIONS.filter((p) => choices[p.condition]);

  const createMutation = useMutation({
    mutationFn: () =>
      policyApi.createPolicy({
        name: name.trim(),
        description: selected.map((p) => `${p.label}: ${ACTION_META[choices[p.condition]!].label}`).join("; "),
        policy_type: "content_filter",
        enabled: true,
        tags: ["custom"],
        rules: selected.map((p) => ({
          condition: p.condition,
          action: choices[p.condition],
          priority: PRIORITY[choices[p.condition]!],
        })),
      }),
    onSuccess: (policy) => {
      setCreated(policy);
      queryClient.invalidateQueries({ queryKey: ["policies"] });
    },
  });

  const testMutation = useMutation({
    mutationFn: () => policyApi.evaluatePolicies({ content: testText, policy_ids: [created.id] }),
    onSuccess: setTestResult,
  });

  const toggle = (p: Protection) =>
    setChoices((c) => ({ ...c, [p.condition]: c[p.condition] ? null : p.actions[0] }));

  const canSave = name.trim().length > 0 && selected.length > 0 && !createMutation.isPending;

  if (created) {
    return (
      <Card className="mb-8 border-green-300 dark:border-green-800">
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-green-600" />
                &ldquo;{created.name}&rdquo; is on
              </CardTitle>
              <CardDescription>
                It applies to everything checked through your policies from now on. Want to see it work?
              </CardDescription>
            </div>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="try-text">Paste some text to try it</Label>
            <div className="flex gap-2 mt-2">
              <Input
                id="try-text"
                value={testText}
                onChange={(e) => setTestText(e.target.value)}
                placeholder={selected[0]?.example ?? "Type something\u2026"}
              />
              <Button onClick={() => testMutation.mutate()} disabled={!testText.trim() || testMutation.isPending}>
                {testMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Check"}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Try, for example: <button type="button" className="underline" onClick={() => setTestText(selected[0]?.example ?? "")}>{selected[0]?.example}</button>
            </p>
          </div>
          {testResult && (
            <Alert variant={testResult.allowed ? "default" : "destructive"}>
              <AlertDescription>
                {testResult.violations.length === 0 ? (
                  <p>Nothing found &mdash; this text would go through untouched.</p>
                ) : (
                  <div className="space-y-1">
                    <p className="font-medium">
                      {!testResult.allowed
                        ? "This request would be stopped."
                        : testResult.modified_content
                          ? "This text would go through with the sensitive part removed."
                          : "This text would go through, and you\u2019d be told about it."}
                    </p>
                    <ul className="list-disc pl-5">
                      {testResult.violations.map((v: any, i: number) => {
                        const prot = PROTECTIONS.find((p) => v.reason.includes(`'${p.condition}'`));
                        return <li key={i}>Found: {prot?.label ?? v.reason}</li>;
                      })}
                    </ul>
                  </div>
                )}
              </AlertDescription>
            </Alert>
          )}
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>Done</Button>
            <Button
              variant="ghost"
              onClick={() => { setCreated(null); setTestResult(null); setTestText(""); setName(""); setChoices({}); }}
            >
              Create another
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="mb-8 border-primary/40">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>Create a policy</CardTitle>
            <CardDescription>
              Tick what you want Rampart to look out for, then choose what should happen when it finds it.
            </CardDescription>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div>
          <Label htmlFor="policy-name">Give it a name</Label>
          <Input
            id="policy-name"
            className="mt-2 max-w-md"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Support chat guardrails"
          />
        </div>

        {GROUPS.map((group) => (
          <div key={group}>
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">{group}</h3>
            <div className="space-y-2">
              {PROTECTIONS.filter((p) => p.group === group).map((p) => {
                const chosen = choices[p.condition];
                return (
                  <div
                    key={p.condition}
                    className={`rounded-lg border p-3 transition ${chosen ? "border-primary bg-accent/40" : "border-border"}`}
                  >
                    <label className="flex items-start gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        className="mt-1 h-4 w-4"
                        checked={!!chosen}
                        onChange={() => toggle(p)}
                      />
                      <div className="flex-1">
                        <div className="font-medium">{p.label}</div>
                        <div className="text-sm text-muted-foreground">{p.help}</div>
                      </div>
                    </label>
                    {chosen && (
                      <div className="mt-3 ml-7">
                        <div className="text-xs text-muted-foreground mb-1">When found:</div>
                        <div className="flex flex-wrap gap-2">
                          {p.actions.map((a) => {
                            const Icon = ACTION_META[a].icon;
                            return (
                              <button
                                key={a}
                                type="button"
                                title={ACTION_META[a].help}
                                onClick={() => setChoices((c) => ({ ...c, [p.condition]: a }))}
                                className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm transition ${
                                  chosen === a
                                    ? "border-primary bg-primary text-primary-foreground"
                                    : "border-border hover:bg-accent"
                                }`}
                              >
                                <Icon className="h-3.5 w-3.5" />
                                {ACTION_META[a].label}
                              </button>
                            );
                          })}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">{ACTION_META[chosen].help}</p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}

        {createMutation.isError && (
          <Alert variant="destructive">
            <AlertDescription>Couldn&apos;t save the policy. Please try again.</AlertDescription>
          </Alert>
        )}

        <div className="flex items-center justify-between border-t pt-4">
          <p className="text-sm text-muted-foreground">
            {selected.length === 0
              ? "Pick at least one thing to look out for."
              : `${selected.length} protection${selected.length === 1 ? "" : "s"} selected`}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={() => createMutation.mutate()} disabled={!canSave}>
              {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Turn it on
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
