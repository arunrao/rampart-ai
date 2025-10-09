'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { PlayCircle, CheckCircle, XCircle, Clock, AlertTriangle, FlaskConical } from 'lucide-react';
import { fetchJSON } from '@/utils/api';

interface TestScenario {
  id: string;
  name: string;
  category: string;
  description: string;
  test_input: string;
  expected_threat: string | null;
  expected_severity: string | null;
  should_block: boolean;
  context_type: string;
}

interface TestResult {
  scenario_id: string;
  scenario_name: string;
  passed: boolean;
  expected: any;
  actual: any;
  execution_time_ms: number;
  error?: string;
}

interface TestRunResponse {
  run_id: string;
  total_tests: number;
  passed: number;
  failed: number;
  results: TestResult[];
  total_duration_ms: number;
}

export default function TestingPage() {
  const [scenarios, setScenarios] = useState<TestScenario[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<TestRunResponse | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchScenarios();
    fetchCategories();
  }, []);

  const fetchScenarios = async () => {
    try {
      const data = await fetchJSON<TestScenario[]>(`${process.env.NEXT_PUBLIC_API_URL}/test/scenarios`);
      setScenarios(data);
    } catch (err) {
      console.error('Failed to fetch scenarios:', err);
    }
  };

  const fetchCategories = async () => {
    try {
      const data = await fetchJSON<any[]>(`${process.env.NEXT_PUBLIC_API_URL}/test/categories`);
      setCategories(data);
    } catch (err) {
      console.error('Failed to fetch categories:', err);
    }
  };

  const runTests = async (category?: string) => {
    setIsRunning(true);
    setError(null);
    setTestResults(null);

    try {
      const body = category ? { category } : {};
      const data = await fetchJSON<TestRunResponse>(`${process.env.NEXT_PUBLIC_API_URL}/test/run`, {
        method: 'POST',
        body: JSON.stringify(body)
      });
      setTestResults(data);
    } catch (err: any) {
      setError(err.message || 'Failed to run tests. Please try again.');
      console.error('Test run error:', err);
    } finally {
      setIsRunning(false);
    }
  };

  const getCategoryColor = (category: string) => {
    const colors: { [key: string]: string } = {
      prompt_injection: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
      jailbreak: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
      data_exfiltration: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
      pii_detection: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
      safe_content: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    };
    return colors[category] || 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-400';
  };

  const filteredScenarios = selectedCategory
    ? scenarios.filter(s => s.category === selectedCategory)
    : scenarios;

  return (
    <div className="min-h-screen bg-background p-6">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center space-x-3">
            <Link href="/" className="flex items-center space-x-2 text-muted-foreground hover:text-foreground">
              <FlaskConical className="h-6 w-6" />
              <span className="font-semibold">Project Rampart</span>
            </Link>
            <span className="text-muted-foreground">/</span>
            <h1 className="text-xl font-bold text-foreground">Security Testing</h1>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8 max-w-7xl">

      {/* Quick Actions */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Quick Test</CardTitle>
          <CardDescription>Run all tests or select a category</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button
              onClick={() => runTests()}
              disabled={isRunning}
              className="flex items-center gap-2"
            >
              {isRunning ? (
                <>
                  <Clock className="h-4 w-4 animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <PlayCircle className="h-4 w-4" />
                  Run All Tests ({scenarios.length})
                </>
              )}
            </Button>

            {categories.map(cat => (
              <Button
                key={cat.name}
                onClick={() => runTests(cat.name)}
                disabled={isRunning}
                variant="outline"
              >
                {cat.name.replace(/_/g, ' ')} ({cat.count})
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Test Results */}
      {testResults && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Test Results</CardTitle>
            <CardDescription>
              Completed in {testResults.total_duration_ms.toFixed(2)}ms
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="text-center p-4 bg-muted rounded-lg">
                <div className="text-3xl font-bold">{testResults.total_tests}</div>
                <div className="text-sm text-muted-foreground">Total Tests</div>
              </div>
              <div className="text-center p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <div className="text-3xl font-bold text-green-600 dark:text-green-400">{testResults.passed}</div>
                <div className="text-sm text-muted-foreground">Passed</div>
              </div>
              <div className="text-center p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                <div className="text-3xl font-bold text-red-600 dark:text-red-400">{testResults.failed}</div>
                <div className="text-sm text-muted-foreground">Failed</div>
              </div>
            </div>

            <div className="space-y-3">
              {testResults.results.map(result => (
                <div
                  key={result.scenario_id}
                  className={`p-4 rounded-lg border ${
                    result.passed
                      ? 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800'
                      : 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 flex-1">
                      {result.passed ? (
                        <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400 mt-0.5" />
                      ) : (
                        <XCircle className="h-5 w-5 text-red-600 dark:text-red-400 mt-0.5" />
                      )}
                      <div className="flex-1">
                        <div className="font-medium text-foreground">{result.scenario_name}</div>
                        <div className="text-sm text-muted-foreground mt-1">
                          {result.scenario_id}
                        </div>
                        {result.error && (
                          <div className="mt-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-2">
                            <AlertTriangle className="h-4 w-4 text-red-600 dark:text-red-400 mt-0.5" />
                            <div className="text-sm text-red-800 dark:text-red-300">{result.error}</div>
                          </div>
                        )}
                        {!result.passed && !result.error && (
                          <div className="mt-2 text-sm">
                            <div className="font-medium text-foreground">Expected:</div>
                            <pre className="bg-card p-2 rounded mt-1 text-xs overflow-x-auto">
                              {JSON.stringify(result.expected, null, 2)}
                            </pre>
                            <div className="font-medium mt-2 text-foreground">Actual:</div>
                            <pre className="bg-card p-2 rounded mt-1 text-xs overflow-x-auto">
                              {JSON.stringify(result.actual, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>
                    <Badge variant="outline" className="ml-4">
                      {result.execution_time_ms.toFixed(2)}ms
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error Display */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400 mt-0.5" />
          <div className="text-sm text-red-800 dark:text-red-300">{error}</div>
        </div>
      )}

      {/* Test Scenarios List */}
      <Card>
        <CardHeader>
          <CardTitle>Available Test Scenarios</CardTitle>
          <CardDescription>
            {scenarios.length} scenarios across {categories.length} categories
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Category Filter */}
          <div className="flex flex-wrap gap-2 mb-6">
            <Button
              variant={selectedCategory === null ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedCategory(null)}
            >
              All ({scenarios.length})
            </Button>
            {categories.map(cat => (
              <Button
                key={cat.name}
                variant={selectedCategory === cat.name ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSelectedCategory(cat.name)}
              >
                {cat.name.replace(/_/g, ' ')} ({cat.count})
              </Button>
            ))}
          </div>

          {/* Scenarios Grid */}
          <div className="grid gap-4">
            {filteredScenarios.map(scenario => (
              <div
                key={scenario.id}
                className="p-4 border rounded-lg hover:shadow-md transition-shadow bg-card"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className="font-medium text-foreground">{scenario.name}</h3>
                    <p className="text-sm text-muted-foreground mt-1">{scenario.description}</p>
                  </div>
                  <Badge className={getCategoryColor(scenario.category)}>
                    {scenario.category.replace(/_/g, ' ')}
                  </Badge>
                </div>
                
                <div className="mt-3 p-3 bg-muted rounded text-sm font-mono">
                  {scenario.test_input}
                </div>

                <div className="mt-3 flex items-center gap-4 text-sm">
                  {scenario.expected_threat && (
                    <div>
                      <span className="text-muted-foreground">Expected:</span>{' '}
                      <Badge variant="outline">{scenario.expected_threat}</Badge>
                    </div>
                  )}
                  {scenario.expected_severity && (
                    <div>
                      <span className="text-muted-foreground">Severity:</span>{' '}
                      <Badge variant="outline">{scenario.expected_severity}</Badge>
                    </div>
                  )}
                  <div>
                    <span className="text-muted-foreground">Should Block:</span>{' '}
                    <Badge variant={scenario.should_block ? 'destructive' : 'default'}>
                      {scenario.should_block ? 'Yes' : 'No'}
                    </Badge>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      </main>
    </div>
  );
}
