export {};

declare global {
  interface Window {
    mayaDesktop: {
      getHealth(): Promise<{
        ok: boolean;
        mode: 'mock' | 'unavailable';
        databaseReady: boolean;
        capabilities: string[];
      }>;
    };
  }
}
