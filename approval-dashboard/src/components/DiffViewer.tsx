import { useEffect, useRef } from 'react';
import * as Diff2Html from 'diff2html';
import 'diff2html/bundles/css/diff2html.min.css';

interface DiffViewerProps {
  diff: string;
}

export function DiffViewer({ diff }: DiffViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current && diff) {
      try {
        const html = Diff2Html.html(diff, {
          drawFileList: true,
          matching: 'lines',
          outputFormat: 'side-by-side',
          renderNothingWhenEmpty: false,
        });
        containerRef.current.innerHTML = html;
      } catch (error) {
        console.error('Failed to render diff:', error);
        containerRef.current.innerHTML = `<pre class="text-xs text-red-600">Failed to parse diff: ${error}</pre>`;
      }
    }
  }, [diff]);

  return (
    <div>
      <h4 className="font-medium text-sm text-gray-900 mb-2">Changes (git diff)</h4>
      <div
        ref={containerRef}
        className="border border-gray-300 rounded-md overflow-x-auto max-h-96 overflow-y-auto"
      />
    </div>
  );
}
