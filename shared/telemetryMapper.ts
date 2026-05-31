export interface TelemetryEvent {
  event: 'click' | 'input' | 'scroll' | 'navigation' | 'page_visit';
  timestamp: number;
  url: string;
  title: string;
  automation: {
    selector: string | null;
    xpath: string | null;
    tag: string | null;
    inputType: string | null;
  };
  raw?: {
    text?: string;
    value?: string;
    length?: number;
    fieldName?: string;
    y?: number;
  };
}

export interface CanonicalStep {
  type: string;
  action: string;
  params: Record<string, any>;
}

export function mapTelemetryToSteps(events: TelemetryEvent[]): CanonicalStep[] {
  return events.map((event) => {
    switch (event.event) {
      case 'click':
        return {
          type: 'browser',
          action: 'click',
          params: {
            selector: event.automation.selector || event.automation.xpath || '',
            url: event.url,
            text: event.raw?.text || ''
          }
        };
      case 'input':
        return {
          type: 'browser',
          action: 'fill',
          params: {
            selector: event.automation.selector || event.automation.xpath || '',
            value: event.raw?.value || '',
            url: event.url
          }
        };
      case 'scroll':
        return {
          type: 'browser',
          action: 'scroll',
          params: {
            y: event.raw?.y || 0,
            url: event.url
          }
        };
      case 'navigation':
      case 'page_visit':
        return {
          type: 'browser',
          action: 'navigate',
          params: {
            url: event.url
          }
        };
      default:
        return {
          type: 'unknown',
          action: event.event,
          params: { ...event }
        };
    }
  });
}
