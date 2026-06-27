import "@testing-library/jest-dom";

// Node 22+ may expose a broken global `localStorage` unless --localstorage-file is set.
// Tests use bare `localStorage` / `sessionStorage`; bind globals to jsdom's storage.
if (typeof window !== "undefined") {
  Object.defineProperty(globalThis, "localStorage", {
    value: window.localStorage,
    configurable: true,
    writable: true,
  });
  Object.defineProperty(globalThis, "sessionStorage", {
    value: window.sessionStorage,
    configurable: true,
    writable: true,
  });
}

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {},
  }),
});
