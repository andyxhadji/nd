import { Circle } from 'lucide-react';

interface ConnectionStatusProps {
  isConnected: boolean;
  isLoading: boolean;
  lastUpdate?: Date;
}

export function ConnectionStatus({ isConnected, isLoading, lastUpdate }: ConnectionStatusProps) {
  const statusColor = isConnected ? 'text-green-500' : 'text-red-500';
  const statusText = isConnected ? 'Connected' : 'Disconnected';

  const updateText = lastUpdate
    ? `Updated ${Math.floor((Date.now() - lastUpdate.getTime()) / 1000)}s ago`
    : 'Never updated';

  return (
    <div className="flex items-center gap-2 text-sm text-gray-600">
      <Circle className={`w-3 h-3 fill-current ${statusColor} ${isLoading ? 'animate-pulse' : ''}`} />
      <span>{statusText}</span>
      <span className="text-gray-400">•</span>
      <span className="text-gray-500">{updateText}</span>
    </div>
  );
}
