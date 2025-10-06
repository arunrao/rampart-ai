import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 4,
  }).format(amount);
}

export function formatNumber(num: number): string {
  return new Intl.NumberFormat("en-US").format(num);
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(date));
}

export function getSeverityColor(severity: string): string {
  switch (severity.toLowerCase()) {
    case "critical":
      return "text-red-600 bg-red-50 border-red-200";
    case "high":
      return "text-orange-600 bg-orange-50 border-orange-200";
    case "medium":
      return "text-yellow-600 bg-yellow-50 border-yellow-200";
    case "low":
      return "text-blue-600 bg-blue-50 border-blue-200";
    default:
      return "text-gray-600 bg-gray-50 border-gray-200";
  }
}

export function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case "success":
    case "resolved":
    case "active":
      return "text-green-600 bg-green-50 border-green-200";
    case "error":
    case "open":
      return "text-red-600 bg-red-50 border-red-200";
    case "blocked":
      return "text-red-700 bg-red-100 border-red-300";
    case "investigating":
      return "text-yellow-600 bg-yellow-50 border-yellow-200";
    case "false_positive":
      return "text-gray-600 bg-gray-50 border-gray-200";
    default:
      return "text-blue-600 bg-blue-50 border-blue-200";
  }
}
