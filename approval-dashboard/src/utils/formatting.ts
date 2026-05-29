/**
 * Format relative time (e.g., "5m ago", "2h ago").
 */
export function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) {
    return `${diffSeconds}s ago`;
  } else if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  } else if (diffHours < 24) {
    return `${diffHours}h ago`;
  } else {
    return `${diffDays}d ago`;
  }
}

/**
 * Format duration (e.g., "Waiting 5m", "Waiting 2h").
 */
export function formatDuration(startDate: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - startDate.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);

  if (diffMinutes < 60) {
    return `Waiting ${diffMinutes}m`;
  } else {
    return `Waiting ${diffHours}h`;
  }
}

/**
 * Format expiration countdown (e.g., "Expires in 71h", "Expires in 2d").
 */
export function formatExpiration(expiresAt: Date): string {
  const now = new Date();
  const diffMs = expiresAt.getTime() - now.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);

  if (diffMs < 0) {
    return 'Expired';
  } else if (diffHours < 24) {
    return `Expires in ${diffHours}h`;
  } else {
    return `Expires in ${diffDays}d`;
  }
}

/**
 * Get confidence badge color based on score.
 */
export function getConfidenceColor(confidence: number): string {
  if (confidence < 70) return 'bg-red-100 text-red-800';
  if (confidence < 85) return 'bg-yellow-100 text-yellow-800';
  return 'bg-green-100 text-green-800';
}

/**
 * Get approval type badge color.
 */
export function getApprovalTypeBadge(type: string): { bg: string; text: string; label: string } {
  switch (type) {
    case 'spec':
      return { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Spec Review' };
    case 'roborev':
      return { bg: 'bg-orange-100', text: 'text-orange-800', label: 'Roborev Failure' };
    case 'post':
      return { bg: 'bg-green-100', text: 'text-green-800', label: 'Response Approval' };
    default:
      return { bg: 'bg-gray-100', text: 'text-gray-800', label: 'Unknown' };
  }
}
