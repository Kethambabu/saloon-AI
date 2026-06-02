/**
 * Loyalty Sync Service
 * Manages automatic refreshing of loyalty points when key events occur
 * This service acts as a bridge between API calls and the useLoyalty hook
 */

export type LoyaltyEventType =
  | 'appointment_completed'
  | 'appointment_cancelled'
  | 'review_submitted'
  | 'app_usage_bonus'
  | 'manual_adjustment'
  | 'manual_refresh';

interface LoyaltyListener {
  id: string;
  callback: (eventType: LoyaltyEventType) => void;
}

class LoyaltySyncService {
  private listeners: Map<string, LoyaltyListener> = new Map();
  private listenerCounter = 0;
  private eventQueue: LoyaltyEventType[] = [];
  private isProcessing = false;

  /**
   * Subscribe to loyalty update events
   * Returns a function to unsubscribe
   */
  subscribe(callback: (eventType: LoyaltyEventType) => void): () => void {
    const id = `listener_${++this.listenerCounter}`;
    this.listeners.set(id, { id, callback });

    // Return unsubscribe function
    return () => {
      this.listeners.delete(id);
    };
  }

  /**
   * Emit a loyalty event - notifies all subscribers
   */
  emit(eventType: LoyaltyEventType): void {
    this.eventQueue.push(eventType);
    this.processQueue();
  }

  /**
   * Process queued events
   */
  private processQueue(): void {
    if (this.isProcessing || this.eventQueue.length === 0) {
      return;
    }

    this.isProcessing = true;

    // Process all queued events
    while (this.eventQueue.length > 0) {
      const event = this.eventQueue.shift();
      if (event) {
        this.notifyListeners(event);
      }
    }

    this.isProcessing = false;
  }

  /**
   * Notify all listeners of an event
   */
  private notifyListeners(eventType: LoyaltyEventType): void {
    this.listeners.forEach((listener) => {
      try {
        listener.callback(eventType);
      } catch (err) {
        console.error(`Error in loyalty listener ${listener.id}:`, err);
      }
    });
  }

  /**
   * Get total number of active listeners
   */
  getListenerCount(): number {
    return this.listeners.size;
  }

  /**
   * Clear all listeners (useful for cleanup)
   */
  clearListeners(): void {
    this.listeners.clear();
  }
}

// Export singleton instance
export const loyaltySyncService = new LoyaltySyncService();

export default loyaltySyncService;
