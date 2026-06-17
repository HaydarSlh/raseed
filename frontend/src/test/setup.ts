import '@testing-library/jest-dom';

// Recharts' ResponsiveContainer requires ResizeObserver which jsdom lacks.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver = ResizeObserverStub;
