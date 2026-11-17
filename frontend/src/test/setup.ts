import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
  localStorage.clear();
});

// jsdom lacks these browser APIs.
URL.createObjectURL = () => "blob:preview";
URL.revokeObjectURL = () => undefined;
window.scrollTo = () => undefined;
Element.prototype.scrollIntoView = () => undefined;
