/**
 * Error Display Component
 */

import React from 'react';

interface ErrorProps {
  message: string;
  details?: string;
  onDismiss?: () => void;
}

export const Error: React.FC<ErrorProps> = ({ message, details, onDismiss }) => {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
      <div className="flex justify-between items-start">
        <div>
          <h3 className="text-red-800 font-semibold">{message}</h3>
          {details && <p className="text-red-700 text-sm mt-1">{details}</p>}
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-red-500 hover:text-red-700"
            aria-label="Dismiss error"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
};

export default Error;
