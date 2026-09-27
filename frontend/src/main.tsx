import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { PrivacyPolicyPage } from './pages/PrivacyPolicyPage'
import { TermsPage } from './pages/TermsPage'
import { WelcomePage } from './pages/WelcomePage'

// This app has no client-side router (the case-management workspace itself
// is a single page driven by tab state, not distinct URLs -- see App.tsx).
// The Privacy Policy, Terms & Conditions and public Welcome page are
// different in kind: static, externally-linkable documents/pages that
// deserve a real, bookmarkable URL and don't belong inside the workspace's
// Lenis/GSAP/Three.js chrome (Welcome has its own, entirely separate
// Neo-Brutalist design system -- see WelcomePage.tsx). Rather than pull in
// a full router for three static pages, resolve the path once at load
// (these are reached by a real navigation -- a footer/nav link or a
// typed/bookmarked URL -- never a client-side transition, so there's
// nothing to react to after mount).
function resolvePage() {
  switch (window.location.pathname) {
    case '/privacy':
      return <PrivacyPolicyPage />;
    case '/terms':
      return <TermsPage />;
    case '/welcome':
      return <WelcomePage />;
    default:
      return <App />;
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {resolvePage()}
  </StrictMode>,
)
