import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MotionConfig } from "motion/react";
import App from "./App.tsx";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element not found.");
}

/*
 * reducedMotion="user" drops transform and layout animations for
 * anyone with the OS setting enabled, keeping opacity fades. The
 * CSS animations in App.css are unaffected by this.
 */

createRoot(rootElement).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <App />
    </MotionConfig>
  </StrictMode>,
);